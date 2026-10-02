"""M2: non-interactive E2EE passthrough.

Covers:
- content-envelope guard (validate BEFORE persisting),
- negotiation derived from the receiver's published public_keys
  (fail closed for legacy agents, priority fallback),
- read-side degradation (encrypted flag / encrypted_parse_error /
  per-message classification, zero misclassification of lookalikes),
- the full live e2ee round trip: offline queue -> reconnect redelivery
  -> SDK decrypt with the long-lived key -> sealed result write-back,
  with the ciphertext stores byte-identical,
- DECRYPT_FAILED terminating the task in the failed state.
"""

from __future__ import annotations

import asyncio
import base64
import json
import sys
import uuid
from pathlib import Path
from typing import Any

# The python-sdk ships the E2EE crypto primitives used by the live
# tests; put it on the path when running from apps/api.
_SDK_ROOT = Path(__file__).resolve().parents[3] / "packages" / "python-sdk"
if str(_SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(_SDK_ROOT))

import httpx
import pytest
from sqlalchemy import select

from app.database import SessionLocal
from app.exceptions import DomainException
from app.main import app
from app.models.agent import Agent
from app.models.connection import Connection
from app.models.message import Message
from app.models.task import Task
from app.protocol.constants import ErrorCode, SecurityMode
from app.protocol.validators import (
    content_security_mode,
    ensure_content_security_supported,
)
from app.services.connection_service import (
    agent_supported_security_modes,
    negotiate_security_mode,
)
from app.services.message_content_view import build_content_view

from helpers.ws_e2e import run_live_server

PLAINTEXT_MARKER = "E2EE-PLAINTEXT-MARKER-3f9a"


def _b64(data: bytes) -> str:
    return base64.standard_b64encode(data).decode("ascii")


def _envelope_fields(
    *,
    mode: str = "e2ee",
    nonce: str | None = "bm9uY2U=",
    encrypted_payload: str | None = "YWJjZA==",
    aad: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "security": {
            "mode": mode,
            "encryption": "X25519+HKDF-SHA256+AES-256-GCM",
            "key_id": "key_01",
            "nonce": nonce,
        },
        "encrypted_payload": encrypted_payload,
        "aad": aad if aad is not None else {"from": "agt_a", "to": "agt_b"},
    }


async def _register_user(client: httpx.AsyncClient, name: str) -> str:
    resp = await client.post(
        "/v1/auth/register", json={"username": name, "key_name": "e2ee"}
    )
    assert resp.status_code == 200
    return resp.json()["api_key"]


