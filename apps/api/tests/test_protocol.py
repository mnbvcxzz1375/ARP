from pydantic import ValidationError
import pytest

from app.exceptions import DomainException
from app.protocol.constants import ErrorCode, MessageType, SecurityMode
from app.protocol.envelope import Envelope
from app.protocol.validators import ensure_mvp_security_supported


def test_protocol_model_validation() -> None:
    envelope = Envelope.model_validate(
        {
            "message_id": "msg_01JABC",
            "request_id": "req_01JABC",
            "session_id": "sess_01JABC",
            "type": "task.request",
            "from": "agt_sender",
            "to": "agt_receiver",
            "task_id": "task_01JABC",
            "content": [{"mime": "text/plain", "text": "hello"}],
            "delivery": {"requires_ack": True, "idempotency_key": "idem_01JABC"},
        }
    )

    assert envelope.version == "arp-0.1"
    assert envelope.type == MessageType.TASK_REQUEST
    assert envelope.from_agent == "agt_sender"
    assert envelope.to_agent == "agt_receiver"
    assert envelope.security.mode == SecurityMode.RELAY_VISIBLE


def test_invalid_security_mode_rejected_by_model() -> None:
    with pytest.raises(ValidationError):
        Envelope.model_validate(
            {
                "message_id": "msg_bad",
                "type": "task.request",
                "security": {"mode": "mtproto"},
            }
        )


def test_e2ee_reserved_field_is_accepted_by_model() -> None:
    envelope = Envelope.model_validate(
        {
            "message_id": "msg_e2ee",
            "type": "task.request",
            "security": {
                "mode": "e2ee",
                "encryption": "x25519-chacha20poly1305",
                "key_id": "key_01JABC",
                "nonce": "base64_nonce",
            },
            "encrypted_payload": "base64_ciphertext",
            "aad": {"from": "agt_sender", "to": "agt_receiver", "type": "task.request"},
        }
    )

    assert envelope.security.mode == SecurityMode.E2EE
    assert envelope.encrypted_payload == "base64_ciphertext"


def test_e2ee_reserved_mode_is_not_implemented_in_business_logic() -> None:
    envelope = Envelope.model_validate(
        {
            "message_id": "msg_e2ee",
            "type": "task.request",
            "security": {"mode": "e2ee"},
        }
    )

    with pytest.raises(DomainException) as exc_info:
        ensure_mvp_security_supported(envelope)

    assert exc_info.value.code == ErrorCode.E2EE_NOT_IMPLEMENTED
    assert exc_info.value.status_code == 501

