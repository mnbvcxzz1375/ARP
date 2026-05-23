"""Phase Web 5: Admin Dashboard API -- endpoint tests."""
import hashlib
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.api_key import ApiKey
from app.models.user import User, UserRole


@pytest.fixture(autouse=True)
def _mock_admin_redis():
    """Mock Redis used by admin_service (get_admin_overview_kpis checks agent presence)."""
    mock = AsyncMock()
    mock.exists = AsyncMock(return_value=0)
    mock.ping = AsyncMock(return_value=True)
    mock.get = AsyncMock(return_value=None)
    mock.setex = AsyncMock(return_value=None)
    with patch("app.services.admin_service.redis_client", mock):
        yield mock


@pytest.fixture
async def admin_user(session: AsyncSession):
    """Create a super_admin user for admin API testing."""
    user = User(
        id=uuid.uuid4(),
        username=f"admin-{uuid.uuid4().hex[:8]}",
        role=UserRole.SUPER_ADMIN.value,
    )
    session.add(user)
    await session.flush()

    api_key = ApiKey(
        id=uuid.uuid4(),
        user_id=user.id,
        key_hash=hashlib.sha256(b"admin-key-12345").hexdigest(),
        key_prefix="ak_admin",
        name="admin-key",
    )
    session.add(api_key)
    await session.flush()
    return user, api_key, b"admin-key-12345"


@pytest.fixture
async def regular_user(session: AsyncSession):
    """Create a regular user (should not have admin access)."""
    user = User(
        id=uuid.uuid4(),
        username=f"regular-{uuid.uuid4().hex[:8]}",
        role=UserRole.USER.value,
    )
    session.add(user)
    await session.flush()

    api_key = ApiKey(
        id=uuid.uuid4(),
        user_id=user.id,
        key_hash=hashlib.sha256(b"regular-key-12345").hexdigest(),
        key_prefix="ak_reg",
        name="regular-key",
    )
    session.add(api_key)
    await session.flush()
    return user, api_key, b"regular-key-12345"


async def login(client: AsyncClient, username: str, api_key: str):
    """Login and return response. Sets session cookie on client."""
    return await client.post("/v1/dashboard/auth/login", json={
        "username": username,
        "api_key": api_key,
    })


def csrf_headers(client):
    """Build X-CSRF-Token header from the CSRF cookie stored on the client."""
    csrf = client.cookies.get("agentnet_csrf")
    if csrf:
        return {"X-CSRF-Token": csrf}
    return {}


async def login_and_step_up(client: AsyncClient, username: str, api_key: str):
    """Login and perform step-up to enable high-risk admin operations."""
    await login(client, username, api_key)
    csrf = client.cookies.get("agentnet_csrf")
    resp = await client.post("/v1/dashboard/auth/step-up", json={
        "api_key": api_key,
    }, headers={"X-CSRF-Token": csrf} if csrf else {})
    return resp


# ──────────────────────────────────────────────────────────────────
# Admin Access: Role-based isolation
# ──────────────────────────────────────────────────────────────────

class TestAdminAccess:
    """Non-admin users cannot access admin endpoints."""

    async def test_regular_user_cannot_access_admin_overview(self, client: AsyncClient, regular_user):
        user, _, plain_key = regular_user
        await login(client, user.username, plain_key.decode())
        resp = await client.get("/v1/dashboard/admin/overview")
        assert resp.status_code == 403

    async def test_regular_user_cannot_access_admin_users(self, client: AsyncClient, regular_user):
        user, _, plain_key = regular_user
        await login(client, user.username, plain_key.decode())
        resp = await client.get("/v1/dashboard/admin/users")
        assert resp.status_code == 403

    async def test_regular_user_cannot_access_admin_agents(self, client: AsyncClient, regular_user):
        user, _, plain_key = regular_user
        await login(client, user.username, plain_key.decode())
        resp = await client.get("/v1/dashboard/admin/agents")
        assert resp.status_code == 403

    async def test_regular_user_cannot_access_admin_tasks(self, client: AsyncClient, regular_user):
        user, _, plain_key = regular_user
        await login(client, user.username, plain_key.decode())
        resp = await client.get("/v1/dashboard/admin/tasks")
        assert resp.status_code == 403

    async def test_regular_user_cannot_access_audit_logs(self, client: AsyncClient, regular_user):
        user, _, plain_key = regular_user
        await login(client, user.username, plain_key.decode())
        resp = await client.get("/v1/dashboard/admin/audit-logs")
        assert resp.status_code == 403

    async def test_regular_user_cannot_access_system_health(self, client: AsyncClient, regular_user):
        user, _, plain_key = regular_user
        await login(client, user.username, plain_key.decode())
        resp = await client.get("/v1/dashboard/admin/system-health")
        assert resp.status_code == 403

    async def test_unauthenticated_cannot_access_admin_overview(self, client: AsyncClient):
        resp = await client.get("/v1/dashboard/admin/overview")
        assert resp.status_code == 401


