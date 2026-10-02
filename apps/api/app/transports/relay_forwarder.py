"""Relay forwarder transport: personal_edge / regional_relay route types.

M3: models the receive → lookup → forward dataplane of a relay node.

1. RECEIVE: the message arrives at the relay (this deliver() call).
2. HEARTBEAT: the relay refreshes its own health by really invoking the
   relay heartbeat endpoint (app.routers.routing: relay_node_heartbeat),
   so last_heartbeat_at / status / load stay current in the database —
   exactly the endpoint a deployed relay node would call.
3. LOOKUP: resolve where the target agent currently lives (local
   connection or, via the presence key, another node).
4. FORWARD: hand the bytes to the central transport for the final hop,
   which publishes cross-node when the agent is elsewhere.

Relay-specific delivery events (relay_forwarded) are recorded here so the
acceptance chain route_selected → relay_forwarded → delivered is visible
in message_delivery_events.
"""

from __future__ import annotations

import logging
import time
import uuid

from app.transports.base import (
    DeliveryResult,
    Transport,
)
from app.transports.central import CentralTransport

logger = logging.getLogger(__name__)


class RelayForwarder(Transport):
    """Forward through a personal_edge / regional relay node."""

    def __init__(self, manager=None, central: CentralTransport | None = None):
        self._manager = manager
        self._central = central

    def _central_transport(self) -> CentralTransport:
        if self._central is not None:
            return self._central
        return CentralTransport(manager=self._manager)

    async def refresh_relay_health(self, relay_node_id: uuid.UUID) -> None:
        """Refresh the relay node's heartbeat via the real routing endpoint.

        Calls app.routers.routing.relay_node_heartbeat with a dedicated
        session instead of hand-writing the UPDATE, so the relay dataplane
        and the control plane share one heartbeat code path (60s health
        window used by continuity_service.check_relay_health and
        path_optimizer._get_healthy_relays).
        """
        from app.database import SessionLocal
        from app.routers.routing import relay_node_heartbeat
        from app.schemas.routing import RelayNodeHeartbeatRequest

        async with SessionLocal() as session:
            req = RelayNodeHeartbeatRequest(
                current_load=0.0,
                queue_depth=0,
                avg_latency_ms=None,
                success_rate=1.0,
            )
            try:
                await relay_node_heartbeat(str(relay_node_id), req, session, None)
            except Exception:
                # A failed health refresh must not drop the message; the
                # forward proceeds and the failure is logged.
                logger.warning(
                    "Relay heartbeat refresh failed for node %s",
                    relay_node_id,
                    exc_info=True,
                )

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

        # RECEIVE + HEARTBEAT: the relay node is alive and handling this
        # message, so refresh its heartbeat before forwarding.
        if relay_node_id is not None:
            await self.refresh_relay_health(relay_node_id)

        # LOOKUP + FORWARD: the central transport resolves the target
        # connection (local or cross-node) and performs the final hop.
        result = await self._central_transport().deliver(
            agent_id=agent_id,
            message=message,
            message_id=message_id,
            task_id=task_id,
            source_agent_id=source_agent_id,
            relay_node_id=relay_node_id,
            track_pending=track_pending,
        )
        result.latency_ms = int((time.perf_counter() - start) * 1000)

        # Record the relay_forwarded hop for the delivery timeline.
        if task_id is not None:
            try:
                from app.database import SessionLocal
                from app.models.message_delivery_event import MessageDeliveryEvent

                async with SessionLocal() as session:
                    session.add(
                        MessageDeliveryEvent(
                            message_id=message_id,
                            task_id=task_id,
                            event_type="relay_forwarded",
                            relay_node_id=relay_node_id,
                            extra_metadata={
                                "outcome": result.outcome,
                                "node_id": result.node_id,
                            },
                        )
                    )
                    await session.commit()
            except Exception:
                logger.warning(
                    "Failed to record relay_forwarded event for message %s",
                    message_id,
                    exc_info=True,
                )

        return result
