"""Determinism tests for the e2ee ciphertext marking.

The marking reuses the envelope's existing reserved fields
(security/encrypted_payload/aad). This validates, against
packages/protocol/schemas/envelope.schema.json (schema files stay at
exactly 7 — no new schema file is added for this):

  - a fully marked e2ee envelope validates
  - a plaintext-marked envelope validates
  - a missing nonce is rejected
  - an extra field inside `security` is rejected
    (additionalProperties: false)
  - an extra top-level field (e.g. a hand-rolled `enc` block) is
    rejected — the single source of the marking block is the reserved
    fields, not a new one
"""

import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

# Make the python-sdk importable when this file is collected outside the
# root conftest (e.g. `pytest apps/api` alone).
_SDK_ROOT = Path(__file__).parents[3] / "packages" / "python-sdk"
if str(_SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(_SDK_ROOT))

from agentnet.crypto import (
    AgentPublicKeys,
    generate_kem_keypair,
    generate_signing_keypair,
    seal_message,
)
from agentnet.websocket import AgentWebSocket

PLAINTEXT = b"top secret payload"

SCHEMA_DIR = (
    Path(__file__).parents[3] / "packages" / "protocol" / "schemas"
)
SCHEMA_PATH = SCHEMA_DIR / "envelope.schema.json"


@pytest.fixture(scope="module")
def validator() -> Draft202012Validator:
    with SCHEMA_PATH.open(encoding="utf-8") as f:
        return Draft202012Validator(json.load(f))


@pytest.fixture(scope="module")
def sealed():
    _, kem_pub = generate_kem_keypair()
    _, sig_pub = generate_signing_keypair()
    sig_priv, _ = generate_signing_keypair()
    return seal_message(
        PLAINTEXT,
        recipient_public_keys=AgentPublicKeys(kem=kem_pub, sig=sig_pub),
        sender_signing_private_key=sig_priv,
    )


def _envelope_from_build(msg: dict, **overrides) -> dict:
    """Map an SDK-built WS message onto the protocol envelope shape.

    The SDK wire message carries routing payload under `payload`; the
    envelope schema uses `content` parts. For e2ee messages the
    plaintext never appears in the envelope at all.
    """
    envelope = {
        "version": "arp-0.1",
        "message_id": msg["message_id"],
        "type": msg["type"],
        "timestamp": msg["timestamp"],
        "from": "AN-SENDER",
        "to": "AN-RECIPIENT",
        "security": msg["security"],
        "content": [],
        "encrypted_payload": msg["encrypted_payload"],
        "aad": msg["aad"],
    }
    envelope.update(overrides)
    return envelope


class TestE2eeEnvelopeSchema:
    def test_sealed_envelope_validates(self, validator, sealed):
        msg = AgentWebSocket._build_message(
            "task.result", {"task_id": "t-1"}, sealed=sealed
        )
        envelope = _envelope_from_build(msg)
        errors = list(validator.iter_errors(envelope))
        assert errors == [], [e.message for e in errors]

    def test_plaintext_envelope_validates(self, validator):
        msg = AgentWebSocket._build_message("task.result", {"task_id": "t-1"})
        envelope = _envelope_from_build(msg)
        assert list(validator.iter_errors(envelope)) == []

    def test_missing_nonce_rejected(self, validator, sealed):
        msg = AgentWebSocket._build_message(
            "task.result", {"task_id": "t-1"}, sealed=sealed
        )
        envelope = _envelope_from_build(msg)
        security = dict(envelope["security"])
        security["nonce"] = None
        envelope["security"] = security
        assert list(validator.iter_errors(envelope))

    def test_nonce_key_omitted_rejected(self, validator, sealed):
        msg = AgentWebSocket._build_message(
            "task.result", {"task_id": "t-1"}, sealed=sealed
        )
        envelope = _envelope_from_build(msg)
        security = dict(envelope["security"])
        del security["nonce"]
        envelope["security"] = security
        assert list(validator.iter_errors(envelope))

    def test_extra_security_field_rejected(self, validator, sealed):
        msg = AgentWebSocket._build_message(
            "task.result", {"task_id": "t-1"}, sealed=sealed
        )
        envelope = _envelope_from_build(msg)
        security = dict(envelope["security"])
        security["signature"] = "not-a-field"
        envelope["security"] = security
        errors = list(validator.iter_errors(envelope))
        assert errors, "additionalProperties:false must reject extra fields"

    def test_extra_top_level_field_rejected(self, validator, sealed):
        """A hand-rolled `enc` block (the rejected alternative design)
        must fail validation — the marking lives only in the reserved
        fields."""
        msg = AgentWebSocket._build_message(
            "task.result", {"task_id": "t-1"}, sealed=sealed
        )
        envelope = _envelope_from_build(msg)
        envelope["enc"] = {"alg": "aes-256-gcm"}
        assert list(validator.iter_errors(envelope))

    def test_e2ee_mode_value_accepted(self, validator, sealed):
        msg = AgentWebSocket._build_message(
            "task.result", {"task_id": "t-1"}, sealed=sealed
        )
        assert msg["security"]["mode"] == "e2ee"
        envelope = _envelope_from_build(msg)
        assert not list(validator.iter_errors(envelope))

    def test_sealed_marking_is_deterministic_in_shape(self, sealed):
        """Two independently sealed messages produce the same field
        shape (values differ — fresh nonce/ephemeral key per seal)."""
        msg1 = AgentWebSocket._build_message(
            "task.result", {"task_id": "1"}, sealed=sealed
        )
        _, kem_pub = generate_kem_keypair()
        _, sig_pub = generate_signing_keypair()
        sig_priv, _ = generate_signing_keypair()
        sealed2 = seal_message(
            PLAINTEXT,
            recipient_public_keys=AgentPublicKeys(kem=kem_pub, sig=sig_pub),
            sender_signing_private_key=sig_priv,
        )
        msg2 = AgentWebSocket._build_message(
            "task.result", {"task_id": "2"}, sealed=sealed2
        )
        assert set(msg1) == set(msg2)
        assert set(msg1["security"]) == {"mode", "encryption", "key_id", "nonce"}
        assert set(msg1["aad"]) == set(msg2["aad"])
        # But the actual ciphertext/nonce differ
        assert msg1["encrypted_payload"] != msg2["encrypted_payload"]
