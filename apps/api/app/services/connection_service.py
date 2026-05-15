"""Connection service: policy enforcement, security mode negotiation, CRUD."""

import logging
from datetime import UTC, datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DomainException
from app.models.agent import Agent
from app.models.connection import Connection
from app.protocol.constants import ErrorCode, InboundPolicy, SecurityMode

logger = logging.getLogger(__name__)


def negotiate_security_mode(
    requested_modes: list[str],
    supported_modes: list[str],
) -> str:
    """Find the highest-priority intersecting security mode.

    MVP only supports relay_visible; e2ee is reserved.
    Raises SECURITY_MODE_NOT_SUPPORTED if no intersection.
    """
    requested = set(requested_modes)
    supported = set(supported_modes)
    intersection = requested & supported

    if not intersection:
        raise DomainException(
            ErrorCode.SECURITY_MODE_NOT_SUPPORTED,
            "No compatible security mode between sender and receiver.",
            status_code=400,
            details={"requested": sorted(requested), "supported": sorted(supported)},
        )

    # Priority: e2ee > relay_encrypted > relay_visible
    priority = [SecurityMode.E2EE.value, SecurityMode.RELAY_ENCRYPTED.value, SecurityMode.RELAY_VISIBLE.value]
    for mode in priority:
        if mode in intersection:
            return mode

    return sorted(intersection)[0]


async def enforce_policy(
    session: AsyncSession,
    from_agent: Agent,
    to_agent: Agent,
    requested_security_modes: list[str] | None = None,
) -> Connection | None:
    """Enforce the receiver's inbound_policy against the sender.

    Same-owner agents can always communicate regardless of policy.
    For cross-user communication, policy determines the flow.

    Returns an existing active Connection if policy requires one, or None if
    access is auto-allowed. Raises DomainException for blocked/needs_approval cases.
    """
    policy = to_agent.inbound_policy

    # Same owner: always allow
    if from_agent.owner_id == to_agent.owner_id:
        return None

    if policy == InboundPolicy.PRIVATE.value:
        raise DomainException(
            ErrorCode.AGENT_FORBIDDEN,
            f"Agent {to_agent.agent_number} is private and does not accept external requests.",
            status_code=403,
        )

    if policy == InboundPolicy.CONTACTS_ONLY.value:
        existing = await _find_active_connection(session, from_agent.id, to_agent.id)
        if existing is None:
            raise DomainException(
                ErrorCode.CONNECTION_APPROVAL_REQUIRED,
                f"Agent {to_agent.agent_number} only accepts requests from authorized contacts.",
                status_code=403,
            )
        return existing

    if policy == InboundPolicy.REQUEST_APPROVAL.value:
        existing = await _find_active_connection(session, from_agent.id, to_agent.id)
        if existing:
            return existing
        # Check if connection was previously rejected
        rejected = await _find_rejected_connection(session, from_agent.id, to_agent.id)
        if rejected:
            raise DomainException(
                ErrorCode.CONNECTION_REJECTED,
                f"Connection to {to_agent.agent_number} was previously rejected.",
                status_code=403,
                details={"connection_id": str(rejected.id)},
            )
        # Check if there's already a pending request
        pending = await _find_pending_request(session, from_agent.id, to_agent.id)
        if pending:
            raise DomainException(
                ErrorCode.CONNECTION_APPROVAL_REQUIRED,
                f"Connection request to {to_agent.agent_number} is pending approval.",
                status_code=202,
                details={"connection_id": str(pending.id)},
            )
        # Create a new connection.request
        conn = await create_connection_request(
            session, from_agent, to_agent,
            requested_security_modes=requested_security_modes or [],
        )
        raise DomainException(
            ErrorCode.CONNECTION_APPROVAL_REQUIRED,
            f"Connection request sent to {to_agent.agent_number}. Awaiting approval.",
            status_code=202,
            details={"connection_id": str(conn.id)},
        )

    if policy == InboundPolicy.PUBLIC.value:
        return None

    raise DomainException(
        ErrorCode.INTERNAL_ERROR,
        f"Unknown inbound policy: {policy}",
        status_code=500,
    )


async def create_connection_request(
    session: AsyncSession,
    from_agent: Agent,
    to_agent: Agent,
    *,
    reason: str | None = None,
    requested_capabilities: list[str] | None = None,
    requested_security_modes: list[str] | None = None,
) -> Connection:
    """Create a pending connection request."""
    preferred_mode = None
    if requested_security_modes:
        security_modes = [SecurityMode.RELAY_VISIBLE.value]
        preferred_mode = negotiate_security_mode(requested_security_modes, security_modes)

    conn = Connection(
        from_agent_id=from_agent.id,
        to_agent_id=to_agent.id,
        status="pending",
        reason=reason,
        allowed_capabilities=requested_capabilities,
        preferred_security_mode=preferred_mode,
    )
    session.add(conn)

    # Commit immediately so the connection persists even if the
    # caller raises (e.g., enforce_policy raises CONNECTION_APPROVAL_REQUIRED).
    await session.commit()
    await session.refresh(conn)

    # Audit: connection request created
    from app.services.audit_service import write_audit
    await write_audit(
        session,
        actor_type="agent",
        actor_id=str(from_agent.id),
        action="connection.requested",
        resource_type="connection",
        resource_id=str(conn.id),
        details={"to_agent": to_agent.agent_number, "security_mode": preferred_mode},
    )

    logger.info(
        "Connection request created: %s from %s to %s",
        conn.id, from_agent.agent_number, to_agent.agent_number,
    )
    return conn


