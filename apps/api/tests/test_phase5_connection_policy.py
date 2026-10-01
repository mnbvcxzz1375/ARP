"""Phase 5: Connection Policy tests."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.protocol.constants import ErrorCode, TaskStatus, DeliveryStatus
from app.exceptions import DomainException
from app.services.connection_service import negotiate_security_mode


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac





@pytest.fixture
async def user_a_key(client):
    resp = await client.post(
        "/v1/auth/register",
        json={"username": "policy_user_a", "key_name": "a-key"},
    )
    assert resp.status_code == 200
    return resp.json()["api_key"]


@pytest.fixture
async def user_b_key(client):
    resp = await client.post(
        "/v1/auth/register",
        json={"username": "policy_user_b", "key_name": "b-key"},
    )
    assert resp.status_code == 200
    return resp.json()["api_key"]


@pytest.fixture
async def agent_a_private(client, user_a_key):
    resp = await client.post(
        "/v1/agents",
        json={"name": "Agent A Private", "runtime": "test", "inbound_policy": "private"},
        headers={"X-API-Key": user_a_key},
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def agent_b_request_approval(client, user_b_key):
    resp = await client.post(
        "/v1/agents",
        json={"name": "Agent B Approve", "runtime": "test", "inbound_policy": "request_approval"},
        headers={"X-API-Key": user_b_key},
    )
    assert resp.status_code == 201
    return resp.json()


async def _ensure_caller_agent(client, api_key, name="Caller A"):
    """Give the calling user an agent.

    Registration always creates a fresh account (usernames are non-unique
    display labels since migration 0030), so a user can no longer inherit
    an agent that an earlier test created for the same registered name.
    Tests that act as the calling side must create their own sender
    agent instead of relying on cross-test user reuse.
    """
    resp = await client.post(
        "/v1/agents",
        json={"name": name, "runtime": "test"},
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 201
    return resp.json()


class TestSecurityModeNegotiation:
    def test_compatible_modes(self):
        result = negotiate_security_mode(
            ["relay_visible", "relay_encrypted"],
            ["relay_visible", "e2ee"],
        )
        assert result == "relay_visible"

    def test_e2ee_not_implemented_returns_compatible(self):
        result = negotiate_security_mode(
            ["relay_visible", "e2ee"],
            ["relay_visible"],
        )
        assert result == "relay_visible"

    def test_no_compatible_mode_raises(self):
        with pytest.raises(DomainException) as exc_info:
            negotiate_security_mode(
                ["e2ee"],
                ["relay_visible"],
            )
        assert exc_info.value.code == ErrorCode.SECURITY_MODE_NOT_SUPPORTED.value


class TestInboundPolicyPrivate:
    async def test_private_blocks_cross_user(self, client, user_a_key, user_b_key, agent_b_request_approval):
        # Create a private agent for user A
        resp_a = await client.post(
            "/v1/agents",
            json={"name": "Private Agent", "runtime": "test", "inbound_policy": "private"},
            headers={"X-API-Key": user_a_key},
        )
        assert resp_a.status_code == 201
        private_number = resp_a.json()["agent_number"]

        # Now user B (different user) tries to send a task to A's private agent
        resp = await client.post(
            "/v1/tasks",
            json={"assigned_to": private_number, "payload": {}},
            headers={"X-API-Key": user_b_key},
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == ErrorCode.AGENT_FORBIDDEN.value


class TestInboundPolicyRequestApproval:
    async def test_request_approval_creates_pending(self, client, user_a_key, user_b_key):
        await _ensure_caller_agent(client, user_a_key)
        # Agent B (request_approval) for user B
        resp_b = await client.post(
            "/v1/agents",
            json={"name": "B Approve", "runtime": "test", "inbound_policy": "request_approval"},
            headers={"X-API-Key": user_b_key},
        )
        assert resp_b.status_code == 201
        b_number = resp_b.json()["agent_number"]

        # User A sends task to B (different user) -> should create connection request
        resp = await client.post(
            "/v1/tasks",
            json={"assigned_to": b_number, "payload": {}},
            headers={"X-API-Key": user_a_key},
        )
        assert resp.status_code == 202
        assert resp.json()["error"]["code"] == ErrorCode.CONNECTION_APPROVAL_REQUIRED.value
        assert "connection_id" in resp.json()["error"]["details"]

    async def test_accepted_connection_allows_task(self, client, user_a_key, user_b_key):
        await _ensure_caller_agent(client, user_a_key)
        # Agent B (request_approval) for user B
        resp_b = await client.post(
            "/v1/agents",
            json={"name": "B Allow", "runtime": "test", "inbound_policy": "request_approval"},
            headers={"X-API-Key": user_b_key},
        )
        assert resp_b.status_code == 201
        b_number = resp_b.json()["agent_number"]

        # Create connection request from user A (their first agent is auto-created)
        resp_conn = await client.post(
            "/v1/connections/request",
            json={"to_agent_number": b_number},
            headers={"X-API-Key": user_a_key},
        )
        assert resp_conn.status_code == 201
        conn_id = resp_conn.json()["id"]

        # User B accepts the connection
        resp_accept = await client.post(
            f"/v1/connections/{conn_id}/accept",
            headers={"X-API-Key": user_b_key},
        )
        assert resp_accept.status_code == 200
        assert resp_accept.json()["status"] == "accepted"

        # Now user A can create a task to B
        resp = await client.post(
            "/v1/tasks",
            json={"assigned_to": b_number, "payload": {"hello": "world"}},
            headers={"X-API-Key": user_a_key},
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "created"

    async def test_rejected_connection_blocks_task(self, client, user_a_key, user_b_key):
        await _ensure_caller_agent(client, user_a_key)
        # Set up B with request_approval
        resp_b = await client.post(
            "/v1/agents",
            json={"name": "B Reject", "runtime": "test", "inbound_policy": "request_approval"},
            headers={"X-API-Key": user_b_key},
        )
        assert resp_b.status_code == 201
        b_number = resp_b.json()["agent_number"]

        # Create connection request
        resp_conn = await client.post(
            "/v1/connections/request",
            json={"to_agent_number": b_number},
            headers={"X-API-Key": user_a_key},
        )
        conn_id = resp_conn.json()["id"]

        # B rejects the connection
        await client.post(
            f"/v1/connections/{conn_id}/reject",
            headers={"X-API-Key": user_b_key},
        )

        # A tries to send task -> should be blocked with CONNECTION_REJECTED
        resp = await client.post(
            "/v1/tasks",
            json={"assigned_to": b_number, "payload": {}},
            headers={"X-API-Key": user_a_key},
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == ErrorCode.CONNECTION_REJECTED.value


class TestSameOwner:
    async def test_same_owner_always_allowed(self, client, user_a_key):
        # Create two agents for same user
        resp_a1 = await client.post(
            "/v1/agents",
            json={"name": "Agent 1", "runtime": "test", "inbound_policy": "private"},
            headers={"X-API-Key": user_a_key},
        )
        assert resp_a1.status_code == 201
        a1_number = resp_a1.json()["agent_number"]

        resp_a2 = await client.post(
            "/v1/agents",
            json={"name": "Agent 2", "runtime": "test", "inbound_policy": "private"},
            headers={"X-API-Key": user_a_key},
        )
        assert resp_a2.status_code == 201
        a2_number = resp_a2.json()["agent_number"]

        # Agent 2 sends task to Agent 1 (same owner, private policy)
        # Using a1_number as target
        resp = await client.post(
            "/v1/tasks",
            json={"assigned_to": a1_number, "payload": {"test": True}},
            headers={"X-API-Key": user_a_key},
        )
        # Same owner -> should succeed regardless of policy
        assert resp.status_code == 201

    async def test_same_owner_request_approval_allowed(self, client, user_a_key):
        """Same-owner communication bypasses request_approval without a connection."""
        # Create two agents under same user, both with request_approval
        resp_a1 = await client.post(
            "/v1/agents",
            json={"name": "Agent R1", "runtime": "test", "inbound_policy": "request_approval"},
            headers={"X-API-Key": user_a_key},
        )
        assert resp_a1.status_code == 201
        r1_number = resp_a1.json()["agent_number"]

        resp_a2 = await client.post(
            "/v1/agents",
            json={"name": "Agent R2", "runtime": "test", "inbound_policy": "request_approval"},
            headers={"X-API-Key": user_a_key},
        )
        assert resp_a2.status_code == 201
        r2_number = resp_a2.json()["agent_number"]

        # Same-owner task to request_approval agent should succeed without connection
        resp = await client.post(
            "/v1/tasks",
            json={"assigned_to": r1_number, "payload": {"test": True}},
            headers={"X-API-Key": user_a_key},
        )
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"

    async def test_same_owner_contacts_only_allowed(self, client, user_a_key):
        """Same-owner communication bypasses contacts_only without a connection."""
        resp = await client.post(
            "/v1/agents",
            json={"name": "Agent C1", "runtime": "test", "inbound_policy": "contacts_only"},
            headers={"X-API-Key": user_a_key},
        )
        assert resp.status_code == 201
        c1_number = resp.json()["agent_number"]

        resp = await client.post(
            "/v1/agents",
            json={"name": "Agent C2", "runtime": "test", "inbound_policy": "contacts_only"},
            headers={"X-API-Key": user_a_key},
        )
        assert resp.status_code == 201
        c2_number = resp.json()["agent_number"]

        # Same-owner task to contacts_only agent should succeed
        resp = await client.post(
            "/v1/tasks",
            json={"assigned_to": c1_number, "payload": {"test": True}},
            headers={"X-API-Key": user_a_key},
        )
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"

    async def test_self_send_request_approval_allowed(self, client, user_a_key):
        """Agent sending a task to itself with request_approval should succeed."""
        resp = await client.post(
            "/v1/agents",
            json={"name": "Self R", "runtime": "test", "inbound_policy": "request_approval"},
            headers={"X-API-Key": user_a_key},
        )
        assert resp.status_code == 201
        agent_number = resp.json()["agent_number"]

        # Self-send task (same agent)
        resp = await client.post(
            "/v1/tasks",
            json={
                "assigned_to": agent_number,
                "from_agent_number": agent_number,
                "payload": {"test": True},
            },
            headers={"X-API-Key": user_a_key},
        )
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"


class TestConnectionAPI:
    async def test_request_connection(self, client, user_a_key, user_b_key):
        await _ensure_caller_agent(client, user_a_key)
        resp_b = await client.post(
            "/v1/agents",
            json={"name": "Target", "runtime": "test"},
            headers={"X-API-Key": user_b_key},
        )
        b_number = resp_b.json()["agent_number"]

        resp = await client.post(
            "/v1/connections/request",
            json={
                "to_agent_number": b_number,
                "reason": "Testing",
                "requested_capabilities": ["code_analysis"],
            },
            headers={"X-API-Key": user_a_key},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"
        assert "id" in data

    async def test_list_connections(self, client, user_a_key, user_b_key):
        await _ensure_caller_agent(client, user_a_key)
        resp_b = await client.post(
            "/v1/agents",
            json={"name": "Target2", "runtime": "test"},
            headers={"X-API-Key": user_b_key},
        )
        b_number = resp_b.json()["agent_number"]

        await client.post(
            "/v1/connections/request",
            json={"to_agent_number": b_number},
            headers={"X-API-Key": user_a_key},
        )

        resp = await client.get(
            "/v1/connections",
            headers={"X-API-Key": user_a_key},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["connections"]) >= 1

    async def test_accept_connection(self, client, user_a_key, user_b_key):
        await _ensure_caller_agent(client, user_a_key)
        resp_b = await client.post(
            "/v1/agents",
            json={"name": "Target3", "runtime": "test"},
            headers={"X-API-Key": user_b_key},
        )
        b_number = resp_b.json()["agent_number"]

        resp_conn = await client.post(
            "/v1/connections/request",
            json={"to_agent_number": b_number},
            headers={"X-API-Key": user_a_key},
        )
        conn_id = resp_conn.json()["id"]

        resp = await client.post(
            f"/v1/connections/{conn_id}/accept",
            json={"allowed_capabilities": ["code_analysis"]},
            headers={"X-API-Key": user_b_key},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "accepted"
        assert resp.json()["allowed_capabilities"] == ["code_analysis"]

    async def test_reject_connection(self, client, user_a_key, user_b_key):
        await _ensure_caller_agent(client, user_a_key)
        resp_b = await client.post(
            "/v1/agents",
            json={"name": "Target4", "runtime": "test"},
            headers={"X-API-Key": user_b_key},
        )
        b_number = resp_b.json()["agent_number"]

        resp_conn = await client.post(
            "/v1/connections/request",
            json={"to_agent_number": b_number},
            headers={"X-API-Key": user_a_key},
        )
        conn_id = resp_conn.json()["id"]

        resp = await client.post(
            f"/v1/connections/{conn_id}/reject",
            json={"reason": "not interested"},
            headers={"X-API-Key": user_b_key},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    async def test_connection_requires_auth(self, client):
        resp = await client.post("/v1/connections/request", json={"to_agent_number": "AN-GLOBAL-X"})
        assert resp.status_code == 401
class TestInboundPolicyContactsOnly:
    """Tests for InboundPolicy.CONTACTS_ONLY."""

    async def test_contacts_only_blocks_stranger(self, client, user_a_key, user_b_key):
        await _ensure_caller_agent(client, user_a_key)
        # Agent B (contacts_only) for user B
        resp_b = await client.post(
            "/v1/agents",
            json={"name": "B Contacts", "runtime": "test", "inbound_policy": "contacts_only"},
            headers={"X-API-Key": user_b_key},
        )
        assert resp_b.status_code == 201
        b_number = resp_b.json()["agent_number"]

        # User A (stranger) tries to send task -> should be blocked
        resp = await client.post(
            "/v1/tasks",
            json={"assigned_to": b_number, "payload": {}},
            headers={"X-API-Key": user_a_key},
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == ErrorCode.CONNECTION_APPROVAL_REQUIRED.value

    async def test_contacts_only_allows_existing_connection(self, client, user_a_key, user_b_key):
        await _ensure_caller_agent(client, user_a_key)
        # Agent B (contacts_only) for user B
        resp_b = await client.post(
            "/v1/agents",
            json={"name": "B Contacts 2", "runtime": "test", "inbound_policy": "contacts_only"},
            headers={"X-API-Key": user_b_key},
        )
        assert resp_b.status_code == 201
        b_number = resp_b.json()["agent_number"]

        # Create an accepted connection first (user B accepts user A)
        resp_conn = await client.post(
            "/v1/connections/request",
            json={"to_agent_number": b_number},
            headers={"X-API-Key": user_a_key},
        )
        conn_id = resp_conn.json()["id"]

        await client.post(
            f"/v1/connections/{conn_id}/accept",
            headers={"X-API-Key": user_b_key},
        )

        # Now user A sends task -> should be allowed (existing contact)
        resp = await client.post(
            "/v1/tasks",
            json={"assigned_to": b_number, "payload": {"test": True}},
            headers={"X-API-Key": user_a_key},
        )
        assert resp.status_code == 201


class TestInboundPolicyPublic:
    """Tests for InboundPolicy.PUBLIC."""

    async def test_public_allows_cross_user(self, client, user_a_key, user_b_key):
        await _ensure_caller_agent(client, user_a_key)
        # Agent B (public) for user B
        resp_b = await client.post(
            "/v1/agents",
            json={"name": "B Public", "runtime": "test", "inbound_policy": "public"},
            headers={"X-API-Key": user_b_key},
        )
        assert resp_b.status_code == 201
        b_number = resp_b.json()["agent_number"]

        # User A sends task to B (public) -> should succeed without connection
        resp = await client.post(
            "/v1/tasks",
            json={"assigned_to": b_number, "payload": {"test": True}},
            headers={"X-API-Key": user_a_key},
        )
        assert resp.status_code == 201

    async def test_public_any_authenticated_can_connect(self, client, user_a_key, user_b_key):
        await _ensure_caller_agent(client, user_a_key)
        # Agent B (public) for user B
        resp_b = await client.post(
            "/v1/agents",
            json={"name": "B Public 2", "runtime": "test", "inbound_policy": "public"},
            headers={"X-API-Key": user_b_key},
        )
        assert resp_b.status_code == 201
        b_number = resp_b.json()["agent_number"]

        # Connection request to a public agent should succeed immediately
        resp = await client.post(
            "/v1/connections/request",
            json={"to_agent_number": b_number, "reason": "Testing public"},
            headers={"X-API-Key": user_a_key},
        )
        # Public agent: connection request should auto-accept (200 or 201)
        assert resp.status_code in (200, 201)