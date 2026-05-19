"""Dashboard auth dependencies: extract session from cookie, require auth."""
from typing import Annotated

from fastapi import Cookie, Depends
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.exceptions import DomainException
from app.models.dashboard_session import DashboardSession
from app.protocol.constants import ErrorCode
from app.services.dashboard_session_service import (
    find_session_by_token,
    update_last_seen,
)


async def get_session_token(
    session_token: Annotated[str | None, Cookie(alias="agentnet_session")] = None,
) -> str | None:
    """Extract the session token from the HttpOnly cookie."""
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