async def accept_connection(
    session: AsyncSession,
    connection_id: str,
    *,
    allowed_capabilities: list[str] | None = None,
    preferred_security_mode: str | None = None,
    expires_at: datetime | None = None,
) -> Connection:
    """Accept a pending connection request."""
    conn = await get_connection(session, connection_id)
    if conn.status != "pending":
        raise DomainException(
            ErrorCode.INTERNAL_ERROR,
            f"Connection {connection_id} is not in pending state (current: {conn.status})",
            status_code=409,
        )

    conn.status = "accepted"
    if allowed_capabilities is not None:
        conn.allowed_capabilities = allowed_capabilities
    if preferred_security_mode is not None:
        conn.preferred_security_mode = preferred_security_mode
    if expires_at is not None:
        conn.expires_at = expires_at

    await session.commit()
    await session.refresh(conn)

    # Audit: connection accepted
    from app.services.audit_service import write_audit
    await write_audit(
        session,
        actor_type="agent",
        actor_id=str(conn.to_agent_id),
        action="connection.accepted",
        resource_type="connection",
        resource_id=str(conn.id),
    )

    logger.info("Connection %s accepted", connection_id)
    return conn


async def reject_connection(
    session: AsyncSession,
    connection_id: str,
    *,
    reason: str | None = None,
) -> Connection:
    """Reject a pending connection request."""
    conn = await get_connection(session, connection_id)
    if conn.status != "pending":
        raise DomainException(
            ErrorCode.INTERNAL_ERROR,
            f"Connection {connection_id} is not in pending state (current: {conn.status})",
            status_code=409,
        )

    conn.status = "rejected"
    if reason:
        conn.reason = reason

    await session.commit()
    await session.refresh(conn)

    # Audit: connection rejected
    from app.services.audit_service import write_audit
    await write_audit(
        session,
        actor_type="agent",
        actor_id=str(conn.to_agent_id),
        action="connection.rejected",
        resource_type="connection",
        resource_id=str(conn.id),
        details={"reason": reason} if reason else None,
    )

    logger.info("Connection %s rejected", connection_id)
    return conn


async def list_connections(
    session: AsyncSession,
    agent_id: str,
    status: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[Connection], int]:
    """List connections for an agent (inbound + outbound)."""
    from uuid import UUID
    agent_uuid = UUID(agent_id)

    stmt = select(Connection).where(
        (Connection.from_agent_id == agent_uuid) | (Connection.to_agent_id == agent_uuid)
    )
    if status:
        stmt = stmt.where(Connection.status == status)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(Connection.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def _find_active_connection(
    session: AsyncSession, from_agent_id, to_agent_id
) -> Connection | None:
    """Find an accepted, non-expired connection between two agents."""
    now = datetime.now(UTC)
    result = await session.execute(
        select(Connection).where(
            Connection.from_agent_id == from_agent_id,
            Connection.to_agent_id == to_agent_id,
            Connection.status == "accepted",
            (Connection.expires_at.is_(None) | (Connection.expires_at > now)),
        )
    )
    return result.scalar_one_or_none()


async def _find_rejected_connection(
    session: AsyncSession, from_agent_id, to_agent_id
) -> Connection | None:
    """Find the most recent rejected connection between two agents."""
    result = await session.execute(
        select(Connection).where(
            Connection.from_agent_id == from_agent_id,
            Connection.to_agent_id == to_agent_id,
            Connection.status == "rejected",
        ).order_by(Connection.created_at.desc()).limit(1)
    )
    return result.scalar_one_or_none()


async def _find_pending_request(
    session: AsyncSession, from_agent_id, to_agent_id
) -> Connection | None:
    """Find a pending connection request."""
    result = await session.execute(
        select(Connection).where(
            Connection.from_agent_id == from_agent_id,
            Connection.to_agent_id == to_agent_id,
            Connection.status == "pending",
        )
    )
    return result.scalar_one_or_none()


async def get_connection(session: AsyncSession, connection_id: str) -> Connection:
    """Get a connection by ID or raise."""
    from uuid import UUID
    result = await session.execute(
        select(Connection).where(Connection.id == UUID(connection_id))
    )
    conn = result.scalar_one_or_none()
    if conn is None:
        raise DomainException(
            ErrorCode.INTERNAL_ERROR,
            f"Connection {connection_id} not found",
            status_code=404,
        )
    return conn
