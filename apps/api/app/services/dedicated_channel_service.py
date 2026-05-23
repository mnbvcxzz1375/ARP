"""Dedicated Channel service: manages dedicated network channels between agents.

Phase 17: Dedicated channels provide direct, high-performance connections
between agents, bypassing the relay infrastructure when available.
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DomainException
from app.models.agent import Agent
from app.models.channel_health_check import ChannelHealthCheck
from app.models.dedicated_channel import DedicatedChannel
from app.protocol.constants import ErrorCode

logger = logging.getLogger(__name__)


async def create_dedicated_channel(
    session: AsyncSession,
    *,
    scope_id: uuid.UUID | None,
    channel_name: str,
    channel_type: str,
    source_agent_id: uuid.UUID,
    target_agent_id: uuid.UUID,
    connection_config: dict,
    encryption_config: dict,
    bandwidth_mbps: float | None = None,
    latency_target_ms: float | None = None,
) -> DedicatedChannel:
    """Create a new dedicated channel between two agents.

    Args:
        session: Database session
        scope_id: Network scope ID (optional)
        channel_name: Human-readable channel name
        channel_type: Channel type (vpn, private_link, p2p, direct_connect)
        source_agent_id: Source agent ID
        target_agent_id: Target agent ID
        connection_config: Connection configuration (endpoint, protocol, etc.)
        encryption_config: Encryption configuration (algorithm, key rotation, etc.)
        bandwidth_mbps: Target bandwidth in Mbps
        latency_target_ms: Target latency in milliseconds

    Returns:
        Created DedicatedChannel

    Raises:
        DomainException: If validation fails
    """
    # Validate channel type
    valid_types = ["vpn", "private_link", "p2p", "direct_connect"]
    if channel_type not in valid_types:
        raise DomainException(
            ErrorCode.INVALID_REQUEST,
            f"Invalid channel_type: {channel_type}. Must be one of {valid_types}",
        )

    # Validate agents exist
    source_agent = await session.get(Agent, source_agent_id)
    if not source_agent:
        raise DomainException(ErrorCode.INVALID_REQUEST, f"Source agent {source_agent_id} not found")

    target_agent = await session.get(Agent, target_agent_id)
    if not target_agent:
        raise DomainException(ErrorCode.INVALID_REQUEST, f"Target agent {target_agent_id} not found")

    # Create channel
    channel = DedicatedChannel(
        scope_id=scope_id,
        channel_name=channel_name,
        channel_type=channel_type,
        source_agent_id=source_agent_id,
        target_agent_id=target_agent_id,
        connection_config=connection_config,
        encryption_config=encryption_config,
        bandwidth_mbps=bandwidth_mbps,
        latency_target_ms=latency_target_ms,
        enabled=True,
    )
    session.add(channel)
    await session.flush()

    logger.info(
        "Created dedicated channel: id=%s name=%s type=%s source=%s target=%s",
        channel.id,
        channel_name,
        channel_type,
        source_agent.agent_number,
        target_agent.agent_number,
    )

    return channel


async def verify_channel_health(
    session: AsyncSession,
    channel_id: uuid.UUID,
) -> ChannelHealthCheck:
    """Perform health check on a dedicated channel.

    This function reads the control-plane reported health status from the
    channel's connection_config[\"health_check\"] field. It does NOT perform
    network-level probing or assume enabled=True means healthy.

    When no explicit health_check report is present, the channel is
    considered down (fail-closed). A disabled channel is always \"down\".

    Args:
        session: Database session
        channel_id: Channel ID to check

    Returns:
        ChannelHealthCheck record

    Raises:
        DomainException: If channel not found
    """
    channel = await session.get(DedicatedChannel, channel_id)
    if not channel:
        raise DomainException(ErrorCode.INVALID_REQUEST, f"Channel {channel_id} not found")

    if not channel.enabled:
        status = "down"
        latency_ms = None
        packet_loss_percent = None
        bandwidth_mbps = None
        error_message = "Channel is disabled"
    else:
        # Read health report from connection_config (control-plane reported, not simulated)
        health_report = channel.connection_config.get("health_check")
        if not health_report or not isinstance(health_report, dict):
            status = "down"
            latency_ms = None
            packet_loss_percent = None
            bandwidth_mbps = None
            error_message = "Dedicated channel health_check is missing or invalid"
        else:
            raw_status = health_report.get("status")
            valid_statuses = {"healthy", "down", "degraded"}
            if raw_status not in valid_statuses:
                status = "down"
                latency_ms = None
                packet_loss_percent = None
                bandwidth_mbps = None
                error_message = "Dedicated channel health_check is missing or invalid"
            else:
                status = raw_status
                latency_ms = health_report.get("latency_ms")
                packet_loss_percent = health_report.get("packet_loss_percent")
                bandwidth_mbps = health_report.get("bandwidth_mbps")
                error_message = health_report.get("error_message")

    # Create health check record
    health_check = ChannelHealthCheck(
        channel_id=channel_id,
        check_time=datetime.now(UTC),
        latency_ms=latency_ms,
        packet_loss_percent=packet_loss_percent,
        bandwidth_mbps=bandwidth_mbps,
        status=status,
        error_message=error_message,
    )
    session.add(health_check)
    await session.flush()

    logger.info(
        "Channel health check: channel=%s status=%s latency=%s",
        channel_id,
        status,
        f"{latency_ms:.1f}ms" if latency_ms is not None else "N/A",
    )

    return health_check


async def select_dedicated_channel(
    session: AsyncSession,
    source_agent_id: uuid.UUID,
    target_agent_id: uuid.UUID,
) -> DedicatedChannel | None:
    """Select the best available dedicated channel for an agent pair.

    Priority order:
    1. Enabled channels only
    2. Healthy channels (based on recent health checks)
    3. Lowest latency

    Args:
        session: Database session
        source_agent_id: Source agent ID
        target_agent_id: Target agent ID

    Returns:
        Best available DedicatedChannel, or None if no healthy channel exists

    Raises:
        DomainException: If database query fails
    """
    try:
        # Query all enabled channels for this agent pair
        result = await session.execute(
            select(DedicatedChannel)
            .where(
                DedicatedChannel.source_agent_id == source_agent_id,
                DedicatedChannel.target_agent_id == target_agent_id,
                DedicatedChannel.enabled == True,  # noqa: E712
            )
        )
        channels = list(result.scalars().all())
    except Exception as e:
        logger.error(
            "Database error querying dedicated channels: source=%s target=%s error=%s",
            source_agent_id,
            target_agent_id,
            e,
            exc_info=True,
        )
        raise DomainException(
            ErrorCode.INTERNAL_ERROR,
            f"Failed to query dedicated channels: {e}",
            status_code=503,
        )

    if not channels:
        return None

    # Filter to healthy channels only
    healthy_channels = []
    for channel in channels:
        try:
            # Get most recent health check
            health_result = await session.execute(
                select(ChannelHealthCheck)
                .where(ChannelHealthCheck.channel_id == channel.id)
                .order_by(ChannelHealthCheck.check_time.desc())
                .limit(1)
            )
            latest_check = health_result.scalar_one_or_none()

            # Only include channels with recent healthy status
            # enabled=True does NOT mean healthy - must check health records
            if latest_check and latest_check.status == "healthy":
                healthy_channels.append((channel, latest_check))
            else:
                logger.debug(
                    "Skipping channel %s: no health check or not healthy (status=%s)",
                    channel.id,
                    latest_check.status if latest_check else "no_check",
                )
        except Exception as e:
            logger.error(
                "Database error checking health for channel %s: %s",
                channel.id,
                e,
                exc_info=True,
            )
            raise DomainException(
                ErrorCode.INTERNAL_ERROR,
                f"Failed to check health for channel {channel.id}: {e}",
                status_code=503,
            )

    if not healthy_channels:
        logger.info(
            "No healthy dedicated channels for source=%s target=%s (found %d enabled channels)",
            source_agent_id,
            target_agent_id,
            len(channels),
        )
        return None

    # Select channel with lowest latency
    best_channel, best_check = min(healthy_channels, key=lambda x: x[1].latency_ms or 999.0)

    logger.info(
        "Selected dedicated channel: id=%s type=%s latency=%.1fms",
        best_channel.id,
        best_channel.channel_type,
        best_check.latency_ms or 0.0,
    )

    return best_channel


async def fallback_to_relay(
    session: AsyncSession,
    channel_id: uuid.UUID,
    reason: str,
) -> None:
    """Record fallback to relay when dedicated channel is unavailable.

    This function logs an audit event when a dedicated channel fails
    and routing falls back to relay infrastructure.

    Args:
        session: Database session
        channel_id: Channel ID that failed
        reason: Reason for fallback
    """
    from app.services.audit_service import write_audit

    channel = await session.get(DedicatedChannel, channel_id)
    if not channel:
        logger.warning("Fallback to relay: channel %s not found", channel_id)
        return

    await write_audit(
        session,
        actor_type="system",
        actor_id="system",
        action="fallback_to_relay",
        resource_type="dedicated_channel",
        resource_id=str(channel_id),
        details={
            "channel_name": channel.channel_name,
            "channel_type": channel.channel_type,
            "source_agent_id": str(channel.source_agent_id),
            "target_agent_id": str(channel.target_agent_id),
            "reason": reason,
        },
    )

    logger.warning(
        "Dedicated channel fallback to relay: channel=%s reason=%s",
        channel_id,
        reason,
    )
