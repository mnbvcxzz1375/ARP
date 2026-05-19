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


async def login_and_step_up(client: AsyncClient, username: str, api_key: str):
    """Login and perform step-up to enable high-risk admin operations."""
    await login(client, username, api_key)
    resp = await client.post("/v1/dashboard/auth/step-up", json={
        "api_key": api_key,
    })
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

    async def test_disable_user_requires_step_up(self, client: AsyncClient, admin_user, regular_user):
        admin, _, admin_key = admin_user
        reg, _, _ = regular_user
        await login(client, admin.username, admin_key.decode())
        # Without step-up, should get 403
        resp = await client.post(f"/v1/dashboard/admin/users/{reg.id}/disable", json={"is_disabled": True})
        assert resp.status_code == 403

    async def test_disable_user_with_step_up(self, client: AsyncClient, admin_user, regular_user, session):
        admin, _, admin_key = admin_user
        reg, _, _ = regular_user
        await login_and_step_up(client, admin.username, admin_key.decode())
        resp = await client.post(f"/v1/dashboard/admin/users/{reg.id}/disable", json={"is_disabled": True})
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
        resp = await client.post(f"/v1/dashboard/admin/users/{reg.id}/force-revoke-keys")
        assert resp.status_code == 403

    async def test_force_revoke_keys_with_step_up(self, client: AsyncClient, admin_user, regular_user, session):
        admin, _, admin_key = admin_user
        reg, reg_api_key, _ = regular_user
        await login_and_step_up(client, admin.username, admin_key.decode())
        resp = await client.post(f"/v1/dashboard/admin/users/{reg.id}/force-revoke-keys")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == str(reg.id)

        # Verify key is revoked
        result = await session.execute(select(ApiKey).where(ApiKey.id == reg_api_key.id))
        key = result.scalar_one()
        assert key.is_revoked is True


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
        resp = await client.post(f"/v1/dashboard/admin/agents/{agent.id}/disable", json={"status": "offline"})
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
        resp = await client.post(f"/v1/dashboard/admin/agents/{agent.id}/disable", json={"status": "offline"})
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
        """Export audit logs works for super_admin (permission-gated, no step-up required)."""
        admin, _, admin_key = admin_user
        await login(client, admin.username, admin_key.decode())
        resp = await client.get("/v1/dashboard/admin/audit-logs/export")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "logs" in data

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
