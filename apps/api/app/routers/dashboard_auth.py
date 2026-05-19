"""Dashboard authentication endpoints: login, logout, step-up, me."""
import hashlib

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_session
from app.dependencies.auth import CurrentSession
from app.exceptions import DomainException
from app.models.api_key import ApiKey
from app.models.user import User
from app.protocol.constants import ErrorCode
from app.services.audit_service import write_audit
from app.services.dashboard_session_service import (
    create_session,
    revoke_session,
    rotate_session,
    set_step_up,
)

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
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    """Authenticate with username + API key, create session, set cookies."""
    username = body.get("username", "")
    api_key = body.get("api_key", "")

    if not username or not api_key:
        raise DomainException(
            ErrorCode.INVALID_CREDENTIALS,
            "Username and API key are required",
            status_code=401,
        )

    key_hash = _hash_key(api_key)
    result = await session.execute(
        select(User).where(User.username == username)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise DomainException(
            ErrorCode.INVALID_CREDENTIALS,
            "Invalid credentials",
            status_code=401,
        )

    key_result = await session.execute(
        select(ApiKey).where(
            ApiKey.user_id == user.id,
            ApiKey.key_hash == key_hash,
            ApiKey.is_revoked == False,
        )
    )
    found_key = key_result.scalar_one_or_none()

    if found_key is None:
        raise DomainException(
            ErrorCode.INVALID_CREDENTIALS,
            "Invalid credentials",
            status_code=401,
        )

    if user.is_disabled:
        raise DomainException(
            ErrorCode.USER_DISABLED,
            "Account has been disabled",
            status_code=403,
        )

    ds, token, csrf_token = await create_session(session, user)
    await session.commit()

    await write_audit(
        session,
        actor_type="user",
        actor_id=str(user.id),
        action="dashboard.login.success",
        resource_type="session",
        resource_id=str(ds.id),
    )

    _set_cookies(response, token, csrf_token)
    response.status_code = 200
    return {"message": "authenticated"}


@router.post("/logout")
async def logout(
    response: Response,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
):
    """Revoke current session, clear cookies."""
    await revoke_session(session, ds, reason="logout")
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
    response: Response,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
):
    """Re-verify API key to extend step-up window."""
    api_key = body.get("api_key", "")
    if not api_key:
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
        )
    )
    if key_result.scalar_one_or_none() is None:
        raise DomainException(
            ErrorCode.INVALID_STEP_UP,
            "Invalid step-up credentials",
            status_code=403,
        )

    new_ds, token, csrf_token = await rotate_session(session, ds, reason="step_up")
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
