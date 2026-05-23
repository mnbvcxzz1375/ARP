"""Phase Web 4: User Dashboard API — endpoint tests."""
import hashlib
import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.agent_token import AgentToken
from app.models.api_key import ApiKey
from app.models.task import Task
from app.models.approval import Approval
from app.models.connection import Connection
from app.models.user import User
from app.models.audit_log import AuditLog


@pytest.fixture(autouse=True)
def _mock_dashboard_redis():
    """Mock Redis used by dashboard_service (imported directly, not covered by conftest)."""
    mock = AsyncMock()
    mock.exists = AsyncMock(return_value=0)
    mock.get = AsyncMock(return_value=None)
    mock.setex = AsyncMock(return_value=None)
    with patch("app.services.dashboard_service.redis_client", mock):
        yield mock


@pytest.fixture
async def dashboard_user(session: AsyncSession):
    """Create a user with an API key and an agent for dashboard testing."""
    user = User(
        id=uuid.uuid4(),
        username=f"dash-user-{uuid.uuid4().hex[:8]}",
    )
    session.add(user)
    await session.flush()

    api_key = ApiKey(
        id=uuid.uuid4(),
        user_id=user.id,
        key_hash=hashlib.sha256(b"dash-key-12345").hexdigest(),
        key_prefix="ak_dash",
        name="dash-key",
    )
    session.add(api_key)
    await session.flush()

    # Use the service to create an agent (auto-generates token)
    from app.services.agent_service import create_agent as _create_agent_service
    agent = await _create_agent_service(
        session, user, name="dash-agent", runtime="python", inbound_policy="public",
    )
    await session.flush()

    return user, api_key, agent, b"dash-key-12345"


@pytest.fixture
async def other_user(session: AsyncSession):
    """Create a different user for cross-user isolation tests."""
    user = User(
        id=uuid.uuid4(),
        username=f"other-user-{uuid.uuid4().hex[:8]}",
    )
    session.add(user)
    await session.flush()

    api_key = ApiKey(
        id=uuid.uuid4(),
        user_id=user.id,
        key_hash=hashlib.sha256(b"other-key-12345").hexdigest(),
        key_prefix="ak_other",
        name="other-key",
    )
    session.add(api_key)
    await session.flush()

    return user, api_key, b"other-key-12345"


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

async def login(client: AsyncClient, username: str, api_key: str):
    """Login and return the response. Sets session cookie on client."""
    resp = await client.post("/v1/dashboard/auth/login", json={
        "username": username,
        "api_key": api_key,
    })
    return resp


def make_approval(agent_id, task_id, **overrides):
    """Create an Approval with correct field types (action_preview is String)."""
    kwargs = {
        "id": uuid.uuid4(),
        "agent_id": agent_id,
        "task_id": task_id,
        "status": "pending",
        "risk_level": "medium",
        "action_kind": "execute_command",
        "action_preview": '{"cmd": "ls -la"}',
    }
    kwargs.update(overrides)
    return Approval(**kwargs)


def csrf_headers(client):
    """Build X-CSRF-Token header from the CSRF cookie stored on the client."""
    csrf = client.cookies.get("agentnet_csrf")
    if csrf:
        return {"X-CSRF-Token": csrf}
    return {}


# ──────────────────────────────────────────────────────────────────
# Overview
# ──────────────────────────────────────────────────────────────────