# ──────────────────────────────────────────────────────────────────
# Admin Overview
# ──────────────────────────────────────────────────────────────────

class TestAdminOverview:
    async def test_admin_overview_returns_kpis(self, client: AsyncClient, admin_user):
        user, _, plain_key = admin_user
        await login(client, user.username, plain_key.decode())
        resp = await client.get("/v1/dashboard/admin/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_users" in data
        assert "total_agents" in data
        assert "tasks_24h" in data
        assert "online_agents" in data
        assert "active_ws_connections" in data
        assert "pending_approvals" in data
        assert data["total_users"] >= 1  # at least the admin user

    async def test_admin_overview_counts_all_users(self, client: AsyncClient, admin_user, regular_user, session):
        """Overview should count all users, not just admin's."""
        user, _, plain_key = admin_user
        await login(client, user.username, plain_key.decode())
        resp = await client.get("/v1/dashboard/admin/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_users"] >= 2  # admin + regular


# ──────────────────────────────────────────────────────────────────
# Admin Users
# ──────────────────────────────────────────────────────────────────

class TestAdminUsers:
    async def test_list_users(self, client: AsyncClient, admin_user, regular_user, session):
        admin, _, admin_key = admin_user
        reg, _, _ = regular_user
        await login(client, admin.username, admin_key.decode())
        resp = await client.get("/v1/dashboard/admin/users")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2
        assert len(data["users"]) >= 2

    async def test_list_users_filter_by_role(self, client: AsyncClient, admin_user, session):
        admin, _, admin_key = admin_user
        await login(client, admin.username, admin_key.decode())
        resp = await client.get("/v1/dashboard/admin/users?role_filter=super_admin")
        assert resp.status_code == 200
        data = resp.json()
        for u in data["users"]:
            assert u["role"] == "super_admin"

    async def test_list_users_search(self, client: AsyncClient, admin_user, session):
        admin, _, admin_key = admin_user
        await login(client, admin.username, admin_key.decode())
        resp = await client.get(f"/v1/dashboard/admin/users?search={admin.username}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    async def test_user_detail(self, client: AsyncClient, admin_user, regular_user):
        admin, _, admin_key = admin_user
        reg, _, _ = regular_user
        await login(client, admin.username, admin_key.decode())
        resp = await client.get(f"/v1/dashboard/admin/users/{reg.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == reg.username
        assert data["role"] == reg.role

    async def test_user_detail_404_invalid_id(self, client: AsyncClient, admin_user):
        admin, _, admin_key = admin_user
        await login(client, admin.username, admin_key.decode())
        resp = await client.get("/v1/dashboard/admin/users/not-a-uuid")
        assert resp.status_code in (404, 422)

    async def test_user_detail_404_nonexistent(self, client: AsyncClient, admin_user):
        admin, _, admin_key = admin_user
        await login(client, admin.username, admin_key.decode())
        fake_id = uuid.uuid4()
        resp = await client.get(f"/v1/dashboard/admin/users/{fake_id}")
        assert resp.status_code == 404

    async def test_user_detail_creates_audit(self, client: AsyncClient, admin_user, regular_user, session: AsyncSession):
        admin, _, admin_key = admin_user
        reg, _, _ = regular_user
        await login(client, admin.username, admin_key.decode())
        resp = await client.get(f"/v1/dashboard/admin/users/{reg.id}")
        assert resp.status_code == 200
        # Check audit log
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.action == "dashboard.admin.read_user",
                AuditLog.resource_id == str(reg.id),
            )
        )
        logs = list(result.scalars().all())
        assert len(logs) >= 1
        assert logs[0].actor_type == "user"

    async def test_disable_user_requires_step_up(self, client: AsyncClient, admin_user, regular_user):
        admin, _, admin_key = admin_user
        reg, _, _ = regular_user
        await login(client, admin.username, admin_key.decode())
        # Without step-up, should get 403
        resp = await client.post(f"/v1/dashboard/admin/users/{reg.id}/disable", json={"is_disabled": True}, headers=csrf_headers(client))
        assert resp.status_code == 403

    async def test_disable_user_with_step_up(self, client: AsyncClient, admin_user, regular_user, session):
        admin, _, admin_key = admin_user
        reg, _, _ = regular_user
        await login_and_step_up(client, admin.username, admin_key.decode())
        resp = await client.post(f"/v1/dashboard/admin/users/{reg.id}/disable", json={"is_disabled": True}, headers=csrf_headers(client))
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == str(reg.id)
        assert data["is_disabled"] is True

        # Verify in DB
        await session.refresh(reg)
        assert reg.is_disabled is True

    async def test_force_revoke_keys_requires_step_up(self, client: AsyncClient, admin_user, regular_user):
        admin, _, admin_key = admin_user
        reg, _, _ = regular_user
        await login(client, admin.username, admin_key.decode())
        resp = await client.post(f"/v1/dashboard/admin/users/{reg.id}/force-revoke-keys", headers=csrf_headers(client))
        assert resp.status_code == 403

    async def test_force_revoke_keys_with_step_up(self, client: AsyncClient, admin_user, regular_user, session):
        admin, _, admin_key = admin_user
        reg, reg_api_key, _ = regular_user
        await login_and_step_up(client, admin.username, admin_key.decode())
        resp = await client.post(f"/v1/dashboard/admin/users/{reg.id}/force-revoke-keys", headers=csrf_headers(client))
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == str(reg.id)

        # Verify key is revoked
        result = await session.execute(select(ApiKey).where(ApiKey.id == reg_api_key.id))
        key = result.scalar_one()
        assert key.is_revoked is True

    async def test_disable_user_creates_audit(self, client: AsyncClient, admin_user, regular_user, session: AsyncSession):
        admin, _, admin_key = admin_user
        reg, _, _ = regular_user
        await login_and_step_up(client, admin.username, admin_key.decode())
        resp = await client.post(f"/v1/dashboard/admin/users/{reg.id}/disable", json={"is_disabled": True}, headers=csrf_headers(client))
        assert resp.status_code == 200
        # Check audit log
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.action == "dashboard.admin.disable_user",
                AuditLog.actor_id == str(admin.id),
            )
        )
        logs = list(result.scalars().all())
        assert len(logs) >= 1
        assert logs[0].actor_type == "user"

    async def test_force_revoke_keys_revokes_sessions(self, client: AsyncClient, admin_user, regular_user, session: AsyncSession):
        """force_revoke_keys revokes API keys AND active dashboard sessions."""
        from app.services.dashboard_session_service import create_session
        from app.models.dashboard_session import DashboardSession

        admin, _, admin_key = admin_user
        reg, reg_api_key, _ = regular_user

        # Create an active session for the target user
        ds, _token, _csrf = await create_session(session, reg)

        await login_and_step_up(client, admin.username, admin_key.decode())
        resp = await client.post(f"/v1/dashboard/admin/users/{reg.id}/force-revoke-keys", headers=csrf_headers(client))
        assert resp.status_code == 200
        data = resp.json()
        assert data["revoked_keys"] >= 1
        assert data["revoked_sessions"] >= 1

        # Verify API key is revoked
        await session.refresh(reg_api_key)
        assert reg_api_key.is_revoked is True

        # Verify session is revoked
        await session.refresh(ds)
        assert ds.revoked_at is not None
        assert ds.revoked_reason == "force_revoke_keys"

        # Verify audit details include both counts
        from app.models.audit_log import AuditLog
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.action == "dashboard.admin.force_revoke_keys",
                AuditLog.actor_id == str(admin.id),
            )
        )
        logs = list(result.scalars().all())
        assert len(logs) >= 1
        assert "revoked_keys" in (logs[0].details or {})
        assert "revoked_sessions" in (logs[0].details or {})

    async def test_disable_user_revokes_sessions(self, client: AsyncClient, admin_user, regular_user, session: AsyncSession):
        """disable_user(is_disabled=true) revokes target user's active dashboard sessions."""
        from app.services.dashboard_session_service import create_session

        admin, _, admin_key = admin_user
        reg, _, _ = regular_user

        # Create active sessions for the target user
        ds1, _, _ = await create_session(session, reg)
        ds2, _, _ = await create_session(session, reg)

        await login_and_step_up(client, admin.username, admin_key.decode())
        resp = await client.post(f"/v1/dashboard/admin/users/{reg.id}/disable", json={"is_disabled": True}, headers=csrf_headers(client))
        assert resp.status_code == 200

        # Verify sessions are revoked
        await session.refresh(ds1)
        await session.refresh(ds2)
        assert ds1.revoked_at is not None
        assert ds1.revoked_reason == "user_disabled"
        assert ds2.revoked_at is not None
        assert ds2.revoked_reason == "user_disabled"

        # Verify audit details
        from app.models.audit_log import AuditLog
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.action == "dashboard.admin.disable_user",
                AuditLog.actor_id == str(admin.id),
            )
        )
        logs = list(result.scalars().all())
        assert len(logs) >= 1
        details = logs[0].details or {}
        assert details.get("is_disabled") is True
        assert details.get("revoked_sessions", 0) >= 2

    async def test_enable_user_does_not_revoke_sessions(self, client: AsyncClient, admin_user, regular_user, session: AsyncSession):
        """disable_user(is_disabled=false) re-enables without revoking target user's sessions."""
        from app.services.dashboard_session_service import create_session

        admin, _, admin_key = admin_user
        reg, _, _ = regular_user

        # Create a session for the target regular user
        ds, _, _ = await create_session(session, reg)

        # Disable user first
        reg.is_disabled = True
        await session.flush()

        await login_and_step_up(client, admin.username, admin_key.decode())
        resp = await client.post(f"/v1/dashboard/admin/users/{reg.id}/disable", json={"is_disabled": False}, headers=csrf_headers(client))
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_disabled"] is False

        # Verify user is re-enabled
        await session.refresh(reg)
        assert reg.is_disabled is False

        # Target user's session should NOT be revoked by re-enable
        await session.refresh(ds)
        assert ds.revoked_at is None
        assert ds.revoked_reason is None

        # Verify audit details do NOT include revoked_sessions
        from app.models.audit_log import AuditLog
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.action == "dashboard.admin.disable_user",
                AuditLog.actor_id == str(admin.id),
            ).order_by(AuditLog.created_at.desc())
        )
        logs = list(result.scalars().all())
        assert len(logs) >= 1
        details = logs[0].details or {}
        assert details.get("is_disabled") is False
        assert "revoked_sessions" not in details


