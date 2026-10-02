"""Dedicated channel transport: route_type=dedicated_channel.

M3: consumes DedicatedChannel.connection_config (endpoint / protocol) as
the carrier for the final delivery hop.

The channel record is resolved from the agent pair (source -> target) via
dedicated_channel_service.select_dedicated_channel, which is the same
selection the path optimizer used to choose this route — the transport
re-resolves instead of trusting a stale channel id, so a channel disabled
between route selection and delivery fails closed instead of sending over
a dead link.

Because the platform's data plane is the WebSocket bus, the channel
transport terminates on the target agent's connection (local or
cross-node): the validated endpoint/protocol are recorded on the delivery
event, then dedicated_channel_service.deliver_via_dedicated_channel (the
selection -> execution bridge) performs the final hop.
"""

from __future__ import annotations

import logging
import time
import uuid

from app.transports.base import DeliveryResult, Transport, FAILED

logger = logging.getLogger(__name__)


class ChannelTransport(Transport):
    """Deliver over a dedicated channel between two agents."""

    def __init__(self, manager=None):
        self._manager = manager

    async def deliver(
        self,
        *,
        agent_id: uuid.UUID,
        message: str,
        message_id: str,
        task_id: uuid.UUID | None = None,
        source_agent_id: uuid.UUID | None = None,
        relay_node_id: uuid.UUID | None = None,
        track_pending: bool = True,
    ) -> DeliveryResult:
        start = time.perf_counter()

        # Resolve the dedicated channel for this agent pair. Without a
        # source agent we cannot identify a channel, so fail closed.
        if source_agent_id is None:
            return DeliveryResult(
                outcome=FAILED,
                error_code="CHANNEL_SOURCE_UNKNOWN",
                error_message="Dedicated channel transport needs the source agent",
            )

        from app.database import SessionLocal
        from app.services.dedicated_channel_service import (
            deliver_via_dedicated_channel,
            select_dedicated_channel,
        )

        async with SessionLocal() as session:
            try:
                channel = await select_dedicated_channel(
                    session,
                    source_agent_id=source_agent_id,
                    target_agent_id=agent_id,
                )
            except Exception as exc:
                logger.warning(
                    "Dedicated channel resolution failed for message %s: %s",
                    message_id,
                    exc,
                )
                return DeliveryResult(
                    outcome=FAILED,
                    error_code="CHANNEL_RESOLUTION_FAILED",
                    error_message=str(exc),
                )

            if channel is None:
                return DeliveryResult(
                    outcome=FAILED,
                    error_code="NO_HEALTHY_CHANNEL",
                    error_message="No healthy dedicated channel available",
                )

        # Hand the SELECTED channel to the channel transport executor.
        result = await deliver_via_dedicated_channel(
            channel,
            agent_id=agent_id,
            message=message,
            message_id=message_id,
            task_id=task_id,
            source_agent_id=source_agent_id,
            manager=self._manager,
        )
        result.latency_ms = int((time.perf_counter() - start) * 1000)
        return result
