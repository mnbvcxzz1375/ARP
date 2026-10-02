"""Tests for the e2ee envelope marking in AgentWebSocket._build_message
and the E2EE key state in SessionStore."""

import json
import os
import tempfile
from pathlib import Path

from agentnet.crypto import (
    AgentPublicKeys,
    SealedMessage,
    generate_kem_keypair,
    generate_signing_keypair,
    key_fingerprint,
    open_message,
    seal_message,
)
from agentnet.session_store import SessionStore
from agentnet.websocket import AgentWebSocket

PLAINTEXT = b"secret payload"


def _make_sealed() -> tuple[SealedMessage, bytes, bytes]:
    kem_private, kem_public = generate_kem_keypair()
    sig_private, sig_public = generate_signing_keypair()
    sealed = seal_message(
        PLAINTEXT,
        recipient_public_keys=AgentPublicKeys(kem=kem_public, sig=sig_public),
        sender_signing_private_key=sig_private,
    )
    return sealed, kem_private, sig_public


class TestBuildMessagePlaintext:
    def test_plaintext_marking(self):
        msg = AgentWebSocket._build_message("task.progress", {"pct": 50})
        assert msg["security"]["mode"] == "relay_visible"
        assert msg["security"]["encryption"] == "none"
        assert msg["security"]["key_id"] is None
        assert msg["security"]["nonce"] is None
        assert msg["encrypted_payload"] is None
        assert msg["aad"] is None

    def test_plaintext_keeps_existing_fields(self):
        msg = AgentWebSocket._build_message("task.progress", {"pct": 50})
        assert msg["type"] == "task.progress"
        assert msg["payload"] == {"pct": 50}
        assert msg["message_id"]
        assert msg["timestamp"]
        # Still JSON-serializable as-is
        json.dumps(msg)

    def test_plaintext_is_jsonschema_friendly(self):
        """The security block itself must conform to the envelope $defs
        shape (all four properties, no extras)."""
        msg = AgentWebSocket._build_message("task.heartbeat", {})
        assert set(msg["security"]) <= {"mode", "encryption", "key_id", "nonce"}


class TestBuildMessageEncrypted:
    def test_encrypted_marking(self):
        sealed, _, _ = _make_sealed()
        msg = AgentWebSocket._build_message(
            "task.result", {"note": "metadata only"}, sealed=sealed
        )
        assert msg["security"]["mode"] == "e2ee"
        assert msg["security"]["encryption"]
        assert msg["security"]["key_id"] == sealed.key_id
        assert msg["security"]["nonce"]
        assert msg["encrypted_payload"]
        assert isinstance(msg["aad"], dict)
        # base64 decodable
        import base64

        base64.standard_b64decode(msg["encrypted_payload"])
        base64.standard_b64decode(msg["security"]["nonce"])
        # The plaintext never leaks into the envelope
        assert PLAINTEXT not in json.dumps(msg).encode("utf-8")

    def test_encrypted_message_is_openable_by_recipient(self):
        sealed, kem_private, sig_public = _make_sealed()
        msg = AgentWebSocket._build_message(
            "task.result", {"task_id": "t-1"}, sealed=sealed
        )
        restored = SealedMessage.from_envelope_fields(
            {
                "security": msg["security"],
                "encrypted_payload": msg["encrypted_payload"],
                "aad": msg["aad"],
            }
        )
        assert (
            open_message(
                restored,
                recipient_kem_private_key=kem_private,
                sender_signing_public_key=sig_public,
            )
            == PLAINTEXT
        )

    def test_encrypted_and_plaintext_differ_only_in_marking_fields(self):
        sealed, _, _ = _make_sealed()
        plain = AgentWebSocket._build_message("task.result", {"task_id": "t-1"})
        enc = AgentWebSocket._build_message(
            "task.result", {"task_id": "t-1"}, sealed=sealed
        )
        assert plain["type"] == enc["type"]
        assert plain["payload"] == enc["payload"]


class TestSessionStoreKeyState:
    def _store(self, tmp):
        return SessionStore(tmp)

    def test_peer_key_fingerprint_roundtrip(self):
        tmp = tempfile.mktemp(suffix=".json")
        try:
            store = self._store(tmp)
            store.set_peer_key_fingerprint("AN-PEER", "abc123")
            assert store.peer_key_fingerprint("AN-PEER") == "abc123"
            assert store.peer_key_fingerprint("AN-OTHER") is None
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_key_fingerprint_matches_crypto(self):
        _, kem_pub = generate_kem_keypair()
        _, sig_pub = generate_signing_keypair()
        keys = AgentPublicKeys(kem=kem_pub, sig=sig_pub)
        tmp = tempfile.mktemp(suffix=".json")
        try:
            store = self._store(tmp)
            store.set_peer_key_fingerprint("AN-PEER", keys.fingerprint)
            assert store.peer_key_fingerprint("AN-PEER") == key_fingerprint(kem_pub)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_session_key_handle_roundtrip(self):
        tmp = tempfile.mktemp(suffix=".json")
        try:
            store = self._store(tmp)
            store.set_session_key_handle("AN-PEER", "env:AGENTNET_KEM_PRIVATE")
            assert store.session_key_handle("AN-PEER") == "env:AGENTNET_KEM_PRIVATE"
            assert store.session_key_handle("AN-OTHER") is None
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_key_state_persists_to_disk(self):
        tmp = tempfile.mktemp(suffix=".json")
        try:
            store1 = self._store(tmp)
            store1.set_peer_key_fingerprint("AN-PEER", "fp-1")
            store1.set_session_key_handle("AN-PEER", "handle-1")

            data = json.loads(Path(tmp).read_text())
            assert data["peer_keys"] == {"AN-PEER": "fp-1"}
            assert data["session_key_handles"] == {"AN-PEER": "handle-1"}

            store2 = SessionStore(tmp)
            store2.open()
            assert store2.peer_key_fingerprint("AN-PEER") == "fp-1"
            assert store2.session_key_handle("AN-PEER") == "handle-1"
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_legacy_state_file_loads_without_key_state(self):
        """State files written before the key-state fields existed must
        still load cleanly (backward compatibility)."""
        tmp = tempfile.mktemp(suffix=".json")
        try:
            Path(tmp).write_text(
                json.dumps(
                    {
                        "session_id": "s-1",
                        "last_message_id": "m-1",
                        "running_tasks": {"t-1": {"started_at": "x"}},
                    }
                )
            )
            store = SessionStore(tmp)
            store.open()
            assert store.session_id == "s-1"
            assert store.last_message_id == "m-1"
            assert store.is_task_running("t-1")
            assert store.peer_key_fingerprint("AN-PEER") is None
            assert store.session_key_handle("AN-PEER") is None
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_key_state_does_not_clobber_other_state(self):
        tmp = tempfile.mktemp(suffix=".json")
        try:
            store = self._store(tmp)
            store.set_session_id("s-9")
            store.set_last_message_id("m-9")
            store.add_running_task("t-9")
            store.set_peer_key_fingerprint("AN-PEER", "fp-9")
            store.set_session_key_handle("AN-PEER", "h-9")

            store2 = SessionStore(tmp)
            store2.open()
            assert store2.session_id == "s-9"
            assert store2.last_message_id == "m-9"
            assert store2.is_task_running("t-9")
            assert store2.peer_key_fingerprint("AN-PEER") == "fp-9"
            assert store2.session_key_handle("AN-PEER") == "h-9"
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
