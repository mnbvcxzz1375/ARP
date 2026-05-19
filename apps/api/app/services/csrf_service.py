"""CSRF token validation."""
import hashlib
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DomainException
from app.models.dashboard_session import DashboardSession
from app.protocol.constants import ErrorCode


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def validate_csrf(
    session: AsyncSession,
    ds: DashboardSession,
    csrf_token: str,
) -> None:
    """Validate CSRF token against session hash.

    Raises DomainException(CSRF_TOKEN_MISSING) or DomainException(CSRF_TOKEN_INVALID).
    Updates last_csrf_seen_at on success.
    """
    if not csrf_token:
        raise DomainException(
            ErrorCode.CSRF_TOKEN_MISSING,
            "CSRF token is missing from request headers",
            status_code=403,
        )

    if _hash_token(csrf_token) != ds.csrf_hash:
        raise DomainException(
            ErrorCode.CSRF_TOKEN_INVALID,
            "CSRF token is invalid",
            status_code=403,
        )

    ds.last_csrf_seen_at = datetime.now(UTC)
    await session.flush()
