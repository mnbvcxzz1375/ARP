"""Dashboard auth dependencies: extract session from cookie, require auth."""
from typing import Annotated

from fastapi import Cookie, Depends, Header
from fastapi import status as http_status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_session
from app.exceptions import DomainException
from app.models.api_key import ApiKey
from app.models.dashboard_session import DashboardSession
from app.models.user import User
from app.protocol.constants import ErrorCode
from app.services.auth import hash_key
from app.services.dashboard_session_service import (
    find_session_by_token,
    update_last_seen,
)


async def get_session_token(
    session_token: Annotated[
        str | None, Cookie(alias=get_settings().session_cookie_name)
    ] = None,
) -> str | None:
    """Extract the session token from the HttpOnly cookie.

    The cookie name comes from settings so it always matches the name
    dashboard_auth writes at login/logout time.
    """
    return session_token


async def get_current_session(
    session: AsyncSession = Depends(get_session),
    session_token: str | None = Depends(get_session_token),
) -> DashboardSession:
    """Extract and validate the current DashboardSession from cookie.

    Raises 401 if no cookie, session not found, expired, revoked, or user disabled.
    Updates last_seen_at on valid session.
    """
    if not session_token:
        raise DomainException(
            ErrorCode.INVALID_SESSION,
            "Session cookie not found",
            status_code=http_status.HTTP_401_UNAUTHORIZED,
        )

    ds = await find_session_by_token(session, session_token)
    if ds is None:
        raise DomainException(
            ErrorCode.SESSION_EXPIRED,
            "Session has expired or been revoked",
            status_code=http_status.HTTP_401_UNAUTHORIZED,
        )

    await update_last_seen(session, ds)
    await session.refresh(ds)
    return ds


CurrentSession = Annotated[DashboardSession, Depends(get_current_session)]


async def _resolve_user_by_api_key(
    session: AsyncSession, key: str
) -> User | None:
    """Return the user behind a raw API key, or None when not acceptable.

    Mirrors the key check in services/auth.authenticate (hash lookup,
    not revoked, not expired, user not disabled). Kept here rather than
    imported because services/auth.authenticate raises 401 on failure,
    while the hybrid dependency below needs a soft fallback to the
    console session cookie instead.
    """
    from datetime import UTC, datetime

    key_hash = hash_key(key)
    ak_result = await session.execute(
        select(ApiKey).where(
            ApiKey.key_hash == key_hash,
            ApiKey.is_revoked.is_(False),
            or_(
                ApiKey.expires_at.is_(None),
                ApiKey.expires_at > datetime.now(UTC),
            ),
        )
    )
    api_key = ak_result.scalar_one_or_none()
    if api_key is None:
        return None
    # PK lookup; a disabled user must not retain API access even with a
    # valid key.
    user = await session.get(User, api_key.user_id)
    if user is None or user.is_disabled:
        return None
    return user


async def authenticate_session_or_key(
    session: AsyncSession = Depends(get_session),
    session_token: str | None = Depends(get_session_token),
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> User:
    """Hybrid auth: console session cookie first, static API key second.

    Runtime REST endpoints (routing, tasks, personal scope) are consumed
    both by programmatic clients (agents, SDK, CLI) with X-API-Key /
    Bearer tokens and by the web console, which only carries the
    dashboard session cookie set at login. Accepting either keeps the
    console from being bounced to /login by a 401 it cannot fix.

    Session validation reuses the dashboard rules (not revoked, not
    expired, idle timeout, user not disabled). When both credentials
    are present the session wins; when neither resolves, 401.
    """
    if session_token:
        ds = await find_session_by_token(session, session_token)
        if ds is not None:
            await update_last_seen(session, ds)
            await session.refresh(ds)
            if ds.user is not None:
                return ds.user
    key = x_api_key
    if not key and authorization and authorization.startswith("Bearer "):
        key = authorization[7:]
    if key:
        user = await _resolve_user_by_api_key(session, key)
        if user is not None:
            return user
    raise DomainException(
        ErrorCode.INVALID_SESSION,
        "Missing session cookie or API key",
        status_code=http_status.HTTP_401_UNAUTHORIZED,
    )
