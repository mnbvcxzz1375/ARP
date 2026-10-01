"""Dashboard CSRF dependency: extract CSRF token from cookie, validate header."""
from typing import Annotated

from fastapi import Cookie, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_session
from app.dependencies.auth import get_current_session
from app.models.dashboard_session import DashboardSession
from app.services.csrf_service import validate_csrf


async def get_csrf_cookie(
    csrf_token: Annotated[
        str | None, Cookie(alias=get_settings().csrf_cookie_name)
    ] = None,
) -> str | None:
    """Extract the CSRF token from the non-HttpOnly cookie.

    The cookie name comes from settings so it always matches the name
    dashboard_auth writes at login/logout time.
    """
    return csrf_token


async def get_csrf_header(
    x_csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> str | None:
    """Extract the CSRF token from the X-CSRF-Token header."""
    return x_csrf_token


async def require_csrf(
    request: Request,
    session: AsyncSession = Depends(get_session),
    ds: DashboardSession = Depends(get_current_session),
    csrf_cookie: str | None = Depends(get_csrf_cookie),
    csrf_header: str | None = Depends(get_csrf_header),
) -> None:
    """Validate CSRF for mutation requests (POST/PUT/PATCH/DELETE).

    GET/HEAD/OPTIONS are exempt. Raises 403 on missing or invalid CSRF.
    """
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return

    await validate_csrf(session, ds, csrf_header or "")
