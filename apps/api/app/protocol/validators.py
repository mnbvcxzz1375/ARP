from app.exceptions import DomainException
from app.protocol.constants import ErrorCode, SecurityMode
from app.protocol.envelope import Envelope


def ensure_mvp_security_supported(envelope: Envelope) -> None:
    if envelope.security.mode == SecurityMode.E2EE:
        raise DomainException(
            ErrorCode.E2EE_NOT_IMPLEMENTED,
            "E2EE mode is reserved but not implemented in MVP.",
            status_code=501,
        )

