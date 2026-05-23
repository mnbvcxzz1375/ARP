"""Route lease management service."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.route_lease import RouteLease
from app.models.task import Task


async def issue_route_lease(
    session: AsyncSession,
    *,
    source_agent_id: uuid.UUID,
    target_agent_id: uuid.UUID,
    route_type: str,
    duration_seconds: int = 3600,
    max_messages: int | None = None,
    max_bytes: int | None = None,
    allowed_task_types: list[str] | None = None,
    approval_id: uuid.UUID | None = None,
) -> RouteLease:
    """Issue a new route lease, revoking any existing active lease for the same pair.

    Ensures at most one active (non-expired, non-revoked) lease per
    (source, target, route_type) so verify_route_lease never matches
    multiple rows.
    """
    now = datetime.now(UTC)

    # Auto-revoke any existing active lease for the same (source, target, route_type).
    existing = await session.execute(
        select(RouteLease).where(
            RouteLease.source_agent_id == source_agent_id,
            RouteLease.target_agent_id == target_agent_id,
            RouteLease.route_type == route_type,
            RouteLease.expires_at > now,
            RouteLease.revoked_at.is_(None),
        )
    )
    for old in existing.scalars().all():
        old.revoked_at = now
        old.revoke_reason = "superseded"

    lease = RouteLease(
        source_agent_id=source_agent_id,
        target_agent_id=target_agent_id,
        route_type=route_type,
        expires_at=now + timedelta(seconds=duration_seconds),
        max_messages=max_messages,
        max_bytes=max_bytes,
        allowed_task_types=allowed_task_types,
        approval_id=approval_id,
        messages_sent=0,
        bytes_sent=0,
    )
    session.add(lease)
    await session.flush()
    return lease


async def verify_route_lease(
    session: AsyncSession,
    *,
    source_agent_id: uuid.UUID,
    target_agent_id: uuid.UUID,
    route_type: str,
    task: Task,
    message_size_bytes: int,
    lease_id: uuid.UUID | None = None,
) -> RouteLease | None:
    """Verify if a valid route lease exists for the given route.

    Args:
        session: Database session
        source_agent_id: Source agent ID
        target_agent_id: Target agent ID
        route_type: Route type
        task: Task being delivered
        message_size_bytes: Message size in bytes
        lease_id: If provided, verify a specific lease by ID.

    Returns:
        Valid RouteLease if found, None otherwise
    """
    now = datetime.now(UTC)

    stmt = select(RouteLease).where(
        RouteLease.source_agent_id == source_agent_id,
        RouteLease.target_agent_id == target_agent_id,
        RouteLease.route_type == route_type,
        RouteLease.expires_at > now,
        RouteLease.revoked_at.is_(None),
    )
    if lease_id is not None:
        stmt = stmt.where(RouteLease.id == lease_id)
    else:
        stmt = stmt.order_by(RouteLease.created_at.desc()).limit(1)

    result = await session.execute(stmt)
    lease = result.scalar_one_or_none()

    if not lease:
        return None

    # Check message count limit
    if lease.max_messages is not None and lease.messages_sent >= lease.max_messages:
        return None

    # Check byte limit
    if lease.max_bytes is not None and lease.bytes_sent + message_size_bytes > lease.max_bytes:
        return None

    # Task type restriction: use task.route_policy_hint as the task type source.
    # allowed_task_types=None means unrestricted (all types allowed).
    if lease.allowed_task_types is not None:
        task_type = task.route_policy_hint
        if not task_type or task_type not in lease.allowed_task_types:
            return None

    return lease


async def consume_route_lease(
    session: AsyncSession,
    *,
    lease: RouteLease,
    message_size_bytes: int,
) -> None:
    """Consume lease quota after successful delivery.

    Args:
        session: Database session
        lease: Route lease to consume
        message_size_bytes: Message size in bytes
    """
    lease.messages_sent += 1
    lease.bytes_sent += message_size_bytes
    await session.flush()


async def revoke_route_lease(
    session: AsyncSession,
    *,
    lease_id: uuid.UUID,
    reason: str,
) -> RouteLease | None:
    """Revoke a route lease.

    Args:
        session: Database session
        lease_id: Lease ID to revoke
        reason: Revocation reason

    Returns:
        Revoked RouteLease if found, None otherwise
    """
    result = await session.execute(select(RouteLease).where(RouteLease.id == lease_id))
    lease = result.scalar_one_or_none()

    if not lease or lease.revoked_at is not None:
        return None

    lease.revoked_at = datetime.now(UTC)
    lease.revoke_reason = reason
    await session.flush()
    return lease


async def cleanup_expired_leases(session: AsyncSession) -> int:
    """Clean up expired route leases (soft delete by marking revoked).

    Args:
        session: Database session

    Returns:
        Number of leases cleaned up
    """
    now = datetime.now(UTC)

    result = await session.execute(
        select(RouteLease).where(
            RouteLease.expires_at <= now,
            RouteLease.revoked_at.is_(None),
        )
    )
    expired_leases = result.scalars().all()

    count = 0
    for lease in expired_leases:
        lease.revoked_at = now
        lease.revoke_reason = "expired"
        count += 1

    if count > 0:
        await session.flush()

    return count
