"""Transport layer: route_type-aware delivery backends.

M3 (relay dataplane dispatch): deliver_task_request() no longer sends on the
WebSocket bus directly. It resolves the selected_route_type to one of the
transport backends here:

- central_relay       -> CentralTransport (manager path, previous behaviour)
- personal_edge       -> RelayForwarder (in-process relay node simulation)
- regional_relay      -> RelayForwarder (in-process relay node simulation)
- dedicated_channel   -> ChannelTransport (consumes connection_config)

Every transport returns a DeliveryResult describing what actually happened,
so routing_service can record truthful delivery events instead of guessing
from "is_online".
"""

from app.transports.base import (
    DeliveryResult,
    Transport,
    FAILED,
    QUEUED_OFFLINE,
    SENT_CROSS_NODE,
    SENT_LOCALLY,
    SENT_LOCALLY_QUEUED_CROSSNODE_DOWN,
)


def select_transport(route_type: str | None) -> Transport:
    """Map a RouteDecision.selected_route_type onto a Transport backend.

    Unknown / None route types fall back to the central transport so
    pre-Phase-13 messages keep working.
    """
    from app.transports.central import CentralTransport
    from app.transports.channel_transport import ChannelTransport
    from app.transports.relay_forwarder import RelayForwarder

    if route_type == "dedicated_channel":
        return ChannelTransport()
    if route_type in ("personal_edge", "regional_relay"):
        return RelayForwarder()
    return CentralTransport()


__all__ = [
    "DeliveryResult",
    "Transport",
    "select_transport",
    "SENT_LOCALLY",
    "SENT_CROSS_NODE",
    "SENT_LOCALLY_QUEUED_CROSSNODE_DOWN",
    "FAILED",
    "QUEUED_OFFLINE",
]
