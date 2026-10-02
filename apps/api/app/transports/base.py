"""Transport abstraction for route-aware delivery."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

# Delivery outcome codes shared by all transports. They describe the
# *transport-level* truth, which routing_service maps onto delivery events.
SENT_LOCALLY = "sent_locally"
SENT_CROSS_NODE = "sent_cross_node"
# Redis pub/sub is unavailable AND the message could not be delivered on the
# local node: the message is queued for offline delivery, and the call site
# must NOT report a plain "queued" as if the agent were merely offline.
SENT_LOCALLY_QUEUED_CROSSNODE_DOWN = "sent_locally_queued_crossnode_down"
FAILED = "failed"
QUEUED_OFFLINE = "queued_offline"


@dataclass
class DeliveryResult:
    """What a transport actually did while delivering one message.

    outcome is one of the SENT_*/FAILED/QUEUED_OFFLINE codes above.
    node_id is the node the message landed on when the transport knows it
    (cross-node dispatch), otherwise None.
    """

    outcome: str
    node_id: str | None = None
    relay_node_id: uuid.UUID | None = None
    latency_ms: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    # True when the bytes were handed to a live WebSocket connection.
    actually_sent: bool = field(init=False, default=False)

    def __post_init__(self) -> None:
        self.actually_sent = self.outcome in (SENT_LOCALLY, SENT_CROSS_NODE)

    @property
    def is_sent(self) -> bool:
        return self.actually_sent

    @property
    def is_queued(self) -> bool:
        return self.outcome in (QUEUED_OFFLINE, SENT_LOCALLY_QUEUED_CROSSNODE_DOWN)

    @property
    def degraded(self) -> bool:
        """True when delivery only succeeded after a degradation path."""
        return self.outcome == SENT_LOCALLY_QUEUED_CROSSNODE_DOWN


class Transport:
    """Route-type delivery backend."""

    async def deliver(
        self,
        *,
        agent_id: uuid.UUID,
        message: str,
        message_id: str,
        track_pending: bool = True,
    ) -> DeliveryResult:
        raise NotImplementedError
