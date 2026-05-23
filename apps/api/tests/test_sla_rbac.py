"""SLA API RBAC tests: verify authentication and permission enforcement."""
import hashlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.models.dashboard_session import DashboardSession


def _make_session(user: User) -> tuple[DashboardSession, str]:
    """Create a valid DashboardSession with a raw token for cookie auth."""
    raw_token = f"sla-test-token-{uuid4()}"
    session_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    now = datetime.now(UTC)
    ds = DashboardSession(
        user_id=user.id,
        session_hash=session_hash,
        csrf_hash="sla-test-csrf",
        expires_at=now + timedelta(days=7),
        idle_expires_at=now + timedelta(hours=1),
    )
    return ds, raw_token


@pytest.fixture
async def user_with_session(session: AsyncSession):
    """Create a regular user with dashboard session."""
    user = User(username="regular_user", role=UserRole.USER.value)
    session.add(user)
    await session.flush()
    ds, raw_token = _make_session(user)
    session.add(ds)
    await session.flush()
    return user, ds, raw_token


@pytest.fixture
async def admin_with_session(session: AsyncSession):
    """Create an admin user with dashboard session."""
    user = User(username="admin_user", role=UserRole.ADMIN.value)
    session.add(user)
    await session.flush()
    ds, raw_token = _make_session(user)
    session.add(ds)
    await session.flush()
    return user, ds, raw_token


@pytest.fixture
async def super_admin_with_session(session: AsyncSession):
    """Create a super admin user with dashboard session."""
    user = User(username="super_admin_user", role=UserRole.SUPER_ADMIN.value)
    session.add(user)
    await session.flush()
    ds, raw_token = _make_session(user)
    session.add(ds)
    await session.flush()
    return user, ds, raw_token


class TestSLAAuthenticationRequired:
    """Verify all SLA endpoints require authentication."""

    async def test_list_targets_requires_auth(self, client: AsyncClient):
        """GET /v1/sla/targets without auth returns 401."""
        resp = await client.get("/v1/sla/targets")
        assert resp.status_code == 401

    async def test_create_target_requires_auth(self, client: AsyncClient):
        """POST /v1/sla/targets without auth returns 401."""
        resp = await client.post("/v1/sla/targets", params={
            "scope_id": "test-scope",
            "target_name": "test",
            "metric_type": "success_rate",
            "target_value": 0.99,
        })
        assert resp.status_code == 401

    async def test_list_violations_requires_auth(self, client: AsyncClient):
        """GET /v1/sla/violations without auth returns 401."""
        resp = await client.get("/v1/sla/violations")
        assert resp.status_code == 401

    async def test_query_metrics_requires_auth(self, client: AsyncClient):
        """GET /v1/sla/metrics without auth returns 401."""
        resp = await client.get("/v1/sla/metrics?scope_id=test&metric_type=success_rate")
        assert resp.status_code == 401

    async def test_generate_report_requires_auth(self, client: AsyncClient):
        """GET /v1/sla/report without auth returns 401."""
        resp = await client.get("/v1/sla/report")
        assert resp.status_code == 401


class TestSLAReadPermission:
    """Verify sla:read permission for GET endpoints."""

    async def test_regular_user_cannot_read_sla(
        self, client: AsyncClient, user_with_session
    ):
        """Regular user lacks sla:read permission."""
        user, ds, token = user_with_session
        resp = await client.get(
            "/v1/sla/targets",
            cookies={"agentnet_session": token},
        )
        assert resp.status_code == 403

    async def test_admin_can_read_sla(
        self, client: AsyncClient, admin_with_session
    ):
        """Admin has sla:read permission."""
        user, ds, token = admin_with_session
        resp = await client.get(
            "/v1/sla/targets",
            cookies={"agentnet_session": token},
        )
        assert resp.status_code == 200
        assert "targets" in resp.json()

    async def test_super_admin_can_read_sla(
        self, client: AsyncClient, super_admin_with_session
    ):
        """Super admin has sla:read permission."""
        user, ds, token = super_admin_with_session
        resp = await client.get(
            "/v1/sla/violations",
            cookies={"agentnet_session": token},
        )
        assert resp.status_code == 200
        assert "violations" in resp.json()


class TestSLAManagePermission:
    """Verify sla:manage permission for write endpoints."""

    async def test_regular_user_cannot_manage_sla(
        self, client: AsyncClient, user_with_session
    ):
        """Regular user lacks sla:manage permission."""
        user, ds, token = user_with_session
        resp = await client.post(
            "/v1/sla/targets",
            cookies={"agentnet_session": token},
            params={
                "scope_id": "test-scope",
                "target_name": "test",
                "metric_type": "success_rate",
                "target_value": 0.99,
            },
        )
        assert resp.status_code == 403

    async def test_admin_cannot_manage_sla(
        self, client: AsyncClient, admin_with_session
    ):
        """Admin lacks sla:manage permission (read-only)."""
        user, ds, token = admin_with_session
        resp = await client.post(
            "/v1/sla/targets",
            cookies={"agentnet_session": token},
            params={
                "scope_id": "test-scope",
                "target_name": "test",
                "metric_type": "success_rate",
                "target_value": 0.99,
            },
        )
        assert resp.status_code == 403

    async def test_super_admin_can_manage_sla(
        self, client: AsyncClient, super_admin_with_session
    ):
        """Super admin has sla:manage permission."""
        user, ds, token = super_admin_with_session
        resp = await client.post(
            "/v1/sla/targets",
            cookies={"agentnet_session": token},
            params={
                "scope_id": "test-scope",
                "target_name": "test",
                "metric_type": "success_rate",
                "target_value": 0.99,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["target_name"] == "test"