# ──────────────────────────────────────────────────────────────────
# Admin Agents
# ──────────────────────────────────────────────────────────────────

class TestAdminAgents:
    async def test_list_agents(self, client: AsyncClient, admin_user, session):
        admin, _, admin_key = admin_user
        await login(client, admin.username, admin_key.decode())
        resp = await client.get("/v1/dashboard/admin/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert "agents" in data
        assert "total" in data

    async def test_list_agents_filter_by_runtime(self, client: AsyncClient, admin_user, session):
        admin, _, admin_key = admin_user
        await login(client, admin.username, admin_key.decode())
        resp = await client.get("/v1/dashboard/admin/agents?runtime_filter=nonexistent_runtime")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    async def test_list_agents_search(self, client: AsyncClient, admin_user, session):
        admin, _, admin_key = admin_user
        await login(client, admin.username, admin_key.decode())
        resp = await client.get("/v1/dashboard/admin/agents?search=nonexistent_agent_name")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    async def test_disable_agent_requires_step_up(self, client: AsyncClient, admin_user, session):
        from app.models.agent import Agent
        admin, _, admin_key = admin_user
        agent = Agent(
            id=uuid.uuid4(),
            owner_id=admin.id,
            agent_number=f"AN-GLOBAL-{uuid.uuid4().hex[:10].upper()}",
            name="test-agent",
            runtime="python",
        )
        session.add(agent)
        await session.flush()

        await login(client, admin.username, admin_key.decode())
        resp = await client.post(f"/v1/dashboard/admin/agents/{agent.id}/disable", json={"status": "offline"}, headers=csrf_headers(client))
        assert resp.status_code == 403

    async def test_disable_agent_with_step_up(self, client: AsyncClient, admin_user, session):
        from app.models.agent import Agent
        admin, _, admin_key = admin_user
        agent = Agent(
            id=uuid.uuid4(),
            owner_id=admin.id,
            agent_number=f"AN-GLOBAL-{uuid.uuid4().hex[:10].upper()}",
            name="test-agent-2",
            runtime="python",
        )
        session.add(agent)
        await session.flush()

        await login_and_step_up(client, admin.username, admin_key.decode())
        resp = await client.post(f"/v1/dashboard/admin/agents/{agent.id}/disable", json={"status": "offline"}, headers=csrf_headers(client))
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_id"] == str(agent.id)
        assert data["status"] == "offline"


# ──────────────────────────────────────────────────────────────────
# Admin Tasks
# ──────────────────────────────────────────────────────────────────

class TestAdminTasks:
    async def test_list_tasks(self, client: AsyncClient, admin_user, session):
        admin, _, admin_key = admin_user
        await login(client, admin.username, admin_key.decode())
        resp = await client.get("/v1/dashboard/admin/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert "tasks" in data
        assert "total" in data

    async def test_list_tasks_filter_by_status(self, client: AsyncClient, admin_user, session):
        admin, _, admin_key = admin_user
        await login(client, admin.username, admin_key.decode())
        resp = await client.get("/v1/dashboard/admin/tasks?status_filter=completed")
        assert resp.status_code == 200
        data = resp.json()
        assert "tasks" in data


    async def test_list_tasks_returns_real_delivery_status(self, client: AsyncClient, admin_user, session):
        from app.models.agent import Agent
        from app.models.task import Task
        from app.models.message import Message

        admin, _, admin_key = admin_user
        agent = Agent(
            id=uuid.uuid4(),
            owner_id=admin.id,
            agent_number=f"AN-GLOBAL-{uuid.uuid4().hex[:10].upper()}",
            name="task-agent",
            runtime="python",
        )
        session.add(agent)
        await session.flush()

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
            message_id="adm-msg-001",
            type="task_result",
            delivery_status="acked",
            retry_count=3,
        )
        session.add(msg)
        await session.flush()

        await login(client, admin.username, admin_key.decode())
        resp = await client.get("/v1/dashboard/admin/tasks")
        assert resp.status_code == 200
        data = resp.json()
        task_data = next(t for t in data["tasks"] if t["task_id"] == str(task.id))
        assert task_data["delivery_status"] == "acked"
        assert task_data["owner_username"] == admin.username

    async def test_list_tasks_returns_unknown_when_no_message(self, client: AsyncClient, admin_user, session):
        from app.models.agent import Agent
        from app.models.task import Task

        admin, _, admin_key = admin_user
        agent = Agent(
            id=uuid.uuid4(),
            owner_id=admin.id,
            agent_number=f"AN-GLOBAL-{uuid.uuid4().hex[:10].upper()}",
            name="no-msg-agent",
            runtime="python",
        )
        session.add(agent)
        await session.flush()

        task = Task(
            id=uuid.uuid4(),
            created_by=agent.id,
            assigned_to=agent.id,
            status="completed",
        )
        session.add(task)
        await session.flush()

        await login(client, admin.username, admin_key.decode())
        resp = await client.get("/v1/dashboard/admin/tasks")
        assert resp.status_code == 200
        data = resp.json()
        task_data = next(t for t in data["tasks"] if t["task_id"] == str(task.id))
        assert task_data["delivery_status"] == "unknown"
        assert task_data["owner_username"] == admin.username

    async def test_task_detail_returns_real_values(self, client: AsyncClient, admin_user, session):
        from app.models.agent import Agent
        from app.models.task import Task
        from app.models.message import Message

        admin, _, admin_key = admin_user
        agent = Agent(
            id=uuid.uuid4(),
            owner_id=admin.id,
            agent_number=f"AN-GLOBAL-{uuid.uuid4().hex[:10].upper()}",
            name="detail-agent",
            runtime="python",
        )
        session.add(agent)
        await session.flush()

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
            message_id="adm-msg-002",
            type="task_result",
            delivery_status="failed",
            retry_count=7,
        )
        session.add(msg)
        await session.flush()

        await login(client, admin.username, admin_key.decode())
        resp = await client.get(f"/v1/dashboard/admin/tasks/{task.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["delivery_status"] == "failed"
        assert data["retry_count"] == 7
        assert data["owner_username"] == admin.username

    async def test_task_detail_returns_unknown_when_no_message(self, client: AsyncClient, admin_user, session):
        from app.models.agent import Agent
        from app.models.task import Task

        admin, _, admin_key = admin_user
        agent = Agent(
            id=uuid.uuid4(),
            owner_id=admin.id,
            agent_number=f"AN-GLOBAL-{uuid.uuid4().hex[:10].upper()}",
            name="no-msg-detail-agent",
            runtime="python",
        )
        session.add(agent)
        await session.flush()

        task = Task(
            id=uuid.uuid4(),
            created_by=agent.id,
            assigned_to=agent.id,
            status="completed",
        )
        session.add(task)
        await session.flush()

        await login(client, admin.username, admin_key.decode())
        resp = await client.get(f"/v1/dashboard/admin/tasks/{task.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["delivery_status"] == "unknown"
        assert data["retry_count"] == 0
        assert data["owner_username"] == admin.username

    async def test_cancel_task_creates_audit(self, client: AsyncClient, admin_user, session: AsyncSession):
        from app.models.agent import Agent
        from app.models.task import Task
        from app.models.audit_log import AuditLog

        admin, _, admin_key = admin_user
        agent = Agent(
            id=uuid.uuid4(),
            owner_id=admin.id,
            agent_number=f"AN-GLOBAL-{uuid.uuid4().hex[:10].upper()}",
            name="cancel-audit-agent",
            runtime="python",
        )
        session.add(agent)
        await session.flush()

        task = Task(
            id=uuid.uuid4(),
            created_by=agent.id,
            assigned_to=agent.id,
            status="pending",
        )
        session.add(task)
        await session.flush()

        # Login only (no step-up needed for pending task cancel)
        await login(client, admin.username, admin_key.decode())
        resp = await client.post(f"/v1/dashboard/admin/tasks/{task.id}/cancel", headers=csrf_headers(client))
        assert resp.status_code == 200

        # Check audit
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.action == "dashboard.admin.cancel_task",
                AuditLog.task_id == str(task.id),
            )
        )
        logs = list(result.scalars().all())
        assert len(logs) >= 1

    async def test_cancel_running_task_requires_step_up(self, client: AsyncClient, admin_user, session: AsyncSession):
        """super_admin cannot cancel a running task without step-up; task stays running."""
        from app.models.agent import Agent
        from app.models.task import Task

        admin, _, admin_key = admin_user
        agent = Agent(
            id=uuid.uuid4(),
            owner_id=admin.id,
            agent_number=f"AN-GLOBAL-{uuid.uuid4().hex[:10].upper()}",
            name="running-task-agent",
            runtime="python",
        )
        session.add(agent)
        await session.flush()

        task = Task(
            id=uuid.uuid4(),
            created_by=agent.id,
            assigned_to=agent.id,
            status="running",
        )
        session.add(task)
        await session.flush()

        # Login without step-up
        await login(client, admin.username, admin_key.decode())
        resp = await client.post(f"/v1/dashboard/admin/tasks/{task.id}/cancel", headers=csrf_headers(client))
        assert resp.status_code == 403

        # Task status must still be running
        await session.refresh(task)
        assert task.status == "running"

    async def test_cancel_running_task_with_step_up(self, client: AsyncClient, admin_user, session: AsyncSession):
        """super_admin with step-up can cancel a running task."""
        from app.models.agent import Agent
        from app.models.task import Task

        admin, _, admin_key = admin_user
        agent = Agent(
            id=uuid.uuid4(),
            owner_id=admin.id,
            agent_number=f"AN-GLOBAL-{uuid.uuid4().hex[:10].upper()}",
            name="running-task-agent-2",
            runtime="python",
        )
        session.add(agent)
        await session.flush()

        task = Task(
            id=uuid.uuid4(),
            created_by=agent.id,
            assigned_to=agent.id,
            status="running",
        )
        session.add(task)
        await session.flush()

        # Login with step-up
        await login_and_step_up(client, admin.username, admin_key.decode())
        resp = await client.post(f"/v1/dashboard/admin/tasks/{task.id}/cancel", headers=csrf_headers(client))
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == str(task.id)
        assert data["status"] == "cancelled"

        # Verify in DB
        await session.refresh(task)
        assert task.status == "cancelled"


    async def test_expire_task_requires_super_admin(self, client: AsyncClient, admin_user, session: AsyncSession):
        """regular/admin user cannot expire a task."""
        from app.models.agent import Agent
        from app.models.task import Task

        admin, _, admin_key = admin_user
        agent = Agent(
            id=uuid.uuid4(),
            owner_id=admin.id,
            agent_number=f"AN-GLOBAL-{uuid.uuid4().hex[:10].upper()}",
            name="expire-agent",
            runtime="python",
        )
        session.add(agent)
        await session.flush()

        task = Task(
            id=uuid.uuid4(),
            created_by=agent.id,
            assigned_to=agent.id,
            status="pending",
        )
        session.add(task)
        await session.flush()

        # super_admin without step-up → 403
        await login(client, admin.username, admin_key.decode())
        resp = await client.post(f"/v1/dashboard/admin/tasks/{task.id}/expire", headers=csrf_headers(client))
        assert resp.status_code == 403

        # Task status must remain unchanged
        await session.refresh(task)
        assert task.status == "pending"

    async def test_expire_task_with_step_up(self, client: AsyncClient, admin_user, session: AsyncSession):
        """super_admin with step-up can expire a pending task."""
        from app.models.agent import Agent
        from app.models.task import Task

        admin, _, admin_key = admin_user
        agent = Agent(
            id=uuid.uuid4(),
            owner_id=admin.id,
            agent_number=f"AN-GLOBAL-{uuid.uuid4().hex[:10].upper()}",
            name="expire-agent-2",
            runtime="python",
        )
        session.add(agent)
        await session.flush()

        task = Task(
            id=uuid.uuid4(),
            created_by=agent.id,
            assigned_to=agent.id,
            status="pending",
        )
        session.add(task)
        await session.flush()

        await login_and_step_up(client, admin.username, admin_key.decode())
        resp = await client.post(f"/v1/dashboard/admin/tasks/{task.id}/expire", headers=csrf_headers(client))
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == str(task.id)
        assert data["status"] == "expired"

        await session.refresh(task)
        assert task.status == "expired"

    async def test_expire_running_task_with_step_up(self, client: AsyncClient, admin_user, session: AsyncSession):
        """super_admin with step-up can expire a running task."""
        from app.models.agent import Agent
        from app.models.task import Task

        admin, _, admin_key = admin_user
        agent = Agent(
            id=uuid.uuid4(),
            owner_id=admin.id,
            agent_number=f"AN-GLOBAL-{uuid.uuid4().hex[:10].upper()}",
            name="expire-running-agent",
            runtime="python",
        )
        session.add(agent)
        await session.flush()

        task = Task(
            id=uuid.uuid4(),
            created_by=agent.id,
            assigned_to=agent.id,
            status="running",
        )
        session.add(task)
        await session.flush()

        await login_and_step_up(client, admin.username, admin_key.decode())
        resp = await client.post(f"/v1/dashboard/admin/tasks/{task.id}/expire", headers=csrf_headers(client))
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "expired"

        await session.refresh(task)
        assert task.status == "expired"

    async def test_expire_terminal_task_returns_400(self, client: AsyncClient, admin_user, session: AsyncSession):
        """Expiring a terminal task (completed) returns 400 and status is unchanged."""
        from app.models.agent import Agent
        from app.models.task import Task

        admin, _, admin_key = admin_user
        agent = Agent(
            id=uuid.uuid4(),
            owner_id=admin.id,
            agent_number=f"AN-GLOBAL-{uuid.uuid4().hex[:10].upper()}",
            name="expire-terminal-agent",
            runtime="python",
        )
        session.add(agent)
        await session.flush()

        for terminal_status in ("completed", "failed", "cancelled", "expired"):
            task = Task(
                id=uuid.uuid4(),
                created_by=agent.id,
                assigned_to=agent.id,
                status=terminal_status,
            )
            session.add(task)
            await session.flush()

            await login_and_step_up(client, admin.username, admin_key.decode())
            resp = await client.post(f"/v1/dashboard/admin/tasks/{task.id}/expire", headers=csrf_headers(client))
            assert resp.status_code == 400, f"Expected 400 for terminal status '{terminal_status}', got {resp.status_code}"
            assert "Cannot expire" in resp.json()["detail"]

            await session.refresh(task)
            assert task.status == terminal_status

    async def test_expire_task_creates_audit(self, client: AsyncClient, admin_user, session: AsyncSession):
        """Expiring a task writes audit with previous_status in details."""
        from app.models.agent import Agent
        from app.models.task import Task
        from app.models.audit_log import AuditLog

        admin, _, admin_key = admin_user
        agent = Agent(
            id=uuid.uuid4(),
            owner_id=admin.id,
            agent_number=f"AN-GLOBAL-{uuid.uuid4().hex[:10].upper()}",
            name="expire-audit-agent",
            runtime="python",
        )
        session.add(agent)
        await session.flush()

        task = Task(
            id=uuid.uuid4(),
            created_by=agent.id,
            assigned_to=agent.id,
            status="delivered",
        )
        session.add(task)
        await session.flush()

        await login_and_step_up(client, admin.username, admin_key.decode())
        resp = await client.post(f"/v1/dashboard/admin/tasks/{task.id}/expire", headers=csrf_headers(client))
        assert resp.status_code == 200

        result = await session.execute(
            select(AuditLog).where(
                AuditLog.action == "dashboard.admin.expire_task",
                AuditLog.task_id == str(task.id),
            )
        )
        logs = list(result.scalars().all())
        assert len(logs) >= 1
        assert logs[0].resource_type == "task"
        assert logs[0].resource_id == str(task.id)
        details = logs[0].details or {}
        assert details.get("previous_status") == "delivered"


