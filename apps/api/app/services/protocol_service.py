from app.protocol.envelope import Envelope
from app.protocol.validators import ensure_mvp_security_supported


async def validate_inbound_envelope(envelope: Envelope) -> Envelope:
    ensure_mvp_security_supported(envelope)
    return envelope

