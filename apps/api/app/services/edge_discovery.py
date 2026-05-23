"""Edge Discovery Service: manage personal edge relays and local network detection."""

import ipaddress
import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DomainException
from app.models.relay_node import RelayNode
from app.protocol.constants import ErrorCode

logger = logging.getLogger(__name__)


async def register_personal_edge_relay(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    node_name: str,
    local_ip: str | None = None,
    subnet: str | None = None,
    gateway: str | None = None,
    capabilities: list[str] | None = None,
    max_capacity: int | None = None,
) -> RelayNode:
    """Register a personal edge relay for a user.

    Args:
        session: Database session
        user_id: User ID (for node naming uniqueness)
        node_name: Human-readable node name
        local_ip: Local IP address of the relay
        subnet: Subnet CIDR (e.g., "192.168.1.0/24")
        gateway: Gateway IP address
        capabilities: List of capabilities
        max_capacity: Maximum capacity

    Returns:
        RelayNode instance

    Raises:
        DomainException: If node_name already exists
    """
    # Check if node_name already exists
    result = await session.execute(
        select(RelayNode).where(RelayNode.node_name == node_name)
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise DomainException(
            ErrorCode.INVALID_REQUEST,
            f"Edge relay with name '{node_name}' already exists",
        )

    # Build network_info
    network_info = {}
    if local_ip:
        network_info["local_ip"] = local_ip
    if subnet:
        # Validate subnet format
        try:
            ipaddress.ip_network(subnet, strict=False)
            network_info["subnet"] = subnet
        except ValueError as e:
            raise DomainException(
                ErrorCode.INVALID_REQUEST,
                f"Invalid subnet format: {e}",
            )
    if gateway:
        network_info["gateway"] = gateway

    # Create relay node
    relay = RelayNode(
        node_name=node_name,
        node_type="personal_edge",
        status="healthy",
        current_load=0.0,
        queue_depth=0,
        capabilities=capabilities or ["websocket", "task_delivery"],
        max_capacity=max_capacity or 100,
        network_info=network_info,
        enabled=True,
        last_heartbeat_at=datetime.now(UTC),
        extra_metadata={"user_id": str(user_id)},
    )
    session.add(relay)
    await session.flush()

    logger.info(
        "Registered personal edge relay: node=%s user=%s subnet=%s",
        node_name,
        user_id,
        subnet,
    )

    return relay


async def process_edge_heartbeat(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    node_name: str,
    current_load: float = 0.0,
    queue_depth: int = 0,
    avg_latency_ms: float | None = None,
    success_rate: float | None = None,
) -> RelayNode:
    """Process heartbeat from personal edge relay.

    Args:
        session: Database session
        user_id: User ID (for ownership verification)
        node_name: Node name
        current_load: Current load (0.0-1.0)
        queue_depth: Queue depth
        avg_latency_ms: Average latency in milliseconds
        success_rate: Success rate (0.0-1.0)

    Returns:
        Updated RelayNode

    Raises:
        DomainException: If relay not found or not owned by user
    """
    result = await session.execute(
        select(RelayNode).where(
            RelayNode.node_name == node_name,
            RelayNode.node_type == "personal_edge",
        )
    )
    relay = result.scalar_one_or_none()
    if not relay:
        raise DomainException(
            ErrorCode.INVALID_REQUEST,
            f"Personal edge relay '{node_name}' not found",
        )

    # Verify ownership
    relay_user_id = relay.extra_metadata.get("user_id")
    if relay_user_id != str(user_id):
        raise DomainException(
            ErrorCode.INVALID_REQUEST,
            f"Personal edge relay '{node_name}' not owned by current user",
            status_code=403,
        )

    # Update metrics
    relay.current_load = current_load
    relay.queue_depth = queue_depth
    if avg_latency_ms is not None:
        relay.avg_latency_ms = avg_latency_ms
    if success_rate is not None:
        relay.success_rate = success_rate
    relay.last_heartbeat_at = datetime.now(UTC)

    # Update status based on health
    if relay.is_healthy:
        relay.status = "healthy"
    else:
        relay.status = "degraded"

    await session.flush()

    logger.debug(
        "Edge heartbeat: node=%s load=%.2f queue=%d status=%s",
        node_name,
        current_load,
        queue_depth,
        relay.status,
    )

    return relay


async def get_personal_edge_relays(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    only_healthy: bool = False,
) -> list[RelayNode]:
    """Get all personal edge relays for a user.

    Args:
        session: Database session
        user_id: User ID
        only_healthy: Only return healthy relays

    Returns:
        List of RelayNode instances
    """
    query = select(RelayNode).where(
        RelayNode.node_type == "personal_edge",
        RelayNode.enabled == True,  # noqa: E712
    )

    if only_healthy:
        query = query.where(
            RelayNode.status.in_(["healthy", "degraded"]),
        )

    result = await session.execute(query)
    relays = list(result.scalars().all())

    # Filter by user_id in metadata
    user_relays = [
        r for r in relays
        if r.extra_metadata.get("user_id") == str(user_id)
    ]

    return user_relays


async def check_local_network_match(
    client_network_info: dict,
    relay: RelayNode,
) -> bool:
    """Check if client and relay are on the same local network.

    Args:
        client_network_info: Client network info (subnet, local_ip, gateway)
        relay: RelayNode to check

    Returns:
        True if on same network, False otherwise
    """
    if not relay.network_info:
        return False

    client_subnet = client_network_info.get("subnet")
    relay_subnet = relay.network_info.get("subnet")

    # Simple subnet match
    if client_subnet and relay_subnet:
        return client_subnet == relay_subnet

    # Fallback: check if gateway matches
    client_gateway = client_network_info.get("gateway")
    relay_gateway = relay.network_info.get("gateway")
    if client_gateway and relay_gateway:
        return client_gateway == relay_gateway

    return False


async def cleanup_stale_edge_relays(
    session: AsyncSession,
    stale_threshold_minutes: int = 5,
) -> int:
    """Mark edge relays as down if they haven't sent heartbeat recently.

    Args:
        session: Database session
        stale_threshold_minutes: Minutes without heartbeat to consider stale

    Returns:
        Number of relays marked as down
    """
    threshold = datetime.now(UTC) - timedelta(minutes=stale_threshold_minutes)

    result = await session.execute(
        select(RelayNode).where(
            RelayNode.node_type == "personal_edge",
            RelayNode.status.in_(["healthy", "degraded"]),
            RelayNode.last_heartbeat_at < threshold,
        )
    )
    stale_relays = list(result.scalars().all())

    for relay in stale_relays:
        relay.status = "down"
        logger.warning(
            "Marked edge relay as down due to stale heartbeat: node=%s last_heartbeat=%s",
            relay.node_name,
            relay.last_heartbeat_at,
        )

    if stale_relays:
        await session.flush()

    return len(stale_relays)
