"""Dashboard session management: create, validate, rotate, revoke."""
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.dashboard_session import DashboardSession
from app.models.user import User, UserRole


def _hash_token(token: str) -> str:
    """SHA-256 hex digest."""
    return hashlib.sha256(token.encode()).hexdigest()


def _generate_token() -> str:
    """Generate a cryptographically secure session token."""
    return secrets.token_urlsafe(48)


def _session_lifetime(user: User) -> tuple[timedelta, timedelta]:
    """Return (absolute_lifetime, idle_timeout) based on user role."""
    settings = get_settings()
    if user.role in (UserRole.ADMIN, UserRole.SUPER_ADMIN):
        absolute = timedelta(days=settings.session_admin_lifetime_days)
        idle = timedelta(hours=settings.session_admin_idle_hours)
    else:
        absolute = timedelta(days=settings.session_user_lifetime_days)
        idle = timedelta(hours=settings.session_user_idle_hours)
    return absolute, idle


async def create_session(
    session: AsyncSession,
    user: User,
    request_ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[DashboardSession, str, str]:
    """Create a new session for the user.

    Returns (session, session_token, csrf_token).
    Only the hashes are stored; plain tokens are returned once for cookie-setting.
    """
    now = datetime.now(UTC)
    absolute, idle = _session_lifetime(user)
    token = _generate_token()
    csrf_token = secrets.token_urlsafe(32)

    ds = DashboardSession(
        id=uuid.uuid4(),
        user_id=user.id,
        session_hash=_hash_token(token),
        csrf_hash=_hash_token(csrf_token),
        expires_at=now + absolute,
        idle_expires_at=now + idle,
        request_ip=request_ip,
        user_agent=user_agent,
    )
    session.add(ds)
    await session.flush()
    return ds, token, csrf_token


async def find_session_by_token(
    session: AsyncSession,
    token: str,
) -> DashboardSession | None:
    """Look up a session by plain token (hashes for lookup).

    Returns None if not found, expired, revoked, or user disabled.
    """
    result = await session.execute(
        select(DashboardSession).where(
            DashboardSession.session_hash == _hash_token(token),
            DashboardSession.revoked_at.is_(None),
            DashboardSession.expires_at > datetime.now(UTC),
            DashboardSession.idle_expires_at > datetime.now(UTC),
        )
    )
    ds = result.scalar_one_or_none()
    if ds is None:
        return None

    user_result = await session.execute(
        select(User).where(User.id == ds.user_id)
    )
    user = user_result.scalar_one_or_none()
    if user is None or user.is_disabled:
        return None

    return ds


async def rotate_session(
    session: AsyncSession,
    old_session: DashboardSession,
    reason: str = "session_rotated",
    request_ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[DashboardSession, str, str]:
    """Revoke old session and create a new one for the same user.

    Returns (new_session, new_token, new_csrf_token).
    """
    now = datetime.now(UTC)

    await session.execute(
        update(DashboardSession)
        .where(DashboardSession.id == old_session.id)
        .values(revoked_at=now, revoked_reason=reason)
    )

    user_result = await session.execute(
        select(User).where(User.id == old_session.user_id)
    )
    user = user_result.scalar_one()

    absolute, idle = _session_lifetime(user)
    token = _generate_token()
    csrf_token = secrets.token_urlsafe(32)

    new_ds = DashboardSession(
        id=uuid.uuid4(),
        user_id=user.id,
        session_hash=_hash_token(token),
        csrf_hash=_hash_token(csrf_token),
        expires_at=now + absolute,
        idle_expires_at=now + idle,
        request_ip=request_ip,
        user_agent=user_agent,
        rotated_at=now,
    )
    session.add(new_ds)
    await session.flush()
    return new_ds, token, csrf_token


async def revoke_session(
    session: AsyncSession,
    ds: DashboardSession,
    reason: str = "logout",
) -> None:
    """Revoke a single session."""
    ds.revoked_at = datetime.now(UTC)
    ds.revoked_reason = reason
    await session.flush()


async def revoke_all_sessions(
    session: AsyncSession,
    user_id: uuid.UUID,
    reason: str = "user_disabled",
) -> int:
    """Revoke all active sessions for a user. Returns count."""
    now = datetime.now(UTC)
    result = await session.execute(
        update(DashboardSession)
        .where(
            DashboardSession.user_id == user_id,
            DashboardSession.revoked_at.is_(None),
        )
        .values(revoked_at=now, revoked_reason=reason)
    )
    await session.flush()
    return result.rowcount


async def update_last_seen(
    session: AsyncSession,
    ds: DashboardSession,
) -> None:
    """Update last_seen_at, throttled to avoid write amplification."""
    if ds.last_seen_at is None or (
        datetime.now(UTC) - ds.last_seen_at > timedelta(seconds=60)
    ):
        ds.last_seen_at = datetime.now(UTC)
        settings = get_settings()
        is_admin = ds.user.role in (UserRole.ADMIN, UserRole.SUPER_ADMIN)
        idle_hours = settings.session_admin_idle_hours if is_admin else settings.session_user_idle_hours
        ds.idle_expires_at = ds.last_seen_at + timedelta(hours=idle_hours)
        await session.flush()


async def set_step_up(
    session: AsyncSession,
    ds: DashboardSession,
) -> None:
    """Mark session as step-up verified."""
    settings = get_settings()
    ds.step_up_until = datetime.now(UTC) + timedelta(
        minutes=settings.session_step_up_duration_minutes
    )
    await session.flush()


async def get_session_info(
    session: AsyncSession,
    ds: DashboardSession,
) -> dict[str, Any]:
    """Return safe session info for /me response."""
    user_result = await session.execute(
        select(User).where(User.id == ds.user_id)
    )
    user = user_result.scalar_one()

    permissions: list[str] = []
    if user.role in (UserRole.ADMIN, UserRole.SUPER_ADMIN):
        permissions.extend([
            "admin:read",
            "admin:cancel_pending_tasks",
        ])
    if user.role == UserRole.SUPER_ADMIN:
        permissions.extend([
            "super_admin:disable_user",
            "super_admin:disable_agent",
            "super_admin:cancel_running_tasks",
            "super_admin:export_audit",
        ])

    return {
        "user_id": str(user.id),
        "username": user.username,
        "role": user.role,
        "permissions": permissions,
        "csrf_required": True,
        "session_expires_at": ds.expires_at,
        "step_up_until": ds.step_up_until,
    }
