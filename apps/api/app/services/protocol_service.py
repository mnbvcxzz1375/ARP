"""Protocol-level validation entry points.

``validate_inbound_envelope`` validates a parsed ARP envelope via the
reserved marker fields (``security`` / ``encrypted_payload`` / ``aad``).

The guard is wired into task creation (``task_service.create_task``
validates the content envelope BEFORE persisting — 先校验后落库). The
WebSocket parse path intentionally does not perform envelope-level
security validation: the WS frame is the agent↔relay control channel
and the ARP envelope rides inside ``payload``; e2ee envelopes are
validated when they are turned into persisted task content.
"""

from app.protocol.envelope import Envelope
from app.protocol.validators import (
    content_security_mode,
    ensure_content_security_supported,
    ensure_mvp_security_supported,
)


async def validate_inbound_envelope(envelope: Envelope) -> Envelope:
    ensure_mvp_security_supported(envelope)
    return envelope


def validate_task_content_envelope(content: dict) -> dict:
    """Validate a task content envelope before it is persisted."""
    ensure_content_security_supported(content)
    return content


__all__ = [
    "content_security_mode",
    "ensure_content_security_supported",
    "ensure_mvp_security_supported",
    "validate_inbound_envelope",
    "validate_task_content_envelope",
]