async def _create_agent(client, api_key, *, inbound_policy="request_approval"):
    resp = await client.post(
        "/v1/agents",
        json={
            "name": f"agt-{uuid.uuid4().hex[:6]}",
            "runtime": "pytest",
            "inbound_policy": inbound_policy,
        },
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 201
    return resp.json()


async def _caller_agent(client, api_key):
    resp = await client.post(
        "/v1/agents",
        json={"name": f"caller-{uuid.uuid4().hex[:6]}", "runtime": "pytest"},
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    """Real-app client (real sessions, real commits) — same style as
    test_phase5_connection_policy.py, so cross-session reads (route
    lease verification) see committed rows."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# unit: content envelope guard
# ---------------------------------------------------------------------------


class TestContentEnvelopeGuard:
    def test_plaintext_content_passes(self) -> None:
        ensure_content_security_supported({"kind": "echo", "text": "hi"})

    def test_relay_visible_marker_passes(self) -> None:
        ensure_content_security_supported(
            {"kind": "echo", **_envelope_fields(mode="relay_visible")}
        )

    def test_bare_e2ee_without_ciphertext_stays_reserved_501(self) -> None:
        content = {"kind": "echo"}
        content["security"] = {"mode": "e2ee", "encryption": "none"}
        with pytest.raises(DomainException) as exc_info:
            ensure_content_security_supported(content)
        assert exc_info.value.code == ErrorCode.E2EE_NOT_IMPLEMENTED
        assert exc_info.value.status_code == 501

    def test_e2ee_missing_nonce_rejected_400(self) -> None:
        content = {"kind": "echo", **_envelope_fields(nonce=None)}
        with pytest.raises(DomainException) as exc_info:
            ensure_content_security_supported(content)
        assert exc_info.value.status_code == 400

    def test_e2ee_non_base64_payload_rejected_400(self) -> None:
        content = {"kind": "echo", **_envelope_fields(encrypted_payload="not!base64?")}
        with pytest.raises(DomainException) as exc_info:
            ensure_content_security_supported(content)
        assert exc_info.value.status_code == 400

    def test_e2ee_non_base64_nonce_rejected_400(self) -> None:
        content = {"kind": "echo", **_envelope_fields(nonce="###")}
        with pytest.raises(DomainException) as exc_info:
            ensure_content_security_supported(content)
        assert exc_info.value.status_code == 400

    def test_e2ee_well_formed_passes(self) -> None:
        ensure_content_security_supported({"kind": "echo", **_envelope_fields()})


# ---------------------------------------------------------------------------
# unit: supported modes derived from public_keys
# ---------------------------------------------------------------------------


def _agent_with_keys(public_keys: Any) -> Agent:
    agent = Agent(
        agent_number=f"AN-T-{uuid.uuid4().hex[:6]}",
        owner_id=uuid.uuid4(),
        name="t",
        runtime="t",
        inbound_policy="public",
    )
    agent.public_keys = public_keys
    return agent


def _raw_public(pub) -> str:
    from cryptography.hazmat.primitives import serialization

    return _b64(
        pub.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    )


class TestSupportedSecurityModes:
    def test_legacy_agent_without_keys_is_plaintext_only(self) -> None:
        agent = _agent_with_keys(None)
        assert agent_supported_security_modes(agent) == ["relay_visible"]

    def test_agent_with_valid_keys_advertises_e2ee(self) -> None:
        from cryptography.hazmat.primitives.asymmetric import ed25519, x25519

        kem_pub = _raw_public(x25519.X25519PrivateKey.generate().public_key())
        sig_pub = _raw_public(ed25519.Ed25519PrivateKey.generate().public_key())
        agent = _agent_with_keys({"kem": kem_pub, "sig": sig_pub, "v": 1})
        assert agent_supported_security_modes(agent) == ["relay_visible", "e2ee"]

    def test_malformed_key_bundle_fails_closed(self) -> None:
        agent = _agent_with_keys({"kem": "not-base64", "sig": "???"})
        assert agent_supported_security_modes(agent) == ["relay_visible"]

    def test_unknown_version_fails_closed(self) -> None:
        agent = _agent_with_keys(
            {"kem": _b64(b"0" * 32), "sig": _b64(b"0" * 32), "v": 99}
        )
        assert agent_supported_security_modes(agent) == ["relay_visible"]


class TestNegotiationPriority:
    def test_e2ee_preferred_when_both_supported(self) -> None:
        assert (
            negotiate_security_mode(["e2ee", "relay_visible"], ["e2ee", "relay_visible"])
            == "e2ee"
        )

    def test_relay_visible_fallback_when_e2ee_unsupported(self) -> None:
        assert (
            negotiate_security_mode(["e2ee", "relay_visible"], ["relay_visible"])
            == "relay_visible"
        )

    def test_e2ee_only_against_keyless_receiver_raises(self) -> None:
        with pytest.raises(DomainException) as exc_info:
            negotiate_security_mode(["e2ee"], ["relay_visible"])
        assert exc_info.value.code == ErrorCode.SECURITY_MODE_NOT_SUPPORTED


# ---------------------------------------------------------------------------
# read-side degradation view
# ---------------------------------------------------------------------------


class TestContentView:
    def test_plaintext_content_unchanged(self) -> None:
        content = {"kind": "echo", "text": "hi"}
        assert build_content_view(content) is content

    def test_lookalike_plaintext_judged_plaintext_zero_misclassification(self) -> None:
        # The payload carries same-named lookalike fields, but the
        # top-level marker block says relay_visible + null ciphertext:
        # the message is plaintext, verbatim.
        content = {
            "kind": "echo",
            "text": "plain",
            "security": {
                "mode": "relay_visible",
                "encryption": "none",
                "key_id": None,
                "nonce": None,
            },
            "encrypted_payload": None,
            "aad": None,
            "payload": {"security": {"mode": "e2ee"}, "encrypted_payload": "fake"},
        }
        assert build_content_view(content) is content

    def test_well_formed_ciphertext_returns_encrypted_flag(self) -> None:
        fields = _envelope_fields()
        view = build_content_view({"kind": "echo", **fields})
        assert view["encrypted"] is True
        assert view["security"] == fields["security"]
        assert view["encrypted_payload"] == fields["encrypted_payload"]
        assert view["aad"] == fields["aad"]

    def test_missing_nonce_returns_parse_error_not_raise(self) -> None:
        view = build_content_view({"kind": "echo", **_envelope_fields(nonce=None)})
        assert view["encrypted_parse_error"] is True
        assert view["encrypted"] is False

    def test_non_base64_payload_returns_parse_error(self) -> None:
        view = build_content_view(
            {"kind": "echo", **_envelope_fields(encrypted_payload="%%%")}
        )
        assert view["encrypted_parse_error"] is True

    def test_content_security_mode_reads_marker_only(self) -> None:
        assert content_security_mode({"security": {"mode": "e2ee"}}) == "e2ee"
        assert (
            content_security_mode({"security": {"mode": "relay_visible"}})
            == "relay_visible"
        )
        assert content_security_mode({}) is None
        assert content_security_mode({"security": "not-a-dict"}) is None


# ---------------------------------------------------------------------------
# REST: negotiation failure leaves no pending residue
# ---------------------------------------------------------------------------


class TestNegotiationRequestApprovalPath:
    async def test_e2ee_to_keyless_agent_400_without_pending_residue(
        self, client
    ):
        user_a = await _register_user(client, f"e2ee-a-{uuid.uuid4().hex[:6]}")
        user_b = await _register_user(client, f"e2ee-b-{uuid.uuid4().hex[:6]}")
        sender = await _caller_agent(client, user_a)
        target = await _create_agent(client, user_b, inbound_policy="request_approval")

        async def post_e2ee():
            return await client.post(
                "/v1/tasks",
                json={
                    "assigned_to": target["agent_number"],
                    "from_agent_number": sender["agent_number"],
                    "payload": {"kind": "echo"},
                    **_envelope_fields(),
                },
                headers={"X-API-Key": user_a},
            )

        resp = await post_e2ee()
        assert resp.status_code == 400
        assert (
            resp.json()["error"]["code"]
            == ErrorCode.SECURITY_MODE_NOT_SUPPORTED.value
        )

        # No pending Connection residue: the negotiation raised before
        # any Connection row was added or committed.
        from_uuid_sender = uuid.UUID(sender["agent_id"])
        from_uuid_target = uuid.UUID(target["agent_id"])

        async with SessionLocal() as fresh:
            rows = (
                await fresh.execute(
                    select(Connection).where(
                        Connection.from_agent_id == from_uuid_sender,
                        Connection.to_agent_id == from_uuid_target,
                    )
                )
            ).all()
            assert rows == []

        # Retry of the same pair does not collide with the
        # uq_pending_connection unique index: it fails closed again.
        resp2 = await post_e2ee()
        assert resp2.status_code == 400
        assert (
            resp2.json()["error"]["code"]
            == ErrorCode.SECURITY_MODE_NOT_SUPPORTED.value
        )

    async def test_relay_visible_fallback_creates_pending_202(self, client):
        user_a = await _register_user(client, f"e2ee-c-{uuid.uuid4().hex[:6]}")
        user_b = await _register_user(client, f"e2ee-d-{uuid.uuid4().hex[:6]}")
        sender = await _caller_agent(client, user_a)
        target = await _create_agent(client, user_b, inbound_policy="request_approval")

        resp = await client.post(
            "/v1/tasks",
            json={
                "assigned_to": target["agent_number"],
                "from_agent_number": sender["agent_number"],
                "payload": {
                    "kind": "echo",
                    "requested_security_modes": ["relay_visible", "e2ee"],
                },
            },
            headers={"X-API-Key": user_a},
        )
        assert resp.status_code == 202
        assert (
            resp.json()["error"]["code"]
            == ErrorCode.CONNECTION_APPROVAL_REQUIRED.value
        )

    async def test_e2ee_to_keyed_agent_negotiates_e2ee_pending_202(self, client):
        from cryptography.hazmat.primitives.asymmetric import ed25519, x25519

        user_a = await _register_user(client, f"e2ee-e-{uuid.uuid4().hex[:6]}")
        user_b = await _register_user(client, f"e2ee-f-{uuid.uuid4().hex[:6]}")
        sender = await _caller_agent(client, user_a)
        target = await _create_agent(client, user_b, inbound_policy="request_approval")

        # Publish keys via a committed session so the endpoint's own
        # session reads them fresh.
        async with SessionLocal() as pub_session:
            agent = await pub_session.get(Agent, uuid.UUID(target["agent_id"]))
            assert agent is not None
            agent.public_keys = {
                "kem": _raw_public(x25519.X25519PrivateKey.generate().public_key()),
                "sig": _raw_public(ed25519.Ed25519PrivateKey.generate().public_key()),
                "v": 1,
            }
            await pub_session.commit()

        resp = await client.post(
            "/v1/tasks",
            json={
                "assigned_to": target["agent_number"],
                "from_agent_number": sender["agent_number"],
                "payload": {"kind": "echo"},
                **_envelope_fields(),
            },
            headers={"X-API-Key": user_a},
        )
        assert resp.status_code == 202
        details = resp.json()["error"].get("details", {})
        connection_id = details.get("connection_id")
        assert connection_id

        async with SessionLocal() as fresh:
            conn = await fresh.get(Connection, uuid.UUID(connection_id))
            assert conn is not None
            assert conn.preferred_security_mode == SecurityMode.E2EE.value


class TestCreateTaskMalformedEnc:
    async def test_missing_nonce_rejected_before_persisting(self, client):
        user_a = await _register_user(client, f"e2ee-g-{uuid.uuid4().hex[:6]}")
        sender = await _caller_agent(client, user_a)
        target = await _create_agent(client, user_a, inbound_policy="public")

        resp = await client.post(
            "/v1/tasks",
            json={
                "assigned_to": target["agent_number"],
                "from_agent_number": sender["agent_number"],
                "payload": {"kind": "echo"},
                **_envelope_fields(nonce=None),
            },
            headers={"X-API-Key": user_a},
        )
        assert resp.status_code == 400

        # Nothing was persisted: no task/request message carries our
        # marker security block (validate-before-persist held).
        async with SessionLocal() as fresh:
            rows = (
                await fresh.execute(
                    select(Message).where(Message.type == "task.request")
                )
            ).scalars().all()
        leaked = [
            m
            for m in rows
            if isinstance(m.content, dict)
            and isinstance(m.content.get("security"), dict)
            and m.content["security"].get("key_id") == "key_01"
        ]
        assert leaked == []


# ---------------------------------------------------------------------------
# read-side mixed history (plaintext + ciphertext interleaved)
# ---------------------------------------------------------------------------


class TestMixedReadHistory:
    async def test_plaintext_and_ciphertext_read_per_message(self, client):
        api_key = await _register_user(client, f"mix-{uuid.uuid4().hex[:6]}")
        headers = {"X-API-Key": api_key}

        agent_resp = await client.post(
            "/v1/agents",
            json={"name": f"mix-{uuid.uuid4().hex[:6]}", "runtime": "pytest"},
            headers=headers,
        )
        assert agent_resp.status_code == 201
        agent_number = agent_resp.json()["agent_number"]

        created = await client.post(
            "/v1/tasks",
            json={"assigned_to": agent_number, "payload": {"kind": "echo"}},
            headers=headers,
        )
        assert created.status_code == 201
        task_id = created.json()["task_id"]

        async with SessionLocal() as insert_session:
            task = await insert_session.get(Task, uuid.UUID(task_id))
            assert task is not None

            # A ciphertext message and a malformed-ciphertext message in
            # the same task, interleaved with the plaintext history row.
            fields = _envelope_fields()
            extra = [
                Message(
                    task_id=task.id,
                    message_id=f"m-cipher-{uuid.uuid4().hex[:8]}",
                    type="task.result",
                    delivery_status="acknowledged",
                    content={"kind": "echo", **fields},
                ),
                Message(
                    task_id=task.id,
                    message_id=f"m-broken-{uuid.uuid4().hex[:8]}",
                    type="task.progress",
                    delivery_status="acknowledged",
                    content={"kind": "echo", **_envelope_fields(nonce=None)},
                ),
            ]
            for m in extra:
                insert_session.add(m)
            await insert_session.commit()

        resp = await client.get(f"/v1/tasks/{task_id}/messages", headers=headers)
        assert resp.status_code == 200
        views = {m["message_id"]: m["content"] for m in resp.json()["messages"]}
        assert len(views) == 3

        # plaintext history row: unchanged, readable
        plain_message_id = created.json()["message_id"]
        assert views[plain_message_id] == {"kind": "echo"}

        # ciphertext row: encrypted flag + raw ciphertext, no plaintext
        cipher = views[extra[0].message_id]
        assert cipher["encrypted"] is True
        assert cipher["encrypted_payload"] == fields["encrypted_payload"]
        assert "kind" not in cipher

        # malformed row: parse-error flag, no exception, no 500
        broken = views[extra[1].message_id]
        assert broken["encrypted_parse_error"] is True


# ---------------------------------------------------------------------------
# live e2ee round trip
# ---------------------------------------------------------------------------


async def _reset_circuit_breakers() -> None:
    """Reset relay circuit breakers polluted by offline-queue metrics.

    Offline-queued deliveries are recorded as route-metric failures
    (pre-existing committed behavior of the queued delivery path), and an
    open default-relay breaker makes later task creation fail with
    NO_AVAILABLE_RELAY. Resetting here keeps the shared dev DB sane for
    this module's live tests.
    """
    from sqlalchemy import text

    async with SessionLocal() as s:
        await s.execute(
            text(
                "UPDATE circuit_breakers SET state='closed', "
                "failure_count=0, success_count=0, open_until=NULL"
            )
        )
        await s.commit()


def _kem_keypair():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import x25519

    priv = x25519.X25519PrivateKey.generate()
    raw_priv = priv.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    raw_pub = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )
    return raw_priv, raw_pub


def _sig_keypair():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519

    priv = ed25519.Ed25519PrivateKey.generate()
    raw_priv = priv.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    raw_pub = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )
    return raw_priv, raw_pub


async def _publish_receiver_keys(agent_id: str, kem_pub: bytes, sig_pub: bytes) -> None:
    async with SessionLocal() as s:
        agent = await s.get(Agent, uuid.UUID(agent_id))
        agent.public_keys = {"kem": _b64(kem_pub), "sig": _b64(sig_pub), "v": 1}
        await s.commit()


def _seal_for_receiver(
    plaintext: dict[str, Any],
    *,
    recipient_kem: bytes,
    recipient_sig: bytes,
    sender_kem_priv: bytes,
    sender_sig_priv: bytes,
    from_number: str,
    to_number: str,
):
    from agentnet.crypto import AgentPublicKeys, seal_message

    sealed = seal_message(
        json.dumps(plaintext).encode("utf-8"),
        recipient_public_keys=AgentPublicKeys(kem=recipient_kem, sig=recipient_sig),
        sender_signing_private_key=sender_sig_priv,
        extra_aad={
            "from": from_number,
            "to": to_number,
            "from_sig": _b64(_ed25519_public(sender_sig_priv)),
            "from_kem": _b64(_x25519_public(sender_kem_priv)),
        },
    )
    return sealed


def _x25519_public(priv: bytes) -> bytes:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import x25519

    return x25519.X25519PrivateKey.from_private_bytes(priv).public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )


def _ed25519_public(priv: bytes) -> bytes:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519

    return ed25519.Ed25519PrivateKey.from_private_bytes(priv).public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )


def _tmp_session_path(name: str):
    import tempfile
    from pathlib import Path

    path = Path(tempfile.gettempdir()) / name
    if path.exists():
        path.unlink()
    return path


async def _wait_for(predicate, timeout: float = 15.0, interval: float = 0.1):
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(interval)
    raise TimeoutError("condition never became true")


async def _wait_for_status(
    client: httpx.AsyncClient, task_id: str, headers, expected: str, timeout: float = 15.0
) -> str:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        resp = await client.get(f"/v1/tasks/{task_id}", headers=headers)
        if resp.status_code == 200 and resp.json()["status"] == expected:
            return expected
        await asyncio.sleep(0.1)
    raise TimeoutError(f"task {task_id} never reached {expected}")


@pytest.mark.anyio
async def test_e2ee_offline_reconnect_decrypt_and_sealed_result(monkeypatch):
    await _reset_circuit_breakers()

    from agentnet.crypto import SealedMessage, open_message
    from agentnet.session_store import SessionStore
    from agentnet.types import MessageType
    from agentnet.websocket import AgentWebSocket

    async with run_live_server(monkeypatch) as server:
        async with httpx.AsyncClient(base_url=server.base_url) as client:
            suffix = uuid.uuid4().hex[:8]
            register = await client.post(
                "/v1/auth/register",
                json={"username": f"e2ee-live-{suffix}", "key_name": "e2ee"},
            )
            assert register.status_code == 200
            api_key = register.json()["api_key"]
            headers = {"Authorization": f"Bearer {api_key}"}

            sender = await client.post(
                "/v1/agents",
                json={"name": "E2E Sender", "runtime": "pytest"},
                headers=headers,
            )
            assert sender.status_code == 201
            receiver = await client.post(
                "/v1/agents",
                json={
                    "name": "E2E Receiver",
                    "runtime": "pytest",
                    "inbound_policy": "public",
                },
                headers=headers,
            )
            assert receiver.status_code == 201
            sender = sender.json()
            receiver = receiver.json()

            # long-lived keys
            sender_kem_priv, _sender_kem_pub = _kem_keypair()
            sender_sig_priv, _sender_sig_pub = _sig_keypair()
            recv_kem_priv, recv_kem_pub = _kem_keypair()
            recv_sig_priv, recv_sig_pub = _sig_keypair()

            await _publish_receiver_keys(receiver["agent_id"], recv_kem_pub, recv_sig_pub)

            # seal: the plaintext (with the marker) rides in the
            # ciphertext only — the REST payload stays routing metadata.
            sealed = _seal_for_receiver(
                {"kind": "echo", "text": PLAINTEXT_MARKER},
                recipient_kem=recv_kem_pub,
                recipient_sig=recv_sig_pub,
                sender_kem_priv=sender_kem_priv,
                sender_sig_priv=sender_sig_priv,
                from_number=sender["agent_number"],
                to_number=receiver["agent_number"],
            )
            fields = sealed.to_envelope_fields()

            created = await client.post(
                "/v1/tasks",
                json={
                    "assigned_to": receiver["agent_number"],
                    "from_agent_number": sender["agent_number"],
                    "payload": {"kind": "echo"},
                    **fields,
                },
                headers=headers,
            )
            assert created.status_code == 201
            task = created.json()
            task_id = task["task_id"]
            message_id = task["message_id"]

            # ---- store 1: Message.content is the full ciphertext envelope
            async with SessionLocal() as s:
                row = (
                    await s.execute(
                        select(Message).where(Message.message_id == message_id)
                    )
                ).scalar_one()
                content_db = row.content
            assert content_db["security"]["mode"] == "e2ee"
            assert PLAINTEXT_MARKER not in json.dumps(content_db)

            # ---- store 2: ws:session_pending holds the exact delivery
            # string built from that content (security block copied
            # verbatim by the platform; payload is the same envelope).
            agent_key = f"ws:session_pending:{receiver['agent_id']}:{receiver['agent_id']}"
            queue = server.redis.lists.get(agent_key) or []
            assert len(queue) == 1
            queued_string = queue[0]
            queued = json.loads(queued_string)
            assert queued["type"] == MessageType.TASK_REQUEST.value
            assert queued["message_id"] == message_id
            # ws_payload["payload"] is the stored envelope verbatim
            assert queued["payload"] == content_db
            # the marker block was copied, never constructed
            assert queued["security"] == content_db["security"]
            assert PLAINTEXT_MARKER not in queued_string

            # ---- receiver SDK: offline, then connect and decrypt
            store = SessionStore(str(_tmp_session_path(f"e2e-{suffix}.json")))
            ws = AgentWebSocket(
                store,
                kem_private_key=recv_kem_priv,
                signing_private_key=recv_sig_priv,
            )
            delivered_raws: list[str] = []
            original_handle = ws._handle

            async def recording_handle(raw):
                try:
                    if json.loads(raw).get("type") == MessageType.TASK_REQUEST.value:
                        delivered_raws.append(raw)
                except json.JSONDecodeError:
                    pass
                await original_handle(raw)

            ws._handle = recording_handle

            handler_calls: list[dict[str, Any]] = []

            async def on_task_request(msg):
                handler_calls.append(msg)
                body = {"task_id": msg["task_id"], "result": {"echo": msg["payload"]}}
                sealed_reply = ws.seal_reply(msg["task_id"], body)
                assert sealed_reply is not None
                await ws.send_message(
                    MessageType.TASK_RESULT,
                    {"task_id": msg["task_id"]},
                    sealed=sealed_reply,
                )

            ws.on_task_request(on_task_request)

            await ws.connect(
                server.ws_url, f"e2e-resume-{suffix}", receiver["agent_token"]
            )

            # the delivered string is byte-identical to the queued one
            await _wait_for(lambda: len(delivered_raws) >= 1)
            assert delivered_raws[0] == queued_string

            # the task reaches completed via the sealed result write-back
            async with httpx.AsyncClient(base_url=server.base_url) as poll_client:
                await _wait_for_status(poll_client, task_id, headers, "completed")
                task_resp = await poll_client.get(f"/v1/tasks/{task_id}", headers=headers)
                assert task_resp.status_code == 200
                result = task_resp.json()["result"]
                # read-side view of the sealed write-back
                assert result["encrypted"] is True
                assert PLAINTEXT_MARKER not in json.dumps(result)

            # the handler saw the decrypted plaintext, exactly once
            assert len(handler_calls) == 1
            assert handler_calls[0]["payload"] == {
                "kind": "echo",
                "text": PLAINTEXT_MARKER,
            }
            # top-level routing fields survived
            assert handler_calls[0]["task_id"] == task_id

            # the sender can open the sealed result: full crypto round trip
            reply_sealed = SealedMessage.from_envelope_fields(
                {
                    "security": result["security"],
                    "encrypted_payload": result["encrypted_payload"],
                    "aad": result["aad"],
                }
            )
            reply_plain = open_message(
                reply_sealed,
                recipient_kem_private_key=sender_kem_priv,
                sender_signing_public_key=recv_sig_pub,
            )
            assert reply_plain is not None
            reply_body = json.loads(reply_plain.decode("utf-8"))
            assert reply_body["result"]["echo"]["text"] == PLAINTEXT_MARKER

            # ---- reconnect with a re-injected un-acked copy: the
            # platform replays the identical string; the SDK accepts it
            # exactly once (message_id idempotency), re-acks, and never
            # re-invokes the handler.
            await ws.disconnect()
            await server.redis.lpush(agent_key, queued_string)
            await ws.connect(
                server.ws_url, f"e2e-resume-{suffix}", receiver["agent_token"]
            )

            await _wait_for(lambda: len(delivered_raws) >= 2)
            assert delivered_raws[1] == queued_string
            await _wait_for(lambda: not server.redis.lists.get(agent_key))
            assert len(handler_calls) == 1

            await ws.disconnect()


def _task_status_sync(client: httpx.AsyncClient, task_id: str, headers) -> str:
    """Synchronous wrapper for use inside _wait_for predicates.

    Runs the coroutine on the running loop via a helper task.
    """
    import asyncio

    async def _fetch():
        return await _task_status(client, task_id, headers)

    return asyncio.ensure_future(_fetch())


@pytest.mark.anyio
async def test_e2ee_decrypt_failure_terminates_task_failed(monkeypatch):
    await _reset_circuit_breakers()

    from agentnet.session_store import SessionStore
    from agentnet.websocket import AgentWebSocket

    async with run_live_server(monkeypatch) as server:
        async with httpx.AsyncClient(base_url=server.base_url) as client:
            suffix = uuid.uuid4().hex[:8]
            register = await client.post(
                "/v1/auth/register",
                json={"username": f"e2ee-fail-{suffix}", "key_name": "e2ee"},
            )
            assert register.status_code == 200
            api_key = register.json()["api_key"]
            headers = {"Authorization": f"Bearer {api_key}"}

            sender = await client.post(
                "/v1/agents",
                json={"name": "E2E Sender F", "runtime": "pytest"},
                headers=headers,
            )
            assert sender.status_code == 201
            receiver = await client.post(
                "/v1/agents",
                json={
                    "name": "E2E Receiver F",
                    "runtime": "pytest",
                    "inbound_policy": "public",
                },
                headers=headers,
            )
            assert receiver.status_code == 201
            sender = sender.json()
            receiver = receiver.json()

            # the receiver publishes real keys...
            recv_kem_priv, recv_kem_pub = _kem_keypair()
            recv_sig_priv, recv_sig_pub = _sig_keypair()
            await _publish_receiver_keys(receiver["agent_id"], recv_kem_pub, recv_sig_pub)

            # ...but the sender seals to a DIFFERENT (wrong) recipient
            # key: the envelope is structurally well-formed, so creation
            # succeeds and only the receiver's open() fails.
            _wrong_kem_priv, wrong_kem_pub = _kem_keypair()
            sender_kem_priv, _sender_kem_pub = _kem_keypair()
            sender_sig_priv, _ = _sig_keypair()

            sealed = _seal_for_receiver(
                {"kind": "echo", "text": PLAINTEXT_MARKER},
                recipient_kem=wrong_kem_pub,
                recipient_sig=recv_sig_pub,
                sender_kem_priv=sender_kem_priv,
                sender_sig_priv=sender_sig_priv,
                from_number=sender["agent_number"],
                to_number=receiver["agent_number"],
            )
            fields = sealed.to_envelope_fields()

            created = await client.post(
                "/v1/tasks",
                json={
                    "assigned_to": receiver["agent_number"],
                    "from_agent_number": sender["agent_number"],
                    "payload": {"kind": "echo"},
                    **fields,
                },
                headers=headers,
            )
            assert created.status_code == 201
            task = created.json()

            store = SessionStore(str(_tmp_session_path(f"e2e-fail-{suffix}.json")))
            ws = AgentWebSocket(
                store,
                kem_private_key=recv_kem_priv,
                signing_private_key=recv_sig_priv,
            )
            handler_calls: list[dict[str, Any]] = []

            async def on_task_request(msg):
                handler_calls.append(msg)

            ws.on_task_request(on_task_request)
            await ws.connect(
                server.ws_url, f"e2e-fail-{suffix}", receiver["agent_token"]
            )

            async with httpx.AsyncClient(base_url=server.base_url) as poll_client:
                await _wait_for_status(
                    poll_client, task["task_id"], headers, "failed"
                )
                resp = await poll_client.get(
                    f"/v1/tasks/{task['task_id']}", headers=headers
                )
                assert "DECRYPT_FAILED" in resp.json()["error_message"]

            # the handler never ran on unverifiable bytes
            assert handler_calls == []
            await ws.disconnect()
