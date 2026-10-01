"""Dashboard authentication endpoints: login, logout, step-up, me."""
import hashlib
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_session
from app.dependencies.auth import CurrentSession
from app.dependencies.csrf import require_csrf
from app.exceptions import DomainException
from app.models.api_key import ApiKey
from app.models.dashboard_session import DashboardSession
from app.models.user import User
from app.protocol.constants import ErrorCode
from app.schemas.dashboard import (
    UpdateUserPreferencesRequest,
    UpdateUserProfileRequest,
    UserPreferencesResponse,
    UserProfileResponse,
)
from app.services.audit_service import write_audit
from app.services.dashboard_session_service import (
    create_session,
    revoke_session,
    rotate_session,
    set_step_up,
)
from app.services.user_service import find_user_by_api_key, update_username

router = APIRouter(prefix="/v1/dashboard/auth", tags=["dashboard-auth"])


def _hash_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()


def _set_cookies(response: Response, session_token: str, csrf_token: str) -> None:
    settings = get_settings()
    base_kwargs = {
        "samesite": "lax",
        "path": "/",
        "secure": settings.session_secure_cookie,
    }
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_token,
        httponly=True,
        **base_kwargs,
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        httponly=False,
        **base_kwargs,
    )


def _clear_cookies(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(key=settings.session_cookie_name, path="/")
    response.delete_cookie(key=settings.csrf_cookie_name, path="/")


@router.post("/login")
async def login(
    body: dict,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    """Authenticate with username + API key, create session, set cookies."""
    username = body.get("username", "")
    api_key = body.get("api_key", "")

    # Coerce non-string credentials early: hashing requires .encode().
    if not isinstance(username, str) or not isinstance(api_key, str):
        await write_audit(
            session,
            actor_type="user",
            actor_id="unknown",
            action="dashboard.login.failure",
            resource_type="session",
            details={"reason": "malformed_credentials"},
        )
        await session.commit()
        raise DomainException(
            ErrorCode.INVALID_CREDENTIALS,
            "Username and API key are required",
            status_code=401,
        )

    request_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    if not username or not api_key:
        await write_audit(
            session,
            actor_type="user",
            actor_id="unknown",
            action="dashboard.login.failure",
            resource_type="session",
            details={"reason": "missing_credentials"},
        )
        await session.commit()
        raise DomainException(
            ErrorCode.INVALID_CREDENTIALS,
            "Username and API key are required",
            status_code=401,
        )

    # Key-first resolution (usernames are non-unique display labels since
    # migration 0030): the API key hash uniquely identifies one active
    # key and its owner. The submitted username is recorded for audit
    # traceability but never used to match the user, so duplicate
    # usernames cannot misroute authentication.
    key_hash = _hash_key(api_key)
    resolved = await find_user_by_api_key(session, key_hash)

    if resolved is None:
        await write_audit(
            session,
            actor_type="user",
            actor_id="unknown",
            action="dashboard.login.failure",
            resource_type="session",
            details={"reason": "invalid_credentials", "submitted_username": username},
        )
        await session.commit()
        raise DomainException(
            ErrorCode.INVALID_CREDENTIALS,
            "Invalid credentials",
            status_code=401,
        )

    user, _found_key = resolved

    if user.is_disabled:
        await write_audit(
            session,
            actor_type="user",
            actor_id=str(user.id),
            action="dashboard.login.failure",
            resource_type="session",
            details={"reason": "user_disabled"},
        )
        await session.commit()
        raise DomainException(
            ErrorCode.USER_DISABLED,
            "Account has been disabled",
            status_code=403,
        )

    ds, token, csrf_token = await create_session(
        session, user, request_ip=request_ip, user_agent=user_agent
    )

    await write_audit(
        session,
        actor_type="user",
        actor_id=str(user.id),
        action="dashboard.login.success",
        resource_type="session",
        resource_id=str(ds.id),
    )
    await session.commit()

    _set_cookies(response, token, csrf_token)
    response.status_code = 200
    return {"message": "authenticated"}


@router.post("/logout")
async def logout(
    response: Response,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_csrf),
):
    """Revoke current session, clear cookies."""
    await revoke_session(
        session, ds, reason="logout", revoked_by_user_id=ds.user_id
    )
    await write_audit(
        session,
        actor_type="user",
        actor_id=str(ds.user_id),
        action="dashboard.logout",
        resource_type="session",
        resource_id=str(ds.id),
    )
    await session.commit()

    _clear_cookies(response)
    response.status_code = 200
    return {"message": "logged out"}


@router.post("/step-up")
async def step_up(
    body: dict,
    request: Request,
    response: Response,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_csrf),
):
    """Re-verify API key to extend step-up window."""
    api_key = body.get("api_key", "")
    if not api_key:
        await write_audit(
            session,
            actor_type="user",
            actor_id=str(ds.user_id),
            action="dashboard.step_up.failure",
            resource_type="session",
            details={"reason": "missing_credentials"},
        )
        await session.commit()
        raise DomainException(
            ErrorCode.INVALID_STEP_UP,
            "Invalid step-up credentials",
            status_code=403,
        )

    key_hash = _hash_key(api_key)
    key_result = await session.execute(
        select(ApiKey).where(
            ApiKey.user_id == ds.user_id,
            ApiKey.key_hash == key_hash,
            ApiKey.is_revoked == False,
            or_(ApiKey.expires_at == None, ApiKey.expires_at > datetime.now(UTC)),
        )
    )
    if key_result.scalar_one_or_none() is None:
        await write_audit(
            session,
            actor_type="user",
            actor_id=str(ds.user_id),
            action="dashboard.step_up.failure",
            resource_type="session",
            details={"reason": "invalid_credentials"},
        )
        await session.commit()
        raise DomainException(
            ErrorCode.INVALID_STEP_UP,
            "Invalid step-up credentials",
            status_code=403,
        )

    new_ds, token, csrf_token = await rotate_session(
        session,
        ds,
        reason="step_up",
        request_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await set_step_up(session, new_ds)

    await write_audit(
        session,
        actor_type="user",
        actor_id=str(ds.user_id),
        action="dashboard.step_up.success",
        resource_type="session",
        resource_id=str(new_ds.id),
    )
    await session.commit()

    _set_cookies(response, token, csrf_token)
    response.status_code = 200
    return {"message": "step-up verified"}


@router.get("/me")
async def me(
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
):
    """Return current user and session info."""
    from app.services.dashboard_session_service import get_session_info

    info = await get_session_info(session, ds)
    await session.commit()
    return info


async def _load_user(session: AsyncSession, ds: DashboardSession) -> User:
    """Fetch the user row behind the current session."""
    result = await session.execute(
        select(User).where(User.id == ds.user_id)
    )
    return result.scalar_one()


@router.get("/me/preferences")
async def get_preferences(
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
):
    """Return the current user's locale and appearance preferences."""
    user = await _load_user(session, ds)
    await session.commit()
    return UserPreferencesResponse(
        locale=user.locale,
        preferences=user.preferences or {},
    )


@router.patch("/me/preferences")
async def update_preferences(
    body: UpdateUserPreferencesRequest,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_csrf),
):
    """Update the current user's locale and/or appearance preferences.

    Absent fields keep their stored value; ``locale: null`` clears the
    locale. Provided ``preferences`` are shallow-merged into the stored
    object so partial updates do not wipe unrelated keys.
    """
    user = await _load_user(session, ds)

    updates = body.model_dump(exclude_unset=True)
    if "locale" in updates:
        user.locale = updates["locale"]
    if "preferences" in updates:
        user.preferences = {**(user.preferences or {}), **updates["preferences"]}

    await write_audit(
        session,
        actor_type="user",
        actor_id=str(ds.user_id),
        action="dashboard.preferences.update",
        resource_type="user",
        resource_id=str(user.id),
        details={"changed_fields": sorted(updates)},
    )
    await session.commit()

    return UserPreferencesResponse(
        locale=user.locale,
        preferences=user.preferences or {},
    )


@router.patch("/me/profile", response_model=UserProfileResponse)
async def update_profile(
    body: UpdateUserProfileRequest,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_csrf),
):
    """Rename the current user.

    The username is a non-unique display label; the user_id never
    changes. The new name is trimmed and length-checked (400 on invalid
    input), the change is audited, and the session's cached /me picks
    the new name up on the next fetch.
    """
    from fastapi import HTTPException, status as http_status

    user = await _load_user(session, ds)
    try:
        new_name = await update_username(session, user, body.username)
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    await write_audit(
        session,
        actor_type="user",
        actor_id=str(ds.user_id),
        action="dashboard.profile.update",
        resource_type="user",
        resource_id=str(user.id),
        details={"username": new_name},
    )
    await session.commit()

    return UserProfileResponse(user_id=str(user.id), username=new_name)