class TestOverview:
    async def test_overview_returns_kpis(self, client: AsyncClient, dashboard_user):
        user, _, _, plain_key = dashboard_user
        resp = await login(client, user.username, plain_key.decode())
        assert resp.status_code == 200

        resp = await client.get("/v1/dashboard/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert "online_agents" in data
        assert "tasks_today" in data
        assert "pending_approvals" in data
        assert "failed_tasks" in data
        assert "pending_messages" in data
        assert "recent_tasks" in data
        assert data["online_agents"] == 0  # no Redis presence

    async def test_overview_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/v1/dashboard/overview")
        assert resp.status_code == 401


# ──────────────────────────────────────────────────────────────────
# Agent CRUD
# ──────────────────────────────────────────────────────────────────

class TestAgentEndpoints:
    async def test_list_agents_returns_own_agents(self, client: AsyncClient, dashboard_user):
        user, _, agent, plain_key = dashboard_user
        await login(client, user.username, plain_key.decode())
        resp = await client.get("/v1/dashboard/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any(a["agent_id"] == str(agent.id) for a in data["agents"])

    async def test_list_agents_pagination(self, client: AsyncClient, dashboard_user):
        user, _, _, plain_key = dashboard_user
        await login(client, user.username, plain_key.decode())
        resp = await client.get("/v1/dashboard/agents?page=1&page_size=1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 1

    async def test_list_agents_search(self, client: AsyncClient, dashboard_user):
        user, _, agent, plain_key = dashboard_user
        await login(client, user.username, plain_key.decode())
        resp = await client.get(f"/v1/dashboard/agents?search={agent.name}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    async def test_create_agent(self, client: AsyncClient, dashboard_user):
        user, _, _, plain_key = dashboard_user
        await login(client, user.username, plain_key.decode())
        resp = await client.post("/v1/dashboard/agents", json={
            "name": "new-agent",
            "runtime": "openclaw",
            "inbound_policy": "public",
        }, headers=csrf_headers(client))
        assert resp.status_code == 201
        data = resp.json()
        assert "agent_id" in data
        assert "agent_number" in data
        assert "agent_token" in data
        assert data["agent_token"].startswith("agt_sk_")
        assert data["name"] == "new-agent"

    async def test_create_agent_with_all_fields(self, client: AsyncClient, dashboard_user):
        user, _, _, plain_key = dashboard_user
        await login(client, user.username, plain_key.decode())
        resp = await client.post("/v1/dashboard/agents", json={
            "name": "full-agent",
            "runtime": "python",
            "inbound_policy": "contacts_only",
            "discoverable": True,
            "capabilities": ["chat", "tool_use"],
        }, headers=csrf_headers(client))
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "full-agent"

    async def test_agent_detail(self, client: AsyncClient, dashboard_user):
        user, _, agent, plain_key = dashboard_user
        await login(client, user.username, plain_key.decode())
        resp = await client.get(f"/v1/dashboard/agents/{agent.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_id"] == str(agent.id)
        assert data["name"] == agent.name
        # No Redis presence → status is offline
        assert data["status"] == "offline"

    async def test_agent_detail_online_when_present(self, client: AsyncClient, dashboard_user):
        """When Redis presence key exists, detail endpoint returns status=online."""
        from app.services import dashboard_service

        user, _, agent, plain_key = dashboard_user
        original_exists = dashboard_service.redis_client.exists
        dashboard_service.redis_client.exists = AsyncMock(return_value=1)
        try:
            await login(client, user.username, plain_key.decode())
            resp = await client.get(f"/v1/dashboard/agents/{agent.id}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "online"
        finally:
            dashboard_service.redis_client.exists = original_exists

    async def test_agent_detail_404_for_other_user(self, client: AsyncClient, dashboard_user, other_user, session):
        user, _, _, plain_key = dashboard_user
        other, _, _ = other_user
        other_agent = Agent(
            id=uuid.uuid4(),
            owner_id=other.id,
            agent_number=f"AN-GLOBAL-{uuid.uuid4().hex[:10].upper()}-YY",
            name="other-agent",
            runtime="python",
        )
        session.add(other_agent)
        await session.flush()

        await login(client, user.username, plain_key.decode())
        resp = await client.get(f"/v1/dashboard/agents/{other_agent.id}")
        assert resp.status_code == 404

    async def test_agent_detail_404_invalid_uuid(self, client: AsyncClient, dashboard_user):
        user, _, _, plain_key = dashboard_user
        await login(client, user.username, plain_key.decode())
        resp = await client.get("/v1/dashboard/agents/not-a-uuid")
        assert resp.status_code in (404, 422)

    async def test_update_agent(self, client: AsyncClient, dashboard_user, session: AsyncSession):
        user, _, agent, plain_key = dashboard_user
        await login(client, user.username, plain_key.decode())
        resp = await client.patch(f"/v1/dashboard/agents/{agent.id}", json={
            "name": "updated-name",
        }, headers=csrf_headers(client))
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_id"] == str(agent.id)

        # Verify audit log entry
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.action == "dashboard.agent.update",
                AuditLog.actor_id == str(user.id),
            )
        )
        logs = list(result.scalars().all())
        assert len(logs) >= 1

    async def test_update_agent_inbound_policy(self, client: AsyncClient, dashboard_user):
        user, _, agent, plain_key = dashboard_user
        await login(client, user.username, plain_key.decode())
        resp = await client.patch(f"/v1/dashboard/agents/{agent.id}", json={
            "inbound_policy": "contacts_only",
        }, headers=csrf_headers(client))
        assert resp.status_code == 200

    async def test_update_agent_404_for_other_user(self, client: AsyncClient, dashboard_user, other_user, session):
        user, _, _, plain_key = dashboard_user
        other, _, _ = other_user
        other_agent = Agent(
            id=uuid.uuid4(),
            owner_id=other.id,
            agent_number=f"AN-GLOBAL-{uuid.uuid4().hex[:10].upper()}-UPD",
            name="other-agent-upd",
            runtime="python",
        )
        session.add(other_agent)
        await session.flush()

        await login(client, user.username, plain_key.decode())
        resp = await client.patch(f"/v1/dashboard/agents/{other_agent.id}", json={
            "name": "hacked",
        }, headers=csrf_headers(client))
        assert resp.status_code == 404

    async def test_delete_agent(self, client: AsyncClient, dashboard_user, session):
        user, _, _, plain_key = dashboard_user
        # Create a separate agent to delete using the service
        from app.services.agent_service import create_agent as _create_agent_service
        new_agent = await _create_agent_service(
            session, user, name="to-delete", runtime="python",
        )
        await session.flush()

        await login(client, user.username, plain_key.decode())
        resp = await client.delete(f"/v1/dashboard/agents/{new_agent.id}", headers=csrf_headers(client))
        assert resp.status_code == 204

        # Verify agent is gone
        resp2 = await client.get(f"/v1/dashboard/agents/{new_agent.id}")
        assert resp2.status_code == 404

    async def test_delete_agent_404_for_other_user(self, client: AsyncClient, dashboard_user, other_user, session):
        user, _, _, plain_key = dashboard_user
        other, _, _ = other_user
        other_agent = Agent(
            id=uuid.uuid4(),
            owner_id=other.id,
            agent_number=f"AN-GLOBAL-{uuid.uuid4().hex[:10].upper()}-DEL",
            name="other-agent-del",
            runtime="python",
        )
        session.add(other_agent)
        await session.flush()

        await login(client, user.username, plain_key.decode())
        resp = await client.delete(f"/v1/dashboard/agents/{other_agent.id}", headers=csrf_headers(client))
        assert resp.status_code == 404

    async def test_rotate_token(self, client: AsyncClient, dashboard_user):
        user, _, agent, plain_key = dashboard_user
        await login(client, user.username, plain_key.decode())
        resp = await client.post(f"/v1/dashboard/agents/{agent.id}/rotate-token", headers=csrf_headers(client))
        assert resp.status_code == 200
        data = resp.json()
        assert "agent_token" in data
        assert data["agent_token"].startswith("agt_sk_")
        assert data["agent_id"] == str(agent.id)

    async def test_rotate_token_404_for_other_user(self, client: AsyncClient, dashboard_user, other_user, session):
        user, _, _, plain_key = dashboard_user
        other, _, _ = other_user
        other_agent = Agent(
            id=uuid.uuid4(),
            owner_id=other.id,
            agent_number=f"AN-GLOBAL-{uuid.uuid4().hex[:10].upper()}-ROT",
            name="other-agent-rot",
            runtime="python",
        )
        session.add(other_agent)
        await session.flush()

        await login(client, user.username, plain_key.decode())
        resp = await client.post(f"/v1/dashboard/agents/{other_agent.id}/rotate-token", headers=csrf_headers(client))
        assert resp.status_code == 404


# ──────────────────────────────────────────────────────────────────
# Task endpoints
# ──────────────────────────────────────────────────────────────────

class TestTaskEndpoints:
    async def test_list_tasks_returns_own_tasks(self, client: AsyncClient, dashboard_user, session):
        user, _, agent, plain_key = dashboard_user
        task = Task(
            id=uuid.uuid4(),
            created_by=agent.id,
            assigned_to=agent.id,
            status="completed",
        )
        session.add(task)
        await session.flush()

        await login(client, user.username, plain_key.decode())
        resp = await client.get("/v1/dashboard/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["tasks"]) >= 1
        assert data["tasks"][0]["task_id"] == str(task.id)

    async def test_list_tasks_with_status_filter(self, client: AsyncClient, dashboard_user, session):
        user, _, agent, plain_key = dashboard_user
        task = Task(
            id=uuid.uuid4(),
            created_by=agent.id,
            assigned_to=agent.id,
            status="failed",
        )
        session.add(task)
        await session.flush()

        await login(client, user.username, plain_key.decode())
        resp = await client.get("/v1/dashboard/tasks?status_filter=completed")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0  # only failed task exists

    async def test_list_tasks_pagination(self, client: AsyncClient, dashboard_user, session):
        user, _, agent, plain_key = dashboard_user
        task = Task(
            id=uuid.uuid4(),
            created_by=agent.id,
            assigned_to=agent.id,
            status="completed",
        )
        session.add(task)
        await session.flush()

        await login(client, user.username, plain_key.decode())
        resp = await client.get("/v1/dashboard/tasks?offset=0&limit=1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 1

    async def test_task_detail(self, client: AsyncClient, dashboard_user, session):
        user, _, agent, plain_key = dashboard_user
        task = Task(
            id=uuid.uuid4(),
            created_by=agent.id,
            assigned_to=agent.id,
            status="running",
            error_message=None,
        )
        session.add(task)
        await session.flush()

        await login(client, user.username, plain_key.decode())
        resp = await client.get(f"/v1/dashboard/tasks/{task.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == str(task.id)
        assert data["status"] == "running"

    async def test_task_detail_404_for_other_user(self, client: AsyncClient, dashboard_user, other_user, session):
        user, _, _, plain_key = dashboard_user
        other, _, _ = other_user
        other_agent = Agent(
            id=uuid.uuid4(),
            owner_id=other.id,
            agent_number=f"AN-GLOBAL-{uuid.uuid4().hex[:10].upper()}-AA",
            name="other-agent-2",
            runtime="python",
        )
        session.add(other_agent)
        await session.flush()

        other_task = Task(
            id=uuid.uuid4(),
            created_by=other_agent.id,
            assigned_to=other_agent.id,
            status="completed",
        )
        session.add(other_task)
        await session.flush()

        await login(client, user.username, plain_key.decode())
        resp = await client.get(f"/v1/dashboard/tasks/{other_task.id}")
        assert resp.status_code == 404

    async def test_task_messages_empty(self, client: AsyncClient, dashboard_user, session):
        user, _, agent, plain_key = dashboard_user
        task = Task(
            id=uuid.uuid4(),
            created_by=agent.id,
            assigned_to=agent.id,
            status="completed",
        )
        session.add(task)
        await session.flush()

        await login(client, user.username, plain_key.decode())
        resp = await client.get(f"/v1/dashboard/tasks/{task.id}/messages")
        assert resp.status_code == 200
        data = resp.json()
        assert data["messages"] == []

    async def test_list_tasks_returns_real_delivery_status(self, client: AsyncClient, dashboard_user, session):
        from app.models.message import Message

        user, _, agent, plain_key = dashboard_user
        task = Task(
            id=uuid.uuid4(),
            created_by=agent.id,
            assigned_to=agent.id,
            status="completed",
        )
        session.add(task)
        await session.flush()

        msg = Message(
            id=uuid.uuid4(),
            task_id=task.id,
            message_id="msg-001",
            type="task_result",
            delivery_status="acked",
            retry_count=2,
        )
        session.add(msg)
        await session.flush()

        await login(client, user.username, plain_key.decode())
        resp = await client.get("/v1/dashboard/tasks")
        assert resp.status_code == 200
        data = resp.json()
        task_data = next(t for t in data["tasks"] if t["task_id"] == str(task.id))
        assert task_data["delivery_status"] == "acked"

    async def test_task_detail_returns_real_delivery_status(self, client: AsyncClient, dashboard_user, session):
        from app.models.message import Message

        user, _, agent, plain_key = dashboard_user
        task = Task(
            id=uuid.uuid4(),
            created_by=agent.id,
            assigned_to=agent.id,
            status="completed",
        )
        session.add(task)
        await session.flush()

        msg = Message(
            id=uuid.uuid4(),
            task_id=task.id,
            message_id="msg-002",
            type="task_result",
            delivery_status="failed",
            retry_count=5,
        )
        session.add(msg)
        await session.flush()

        await login(client, user.username, plain_key.decode())
        resp = await client.get(f"/v1/dashboard/tasks/{task.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["delivery_status"] == "failed"
        assert data["retry_count"] == 5

    async def test_task_detail_returns_unknown_when_no_message(self, client: AsyncClient, dashboard_user, session):
        user, _, agent, plain_key = dashboard_user
        task = Task(
            id=uuid.uuid4(),
            created_by=agent.id,
            assigned_to=agent.id,
            status="completed",
        )
        session.add(task)
        await session.flush()

        await login(client, user.username, plain_key.decode())
        resp = await client.get(f"/v1/dashboard/tasks/{task.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["delivery_status"] == "unknown"
        assert data["retry_count"] == 0

    async def test_task_progress_empty(self, client: AsyncClient, dashboard_user, session):
        user, _, agent, plain_key = dashboard_user
        task = Task(
            id=uuid.uuid4(),
            created_by=agent.id,
            assigned_to=agent.id,
            status="running",
        )
        session.add(task)
        await session.flush()

        await login(client, user.username, plain_key.decode())
        resp = await client.get(f"/v1/dashboard/tasks/{task.id}/progress")
        assert resp.status_code == 200
        data = resp.json()
        assert data["progress"] == []


# ──────────────────────────────────────────────────────────────────
# Approval endpoints
# ──────────────────────────────────────────────────────────────────

class TestApprovalEndpoints:
    async def test_list_approvals_empty(self, client: AsyncClient, dashboard_user):
        user, _, _, plain_key = dashboard_user
        await login(client, user.username, plain_key.decode())
        resp = await client.get("/v1/dashboard/approvals")
        assert resp.status_code == 200
        data = resp.json()
        assert "approvals" in data
        assert data["total"] == 0

    async def test_list_approvals_with_data(self, client: AsyncClient, dashboard_user, session):
        user, _, agent, plain_key = dashboard_user
        # Create a task first (Approval.task_id is NOT NULL)
        task = Task(
            id=uuid.uuid4(),
            created_by=agent.id,
            assigned_to=agent.id,
            status="awaiting_approval",
        )
        session.add(task)
        await session.flush()

        approval = make_approval(agent_id=agent.id, task_id=task.id)
        session.add(approval)
        await session.flush()

        await login(client, user.username, plain_key.decode())
        resp = await client.get("/v1/dashboard/approvals")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    async def test_accept_approval(self, client: AsyncClient, dashboard_user, session):
        user, _, agent, plain_key = dashboard_user
        task = Task(id=uuid.uuid4(), created_by=agent.id, assigned_to=agent.id, status="awaiting_approval")
        session.add(task)
        await session.flush()

        approval = make_approval(agent_id=agent.id, task_id=task.id)
        session.add(approval)
        await session.flush()

        await login(client, user.username, plain_key.decode())
        resp = await client.post(f"/v1/dashboard/approvals/{approval.id}/accept", headers=csrf_headers(client))
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "accepted"

        # Verify audit log entry
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.action == "dashboard.approval.accept",
                AuditLog.actor_id == str(user.id),
            )
        )
        logs = list(result.scalars().all())
        assert len(logs) == 1
        assert logs[0].actor_type == "user"

    async def test_reject_approval(self, client: AsyncClient, dashboard_user, session):
        user, _, agent, plain_key = dashboard_user
        task = Task(id=uuid.uuid4(), created_by=agent.id, assigned_to=agent.id, status="awaiting_approval")
        session.add(task)
        await session.flush()

        approval = make_approval(agent_id=agent.id, task_id=task.id)
        session.add(approval)
        await session.flush()

        await login(client, user.username, plain_key.decode())
        resp = await client.post(f"/v1/dashboard/approvals/{approval.id}/reject", headers=csrf_headers(client))
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "rejected"

    async def test_approval_404_for_other_user(self, client: AsyncClient, dashboard_user, other_user, session):
        user, _, _, plain_key = dashboard_user
        other, _, _ = other_user
        other_agent = Agent(
            id=uuid.uuid4(),
            owner_id=other.id,
            agent_number=f"AN-GLOBAL-{uuid.uuid4().hex[:10].upper()}-APP",
            name="other-agent-app",
            runtime="python",
        )
        session.add(other_agent)
        await session.flush()

        other_task = Task(
            id=uuid.uuid4(),
            created_by=other_agent.id,
            assigned_to=other_agent.id,
            status="awaiting_approval",
        )
        session.add(other_task)
        await session.flush()

        other_approval = make_approval(agent_id=other_agent.id, task_id=other_task.id)
        session.add(other_approval)
        await session.flush()

        await login(client, user.username, plain_key.decode())
        resp = await client.post(f"/v1/dashboard/approvals/{other_approval.id}/accept", headers=csrf_headers(client))
        assert resp.status_code == 404


# ──────────────────────────────────────────────────────────────────
# Connection endpoints
# NOTE: The Connection model uses from_agent_id/to_agent_id columns,
# but the dashboard_user router references agent_id/requester_agent_id/
# agent_number/requested_policy which do not exist on the model.
# These endpoints are broken until the model and router are aligned.
# Tests are skipped pending model-router alignment.
# ──────────────────────────────────────────────────────────────────

class TestConnectionEndpoints:
    async def test_connections_returns_agents(self, client: AsyncClient, dashboard_user):
        user, _, agent, plain_key = dashboard_user
        await login(client, user.username, plain_key.decode())
        resp = await client.get("/v1/dashboard/connections")
        assert resp.status_code == 200
        data = resp.json()
        assert "agents" in data
        assert len(data["agents"]) >= 1
        agent_info = data["agents"][0]
        assert agent_info["agent_id"] == str(agent.id)
        assert agent_info["agent_number"] == agent.agent_number
        assert agent_info["inbound_policy"] == agent.inbound_policy
        assert "pending_requests" in agent_info
        assert "accepted_connections" in agent_info
        assert "rejected_connections" in agent_info

    async def test_connections_pending_requests(self, client: AsyncClient, dashboard_user, other_user, session: AsyncSession):
        user, _, user_agent, plain_key = dashboard_user
        other, _, _ = other_user

        requester_agent = Agent(
            id=uuid.uuid4(),
            owner_id=other.id,
            agent_number=f"AN-GLOBAL-{uuid.uuid4().hex[:10].upper()}-REQ",
            name="requester-agent",
            runtime="python",
        )
        session.add(requester_agent)
        await session.flush()

        conn = Connection(
            id=uuid.uuid4(),
            from_agent_id=requester_agent.id,
            to_agent_id=user_agent.id,
            status="pending",
        )
        session.add(conn)
        await session.flush()

        await login(client, user.username, plain_key.decode())
        resp = await client.get("/v1/dashboard/connections")
        assert resp.status_code == 200
        data = resp.json()
        assert "pending_requests" in data
        assert len(data["pending_requests"]) == 1
        req = data["pending_requests"][0]
        assert req["agent_number"] == requester_agent.agent_number
        assert req["requester_agent"] == str(requester_agent.id)

    async def test_accept_connection(self, client: AsyncClient, dashboard_user, other_user, session: AsyncSession):
        user, _, user_agent, plain_key = dashboard_user
        other, _, _ = other_user

        requester_agent = Agent(
            id=uuid.uuid4(),
            owner_id=other.id,
            agent_number=f"AN-GLOBAL-{uuid.uuid4().hex[:10].upper()}-ACC",
            name="req-agent",
            runtime="python",
        )
        session.add(requester_agent)
        await session.flush()

        conn = Connection(
            id=uuid.uuid4(),
            from_agent_id=requester_agent.id,
            to_agent_id=user_agent.id,
            status="pending",
        )
        session.add(conn)
        await session.flush()

        await login(client, user.username, plain_key.decode())
        resp = await client.post(f"/v1/dashboard/connections/{conn.id}/accept", headers=csrf_headers(client))
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "accepted"

        # Verify audit log entry
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.action == "dashboard.connection.accept",
                AuditLog.actor_id == str(user.id),
            )
        )
        logs = list(result.scalars().all())
        assert len(logs) >= 1
        assert logs[0].actor_type == "user"

    async def test_reject_connection(self, client: AsyncClient, dashboard_user, other_user, session: AsyncSession):
        user, _, user_agent, plain_key = dashboard_user
        other, _, _ = other_user

        requester_agent = Agent(
            id=uuid.uuid4(),
            owner_id=other.id,
            agent_number=f"AN-GLOBAL-{uuid.uuid4().hex[:10].upper()}-REJ",
            name="req-agent",
            runtime="python",
        )
        session.add(requester_agent)
        await session.flush()

        conn = Connection(
            id=uuid.uuid4(),
            from_agent_id=requester_agent.id,
            to_agent_id=user_agent.id,
            status="pending",
        )
        session.add(conn)
        await session.flush()

        await login(client, user.username, plain_key.decode())
        resp = await client.post(f"/v1/dashboard/connections/{conn.id}/reject", headers=csrf_headers(client))
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "rejected"

    async def test_connection_404_for_other_user(self, client: AsyncClient, dashboard_user, other_user, session: AsyncSession):
        user, _, _, plain_key = dashboard_user
        other, _, _ = other_user

        other_agent = Agent(
            id=uuid.uuid4(),
            owner_id=other.id,
            agent_number=f"AN-GLOBAL-{uuid.uuid4().hex[:10].upper()}-OTH",
            name="other-agent",
            runtime="python",
        )
        session.add(other_agent)
        await session.flush()

        requester = Agent(
            id=uuid.uuid4(),
            owner_id=other.id,
            agent_number=f"AN-GLOBAL-{uuid.uuid4().hex[:10].upper()}-REQ2",
            name="requester",
            runtime="python",
        )
        session.add(requester)
        await session.flush()

        conn = Connection(
            id=uuid.uuid4(),
            from_agent_id=requester.id,
            to_agent_id=other_agent.id,
            status="pending",
        )
        session.add(conn)
        await session.flush()

        await login(client, user.username, plain_key.decode())
        resp = await client.post(f"/v1/dashboard/connections/{conn.id}/accept", headers=csrf_headers(client))
        assert resp.status_code == 404

    async def test_update_firewall(self, client: AsyncClient, dashboard_user, session: AsyncSession):
        user, _, agent, plain_key = dashboard_user
        await login(client, user.username, plain_key.decode())
        resp = await client.patch(
            f"/v1/dashboard/agents/{agent.id}/firewall",
            json={"inbound_policy": "private"},
            headers=csrf_headers(client),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["inbound_policy"] == "private"

        # Verify audit log entry
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.action == "dashboard.firewall.update",
                AuditLog.actor_id == str(user.id),
            )
        )
        logs = list(result.scalars().all())
        assert len(logs) >= 1
        assert logs[0].actor_type == "user"


# ──────────────────────────────────────────────────────────────────
# API Key endpoints
# ──────────────────────────────────────────────────────────────────

class TestApiKeyEndpoints:
    async def test_list_api_keys(self, client: AsyncClient, dashboard_user):
        user, _, _, plain_key = dashboard_user
        await login(client, user.username, plain_key.decode())
        resp = await client.get("/v1/dashboard/api-keys")
        assert resp.status_code == 200
        data = resp.json()
        assert "api_keys" in data
        assert "total" in data

    async def test_create_api_key(self, client: AsyncClient, dashboard_user):
        user, _, _, plain_key = dashboard_user
        resp = await login(client, user.username, plain_key.decode())
        assert resp.status_code == 200, f"Login failed: {resp.text}"

        resp = await client.post("/v1/dashboard/api-keys", json={
            "name": "new-deploy-key",
        }, headers=csrf_headers(client))
        assert resp.status_code == 201
        data = resp.json()
        assert "api_key" in data  # One-time plain key
        assert "api_key_id" in data
        assert "key_prefix" in data
        assert data["name"] == "new-deploy-key"

    async def test_revoke_api_key(self, client: AsyncClient, dashboard_user):
        user, _, _, plain_key = dashboard_user
        await login(client, user.username, plain_key.decode())
        # Create a key first
        create_resp = await client.post("/v1/dashboard/api-keys", json={"name": "revoke-test"}, headers=csrf_headers(client))
        assert create_resp.status_code == 201
        key_id = create_resp.json()["api_key_id"]

        # Revoke it
        resp = await client.post(f"/v1/dashboard/api-keys/{key_id}/revoke", json={"allow_last_key": True}, headers=csrf_headers(client))
        assert resp.status_code == 200
        data = resp.json()
        assert data["api_key_id"] == key_id

    async def test_cannot_revoke_last_key_without_flag(self, client: AsyncClient, dashboard_user):
        user, _, _, plain_key = dashboard_user
        await login(client, user.username, plain_key.decode())

        # First list keys and try revoking
        list_resp = await client.get("/v1/dashboard/api-keys")
        keys = list_resp.json()["api_keys"]
        if keys:
            key_id = keys[0]["api_key_id"]
            resp = await client.post(f"/v1/dashboard/api-keys/{key_id}/revoke", json={"allow_last_key": False}, headers=csrf_headers(client))
            assert resp.status_code == 409


# ──────────────────────────────────────────────────────────────────
# Cross-user isolation
# ──────────────────────────────────────────────────────────────────

class TestCrossUserIsolation:
    """Ensure users cannot access each other's resources via dashboard endpoints."""

    async def test_cannot_see_other_user_agents(self, client: AsyncClient, dashboard_user, other_user, session):
        user, _, _, plain_key = dashboard_user
        other, _, _ = other_user

        # Create agent for other user
        other_agent = Agent(
            id=uuid.uuid4(),
            owner_id=other.id,
            agent_number=f"AN-GLOBAL-{uuid.uuid4().hex[:10].upper()}-BB",
            name="secret-agent",
            runtime="python",
        )
        session.add(other_agent)
        await session.flush()

        # Login as user and list agents
        await login(client, user.username, plain_key.decode())
        resp = await client.get("/v1/dashboard/agents")
        assert resp.status_code == 200
        data = resp.json()
        # Should not see other user's agent
        assert not any(a["name"] == "secret-agent" for a in data["agents"])

    async def test_cannot_see_other_user_tasks(self, client: AsyncClient, dashboard_user, other_user, session):
        user, _, agent, plain_key = dashboard_user
        other, _, _ = other_user
        other_agent = Agent(
            id=uuid.uuid4(),
            owner_id=other.id,
            agent_number=f"AN-GLOBAL-{uuid.uuid4().hex[:10].upper()}-TASK",
            name="other-task-agent",
            runtime="python",
        )
        session.add(other_agent)
        await session.flush()

        other_task = Task(
            id=uuid.uuid4(),
            created_by=other_agent.id,
            assigned_to=other_agent.id,
            status="completed",
        )
        session.add(other_task)
        await session.flush()

        await login(client, user.username, plain_key.decode())
        resp = await client.get("/v1/dashboard/tasks")
        assert resp.status_code == 200
        data = resp.json()
        # Should only see own tasks
        assert not any(t["task_id"] == str(other_task.id) for t in data["tasks"])

    async def test_cannot_access_other_user_approvals(self, client: AsyncClient, dashboard_user, other_user, session):
        user, _, _, plain_key = dashboard_user
        other, _, _ = other_user
        other_agent = Agent(
            id=uuid.uuid4(),
            owner_id=other.id,
            agent_number=f"AN-GLOBAL-{uuid.uuid4().hex[:10].upper()}-APP2",
            name="other-app-agent",
            runtime="python",
        )
        session.add(other_agent)
        await session.flush()

        other_task = Task(
            id=uuid.uuid4(),
            created_by=other_agent.id,
            assigned_to=other_agent.id,
            status="awaiting_approval",
        )
        session.add(other_task)
        await session.flush()

        other_approval = make_approval(agent_id=other_agent.id, task_id=other_task.id)
        session.add(other_approval)
        await session.flush()

        await login(client, user.username, plain_key.decode())
        resp = await client.get("/v1/dashboard/approvals")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0  # should not see other user's approval

    async def test_cannot_see_other_user_api_keys(self, client: AsyncClient, dashboard_user, other_user):
        user, _, _, plain_key = dashboard_user
        other, other_api_key, _ = other_user
        await login(client, user.username, plain_key.decode())
        resp = await client.get("/v1/dashboard/api-keys")
        assert resp.status_code == 200
        data = resp.json()
        # Should not see other user's keys
        for key in data["api_keys"]:
            assert key["key_prefix"] != other_api_key.key_prefix

    async def test_cannot_update_other_user_agent(self, client: AsyncClient, dashboard_user, other_user, session):
        user, _, _, plain_key = dashboard_user
        other, _, _ = other_user
        other_agent = Agent(
            id=uuid.uuid4(),
            owner_id=other.id,
            agent_number=f"AN-GLOBAL-{uuid.uuid4().hex[:10].upper()}-UPD2",
            name="other-agent-upd2",
            runtime="python",
        )
        session.add(other_agent)
        await session.flush()

        await login(client, user.username, plain_key.decode())
        resp = await client.patch(f"/v1/dashboard/agents/{other_agent.id}", json={"name": "hacked"}, headers=csrf_headers(client))
        assert resp.status_code == 404

    async def test_cannot_delete_other_user_agent(self, client: AsyncClient, dashboard_user, other_user, session):
        user, _, _, plain_key = dashboard_user
        other, _, _ = other_user
        other_agent = Agent(
            id=uuid.uuid4(),
            owner_id=other.id,
            agent_number=f"AN-GLOBAL-{uuid.uuid4().hex[:10].upper()}-DEL2",
            name="other-agent-del2",
            runtime="python",
        )
        session.add(other_agent)
        await session.flush()

        await login(client, user.username, plain_key.decode())
        resp = await client.delete(f"/v1/dashboard/agents/{other_agent.id}", headers=csrf_headers(client))
        assert resp.status_code == 404