# ──────────────────────────────────────────────────────────────────
# Audit Logs
# ──────────────────────────────────────────────────────────────────

class TestAuditLogs:
    async def test_list_audit_logs(self, client: AsyncClient, admin_user):
        admin, _, admin_key = admin_user
        await login(client, admin.username, admin_key.decode())
        resp = await client.get("/v1/dashboard/admin/audit-logs")
        assert resp.status_code == 200
        data = resp.json()
        assert "audit_logs" in data
        assert "total" in data

    async def test_list_audit_logs_filter_by_action(self, client: AsyncClient, admin_user):
        admin, _, admin_key = admin_user
        await login(client, admin.username, admin_key.decode())
        resp = await client.get("/v1/dashboard/admin/audit-logs?action=dashboard.login.success")
        assert resp.status_code == 200
        data = resp.json()
        assert "audit_logs" in data

    async def test_export_audit_logs(self, client: AsyncClient, admin_user):
        """Export audit logs works for super_admin (requires step-up)."""
        admin, _, admin_key = admin_user
        await login_and_step_up(client, admin.username, admin_key.decode())
        resp = await client.get("/v1/dashboard/admin/audit-logs/export")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "logs" in data

    async def test_export_audit_logs_creates_audit(self, client: AsyncClient, admin_user, session: AsyncSession):
        admin, _, admin_key = admin_user
        await login_and_step_up(client, admin.username, admin_key.decode())
        resp = await client.get("/v1/dashboard/admin/audit-logs/export")
        assert resp.status_code == 200
        # Check audit log
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.action == "dashboard.admin.export_audit",
                AuditLog.actor_id == str(admin.id),
            )
        )
        logs = list(result.scalars().all())
        assert len(logs) >= 1
        assert logs[0].actor_type == "user"

    async def test_export_audit_logs_regular_user_forbidden(self, client: AsyncClient, regular_user):
        """Regular user cannot export audit logs."""
        user, _, plain_key = regular_user
        await login(client, user.username, plain_key.decode())
        resp = await client.get("/v1/dashboard/admin/audit-logs/export")
        assert resp.status_code == 403

    async def test_audit_logs_capture_login(self, client: AsyncClient, admin_user, session):
        """Verify login creates an audit log entry."""
        admin, _, admin_key = admin_user
        await login(client, admin.username, admin_key.decode())
        result = await session.execute(
            select(AuditLog).where(AuditLog.action == "dashboard.login.success")
        )
        logs = list(result.scalars().all())
        assert len(logs) >= 1
        assert logs[0].actor_type == "user"


# ──────────────────────────────────────────────────────────────────
# System Health
# ──────────────────────────────────────────────────────────────────

class TestSystemHealth:
    async def test_system_health(self, client: AsyncClient, admin_user):
        admin, _, admin_key = admin_user
        await login(client, admin.username, admin_key.decode())
        resp = await client.get("/v1/dashboard/admin/system-health")
        assert resp.status_code == 200
        data = resp.json()
        assert "api_health" in data
        assert "db_health" in data
        assert "redis_health" in data

    async def test_system_health_no_secrets(self, client: AsyncClient, admin_user):
        admin, _, admin_key = admin_user
        await login(client, admin.username, admin_key.decode())
        resp = await client.get("/v1/dashboard/admin/system-health")
        assert resp.status_code == 200
        data_str = str(resp.json())
        assert "DATABASE_URL" not in data_str
        assert "REDIS_URL" not in data_str
        assert "SECRET" not in data_str

    async def test_system_health_requires_admin(self, client: AsyncClient, regular_user):
        user, _, plain_key = regular_user
        await login(client, user.username, plain_key.decode())
        resp = await client.get("/v1/dashboard/admin/system-health")
        assert resp.status_code == 403
