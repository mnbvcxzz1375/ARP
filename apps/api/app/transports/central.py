"""Central relay transport: the platform WebSocket bus.

This is the pre-M3 delivery path, now wrapped as a Transport so
deliver_task_request() can dispatch on route_type. It is also the final
delivery hop used by the relay forwarder and the channel transport.

Cross-node model (M3): an agent's WebSocket lives on exactly one API node.
The local manager tries the local connections first; if none exist, the
presence key (ws:presence:{agent_id}, whose value is the node_id that owns
the connection) tells us where the agent is, and the message is published
to that node's channel (agentnet:node:{node_id}). The receiving node hands
the bytes to its own local connection. Redis pub/sub failure degrades to
the offline queue with an explicit degraded outcome instead of a silent
mis-delivery.
"""

from __future__ import annotations

import json
import logging
import time
import uuid

from app.transports.base import (
    DeliveryResult,
    Transport,
    FAILED,
    QUEUED_OFFLINE,
    SENT_CROSS_NODE,
    SENT_LOCALLY,
    SENT_LOCALLY_QUEUED_CROSSNODE_DOWN,
)

logger = logging.getLogger(__name__)


class CentralTransport(Transport):
    """Deliver over the central WebSocket bus, with cross-node fan-out."""

    def __init__(self, manager=None):
        # Lazily resolved so tests can pass a two-instance setup and so
        # importing this module never constructs the singleton.
        self._manager = manager

    def _manager_or_default(self):
        from app.websocket.manager import get_connection_manager

        return self._manager if self._manager is not None else get_connection_manager()

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
        mgr = self._manager_or_default()
        start = time.perf_counter()

        # Step 1: local connections on this node.
        sent = await mgr.send_to_agent(agent_id, message, track_pending=track_pending)
        latency_ms = int((time.perf_counter() - start) * 1000)
        if sent:
            return DeliveryResult(
                outcome=SENT_LOCALLY,
                node_id=mgr.node_id,
                relay_node_id=relay_node_id,
                latency_ms=latency_ms,
            )

        # Step 2: no local connection — locate the agent's node via presence.
        try:
            node_id = await mgr.get_agent_node(agent_id)
        except Exception as exc:
            logger.warning(
                "Presence lookup failed for agent %s while dispatching "
                "message %s: %s",
                agent_id,
                message_id,
                exc,
            )
            node_id = None

        if not node_id:
            # Agent is genuinely offline (no presence entry anywhere):
            # queueing here is not a failure of anything.
            return DeliveryResult(
                outcome=QUEUED_OFFLINE,
                node_id=None,
                relay_node_id=relay_node_id,
                latency_ms=latency_ms,
            )

        if node_id == mgr.node_id:
            # Presence says the agent is connected — HERE — yet the local
            # send failed (stale presence or a broken socket). This is a
            # delivery FAILURE, not "agent offline": call sites must count
            # it as an attempt (the retry worker consumes a retry budget
            # for it) instead of silently re-queueing forever.
            return DeliveryResult(
                outcome=FAILED,
                node_id=node_id,
                relay_node_id=relay_node_id,
                latency_ms=latency_ms,
                error_code="LOCAL_SEND_FAILED",
                error_message=(
                    "Agent presence existed on this node but the local "
                    "send failed (stale presence or broken socket)"
                ),
            )

        # Step 3: publish to the owning node's channel.
        payload = json.dumps(
            {
                "agent_id": str(agent_id),
                "message": message,
                "message_id": message_id,
                "task_id": str(task_id) if task_id else None,
                "track_pending": track_pending,
                "source_node": mgr.node_id,
            }
        )
        try:
            await mgr.publish_cross_node(node_id, payload)
        except Exception as exc:
            # Redis pub/sub is broken. Queue for offline delivery and report
            # the degradation explicitly — never report plain "queued",
            # which callers would read as "agent offline".
            logger.warning(
                "Cross-node publish to node %s failed for message %s "
                "(agent %s): falling back to offline queue: %s",
                node_id,
                message_id,
                agent_id,
                exc,
            )
            return DeliveryResult(
                outcome=SENT_LOCALLY_QUEUED_CROSSNODE_DOWN,
                node_id=node_id,
                relay_node_id=relay_node_id,
                latency_ms=latency_ms,
                error_code="CROSSNODE_PUBSUB_FAILED",
                error_message=str(exc),
            )

        return DeliveryResult(
            outcome=SENT_CROSS_NODE,
            node_id=node_id,
            relay_node_id=relay_node_id,
            latency_ms=latency_ms,
        )
