"""M2: AgentWebSocket e2ee dispatch, dedup, and failure semantics.

Unit tests (no network). The fake connection records everything the SDK
tries to send so the tests can assert on the wire bytes.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from agentnet.crypto import (
    AgentPublicKeys,
    SealedMessage,
    b64decode,
    b64encode,
    generate_kem_keypair,
    generate_signing_keypair,
    open_message,
    seal_message,
)
from agentnet.idempotency import IdempotencyCache
from agentnet.session_store import SessionStore
from agentnet.types import MessageType
from agentnet.websocket import AgentWebSocket

PLAINTEXT_MARKER = "E2EE-PLAINTEXT-MARKER-3f9a"


class FakeConn:
    """Minimal stand-in for a connected websockets client."""

    def __init__(self) -> None:
        self.sent: list[str] = []
        self.state = SimpleNamespace(value=1)  # OPEN

    async def send(self, raw: str) -> None:
        self.sent.append(raw)

    async def close(self) -> None:
        self.state = SimpleNamespace(value=3)  # CLOSED


def _keypairs():
    recv_kem_priv, recv_kem_pub = generate_kem_keypair()
    recv_sig_priv, recv_sig_pub = generate_signing_keypair()
    send_kem_priv, send_kem_pub = generate_kem_keypair()
    send_sig_priv, send_sig_pub = generate_signing_keypair()
    return {
        "recv_kem_priv": recv_kem_priv,
        "recv_kem_pub": recv_kem_pub,
        "recv_sig_priv": recv_sig_priv,
        "recv_sig_pub": recv_sig_pub,
        "send_kem_priv": send_kem_priv,
        "send_kem_pub": send_kem_pub,
        "send_sig_priv": send_sig_priv,
        "send_sig_pub": send_sig_pub,
    }


def _seal_task_request(
    keys,
    plaintext: dict[str, Any],
    *,
    recipient_kem: bytes | None = None,
    task_id: str = "task-1",
    message_id: str = "msg-1",
) -> str:
    """Build the WS frame the relay delivers for a sealed task request."""
    sealed = seal_message(
        json.dumps(plaintext).encode("utf-8"),
        recipient_public_keys=AgentPublicKeys(
            kem=recipient_kem or keys["recv_kem_pub"],
            sig=keys["recv_sig_pub"],
        ),
        sender_signing_private_key=keys["send_sig_priv"],
        extra_aad={
            "from": "agt_sender",
            "to": "agt_receiver",
            "from_sig": b64encode(keys["send_sig_pub"]),
            "from_kem": b64encode(keys["send_kem_pub"]),
        },
    )
    # Mirror the real relay frame: ws_payload["payload"] is the full
    # sender envelope (the content stored by the platform) and the
    # top-level security block is the platform's verbatim copy of the
    # envelope's marker block.
    fields = sealed.to_envelope_fields()
    envelope = {"kind": "echo", **fields}
    frame = {
        "type": MessageType.TASK_REQUEST.value,
        "message_id": message_id,
        "task_id": task_id,
        "timestamp": "2026-10-01T00:00:00+00:00",
        "payload": envelope,
        "security": fields["security"],
        "encrypted_payload": fields["encrypted_payload"],
        "aad": fields["aad"],
    }
    return json.dumps(frame)


def _make_ws(keys=None, *, session_file: str | Path | None = None):
    store = SessionStore(str(session_file) if session_file else "unused-session.json")
    ws = AgentWebSocket(
        store,
        idempotency_cache=IdempotencyCache(),
        kem_private_key=keys["recv_kem_priv"] if keys else None,
        signing_private_key=keys["recv_sig_priv"] if keys else None,
    )
    conn = FakeConn()
    ws._ws = conn
    return ws, conn


def _sent_messages(conn: FakeConn) -> list[dict[str, Any]]:
    return [json.loads(raw) for raw in conn.sent]


@pytest.mark.asyncio
async def test_sealed_task_request_is_decrypted_and_dispatched(tmp_path):
    keys = _keypairs()
    ws, conn = _make_ws(keys, session_file=tmp_path / "s1.json")

    handler_payloads: list[dict[str, Any]] = []

    async def on_task_request(msg):
        handler_payloads.append(msg)

    ws.on_task_request(on_task_request)

    raw = _seal_task_request(keys, {"kind": "echo", "text": PLAINTEXT_MARKER})
    await ws._handle(raw)

    assert len(handler_payloads) == 1
    msg = handler_payloads[0]
    # the handler sees the decrypted plaintext, not the ciphertext
    assert msg["payload"] == {"kind": "echo", "text": PLAINTEXT_MARKER}
    # top-level routing fields survive
    assert msg["task_id"] == "task-1"
    # the marker block is still attached for the handler to inspect
    assert msg["security"]["mode"] == "e2ee"

    # the SDK auto-acked (routing-level, message_id is a plaintext field)
    acks = [m for m in _sent_messages(conn) if m["type"] == MessageType.ACK.value]
    assert len(acks) == 1
    assert acks[0]["payload"]["message_id"] == "msg-1"


@pytest.mark.asyncio
async def test_redelivery_is_accepted_exactly_once(tmp_path):
    keys = _keypairs()
    ws, conn = _make_ws(keys, session_file=tmp_path / "s2.json")

    handler_calls: list[dict[str, Any]] = []

    async def on_task_request(msg):
        handler_calls.append(msg)

    ws.on_task_request(on_task_request)

    raw = _seal_task_request(keys, {"kind": "echo", "text": PLAINTEXT_MARKER})
    await ws._handle(raw)
    # a replay/redelivery of the byte-identical string is deduplicated
    await ws._handle(raw)

    assert len(handler_calls) == 1
    acks = [m for m in _sent_messages(conn) if m["type"] == MessageType.ACK.value]
    assert len(acks) == 2  # re-acked, never re-executed


@pytest.mark.asyncio
async def test_lookalike_plaintext_is_judged_plaintext_zero_misclassification():
    # No keys configured: if this message were misjudged as e2ee the
    # SDK would send DECRYPT_FAILED and drop it.
    ws, conn = _make_ws(keys=None)

    handler_payloads: list[dict[str, Any]] = []

    async def on_task_request(msg):
        handler_payloads.append(msg)

    ws.on_task_request(on_task_request)

    # Top-level marker: relay_visible + null ciphertext. The payload
    # itself carries same-named lookalike fields.
    frame = {
        "type": MessageType.TASK_REQUEST.value,
        "message_id": "msg-plain",
        "task_id": "task-plain",
        "payload": {
            "kind": "echo",
            "text": "plain",
            "security": {"mode": "e2ee"},
            "encrypted_payload": "fake",
            "aad": {"fake": True},
        },
        "security": {
            "mode": "relay_visible",
            "encryption": "none",
            "key_id": None,
            "nonce": None,
        },
        "encrypted_payload": None,
        "aad": None,
    }
    await ws._handle(json.dumps(frame))

    assert len(handler_payloads) == 1
    assert handler_payloads[0]["payload"]["text"] == "plain"


@pytest.mark.asyncio
async def test_decrypt_failure_sends_task_failed_with_decrypt_failed(tmp_path):
    keys = _keypairs()
    ws, conn = _make_ws(keys, session_file=tmp_path / "s4.json")

    handler_calls: list[dict[str, Any]] = []

    async def on_task_request(msg):
        handler_calls.append(msg)

    ws.on_task_request(on_task_request)

    # Sealed to a recipient key that is NOT the receiver's key: the
    # envelope is well-formed but open() fails.
    wrong_priv, wrong_pub = generate_kem_keypair()
    raw = _seal_task_request(
        keys, {"kind": "echo", "text": PLAINTEXT_MARKER}, recipient_kem=wrong_pub
    )
    await ws._handle(raw)

    # the handler never ran on unverifiable bytes
    assert handler_calls == []

    failures = [
        m for m in _sent_messages(conn) if m["type"] == MessageType.TASK_FAILED.value
    ]
    assert len(failures) == 1
    assert failures[0]["payload"]["task_id"] == "task-1"
    assert "DECRYPT_FAILED" in failures[0]["payload"]["error_message"]


@pytest.mark.asyncio
async def test_malformed_envelope_missing_nonce_is_decrypt_failed(tmp_path):
    keys = _keypairs()
    ws, conn = _make_ws(keys, session_file=tmp_path / "s5.json")

    async def on_task_request(msg):
        pytest.fail("handler must not run on malformed ciphertext")

    ws.on_task_request(on_task_request)

    sealed = seal_message(
        json.dumps({"kind": "echo"}).encode("utf-8"),
        recipient_public_keys=AgentPublicKeys(
            kem=keys["recv_kem_pub"], sig=keys["recv_sig_pub"]
        ),
        sender_signing_private_key=keys["send_sig_priv"],
        extra_aad={
            "from": "agt_sender",
            "to": "agt_receiver",
            "from_sig": b64encode(keys["send_sig_pub"]),
            "from_kem": b64encode(keys["send_kem_pub"]),
        },
    )
    fields = sealed.to_envelope_fields()
    fields["security"] = dict(fields["security"])
    fields["security"]["nonce"] = None  # illegal: nonce removed
    envelope = {"kind": "echo", **fields}
    frame = {
        "type": MessageType.TASK_REQUEST.value,
        "message_id": "msg-broken",
        "task_id": "task-broken",
        "timestamp": "2026-10-01T00:00:00+00:00",
        "payload": envelope,
        "security": fields["security"],
        "encrypted_payload": fields["encrypted_payload"],
        "aad": fields["aad"],
    }
    await ws._handle(json.dumps(frame))

    failures = [
        m for m in _sent_messages(conn) if m["type"] == MessageType.TASK_FAILED.value
    ]
    assert len(failures) == 1
    assert "DECRYPT_FAILED" in failures[0]["payload"]["error_message"]


@pytest.mark.asyncio
async def test_sealed_result_round_trip_and_plaintext_metadata_only(tmp_path):
    keys = _keypairs()
    ws, conn = _make_ws(keys, session_file=tmp_path / "s6.json")

    captured: list[dict[str, Any]] = []

    async def on_task_request(msg):
        captured.append(msg)
        body = {"task_id": msg["task_id"], "result": {"echo": msg["payload"]}}
        sealed_reply = ws.seal_reply(msg["task_id"], body)
        assert sealed_reply is not None
        await ws.send_message(
            MessageType.TASK_RESULT, {"task_id": msg["task_id"]}, sealed=sealed_reply
        )

    ws.on_task_request(on_task_request)

    raw = _seal_task_request(keys, {"kind": "echo", "text": PLAINTEXT_MARKER})
    await ws._handle(raw)

    results = [
        m for m in _sent_messages(conn) if m["type"] == MessageType.TASK_RESULT.value
    ]
    assert len(results) == 1
    result = results[0]
    # the wire payload is routing metadata only — no plaintext leak
    assert result["payload"] == {"task_id": "task-1"}
    assert PLAINTEXT_MARKER not in json.dumps(result["payload"])
    # the marker block marks the message e2ee
    assert result["security"]["mode"] == "e2ee"
    assert result["encrypted_payload"]

    # the original sender can open the reply: full round trip
    sealed = SealedMessage.from_envelope_fields(
        {
            "security": result["security"],
            "encrypted_payload": result["encrypted_payload"],
            "aad": result["aad"],
        }
    )
    plaintext = open_message(
        sealed,
        recipient_kem_private_key=keys["send_kem_priv"],
        sender_signing_public_key=keys["recv_sig_pub"],
    )
    assert plaintext is not None
    body = json.loads(plaintext.decode("utf-8"))
    assert body["result"]["echo"]["text"] == PLAINTEXT_MARKER


@pytest.mark.asyncio
async def test_seal_reply_returns_none_without_keys(tmp_path):
    ws, _conn = _make_ws(keys=None, session_file=tmp_path / "s7.json")
    assert ws.seal_reply("task-x", {"task_id": "task-x"}) is None


@pytest.mark.asyncio
async def test_seal_reply_unknown_task_returns_none(tmp_path):
    keys = _keypairs()
    ws, _conn = _make_ws(keys, session_file=tmp_path / "s8.json")
    assert ws.seal_reply("never-seen", {"task_id": "never-seen"}) is None


@pytest.mark.asyncio
async def test_task_context_result_sealed_when_seal_fn_set(tmp_path):
    from agentnet.task import TaskContext

    keys = _keypairs()
    ws, conn = _make_ws(keys, session_file=tmp_path / "s9.json")

    # prime the peer state by handling a sealed request
    async def on_task_request(msg):
        pass

    ws.on_task_request(on_task_request)
    await ws._handle(_seal_task_request(keys, {"kind": "echo", "text": "x"}))

    ctx = TaskContext(
        task_id="task-1",
        payload={"kind": "echo"},
        session_store=ws._session_store,
        send_fn=ws.send_message,
        seal_fn=lambda body: ws.seal_reply("task-1", body),
    )
    await ctx.result({"echo": "ok"})

    results = [
        m for m in _sent_messages(conn) if m["type"] == MessageType.TASK_RESULT.value
    ]
    assert len(results) == 1
    assert results[0]["security"]["mode"] == "e2ee"
    assert results[0]["payload"] == {"task_id": "task-1"}
    assert ctx.status == "completed"


@pytest.mark.asyncio
async def test_task_context_result_fails_closed_when_seal_unavailable(tmp_path):
    from agentnet.task import TaskContext

    ws, conn = _make_ws(keys=None, session_file=tmp_path / "s10.json")

    ctx = TaskContext(
        task_id="task-2",
        payload={"kind": "echo"},
        session_store=ws._session_store,
        send_fn=ws.send_message,
        seal_fn=lambda body: None,  # cannot seal
    )
    await ctx.result({"echo": "ok"})

    # never sent as plaintext: the task fails closed instead
    results = [
        m for m in _sent_messages(conn) if m["type"] == MessageType.TASK_RESULT.value
    ]
    assert results == []
    failures = [
        m for m in _sent_messages(conn) if m["type"] == MessageType.TASK_FAILED.value
    ]
    assert len(failures) == 1
    assert "E2EE_REPLY_UNAVAILABLE" in failures[0]["payload"]["error_message"]
    assert ctx.status == "failed"
