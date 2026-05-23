"""Continuity API RBAC tests: verify authentication and permission enforcement."""
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
    raw_token = f"continuity-test-token-{uuid4()}"
    session_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    now = datetime.now(UTC)
    ds = DashboardSession(
        user_id=user.id,
        session_hash=session_hash,
        csrf_hash="continuity-test-csrf",
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


class TestContinuityReadPermission:
    """Verify continuity:read permission for read endpoints."""

    async def test_regular_user_cannot_read_continuity(
        self, client: AsyncClient, user_with_session
    ):
        """Regular user lacks continuity:read permission."""
        user, ds, token = user_with_session
        resp = await client.get(
            "/v1/continuity/failover-configs",
            cookies={"agentnet_session": token},
        )
        assert resp.status_code == 403

    async def test_admin_can_read_continuity(
        self, client: AsyncClient, admin_with_session
    ):
        """Admin has continuity:read permission."""
        user, ds, token = admin_with_session
        resp = await client.get(
            "/v1/continuity/failover-configs",
            cookies={"agentnet_session": token},
        )
        assert resp.status_code == 200
        assert "configs" in resp.json()

    async def test_super_admin_can_read_continuity(
        self, client: AsyncClient, super_admin_with_session
    ):
        """Super admin has continuity:read permission."""
        user, ds, token = super_admin_with_session
        resp = await client.get(
            "/v1/continuity/failover-configs",
            cookies={"agentnet_session": token},
        )
        assert resp.status_code == 200
        assert "configs" in resp.json()


class TestContinuityManagePermission:
    """Verify continuity:manage permission for write endpoints."""

    async def test_regular_user_cannot_manage_continuity(
        self, client: AsyncClient, user_with_session
    ):
        """Regular user lacks continuity:manage permission."""
        user, ds, token = user_with_session
        resp = await client.post(
            "/v1/continuity/failover-configs",
            cookies={"agentnet_session": token},
            params={
                "scope_id": str(uuid4()),
                "primary_relay_id": str(uuid4()),
            },
            json=[str(uuid4())],
        )
        assert resp.status_code == 403

    async def test_admin_cannot_manage_continuity(
        self, client: AsyncClient, admin_with_session
    ):
        """Admin lacks continuity:manage permission (read-only)."""
        user, ds, token = admin_with_session
        resp = await client.post(
            "/v1/continuity/failover-configs",
            cookies={"agentnet_session": token},
            params={
                "scope_id": str(uuid4()),
                "primary_relay_id": str(uuid4()),
            },
            json=[str(uuid4())],
        )
        assert resp.status_code == 403

    async def test_super_admin_can_manage_continuity(
        self, client: AsyncClient, super_admin_with_session, session: AsyncSession
    ):
        """Super admin has continuity:manage permission."""
        from app.models.relay_node import RelayNode

        # Create relay nodes for the test
        scope_id = uuid4()
        primary_relay = RelayNode(id=uuid4(), node_name="primary", node_type="regional")
        backup_relay = RelayNode(id=uuid4(), node_name="backup", node_type="regional")
        session.add(primary_relay)
        session.add(backup_relay)
        await session.flush()

        user, ds, token = super_admin_with_session
        resp = await client.post(
            "/v1/continuity/failover-configs",
            cookies={"agentnet_session": token},
            params={
                "scope_id": str(scope_id),
                "primary_relay_id": str(primary_relay.id),
            },
            json=[str(backup_relay.id)],
        )
        assert resp.status_code == 200
        assert resp.json()["scope_id"] == str(scope_id)


class TestContinuityFailoverOperations:
    """Verify continuity:manage permission for failover operations."""

    async def test_regular_user_cannot_trigger_failover(
        self, client: AsyncClient, user_with_session
    ):
        """Regular user cannot trigger manual failover."""
        user, ds, token = user_with_session
        config_id = str(uuid4())
        resp = await client.post(
            f"/v1/continuity/failover/{config_id}/trigger",
            cookies={"agentnet_session": token},
            params={"trigger_reason": "test"},
        )
        assert resp.status_code == 403

    async def test_admin_cannot_trigger_failover(
        self, client: AsyncClient, admin_with_session
    ):
        """Admin cannot trigger manual failover."""
        user, ds, token = admin_with_session
        config_id = str(uuid4())
        resp = await client.post(
            f"/v1/continuity/failover/{config_id}/trigger",
            cookies={"agentnet_session": token},
            params={"trigger_reason": "test"},
        )
        assert resp.status_code == 403

    async def test_regular_user_cannot_reset_circuit_breaker(
        self, client: AsyncClient, user_with_session
    ):
        """Regular user cannot reset circuit breaker."""
        user, ds, token = user_with_session
        breaker_id = str(uuid4())
        resp = await client.post(
            f"/v1/continuity/circuit-breakers/{breaker_id}/reset",
            cookies={"agentnet_session": token},
        )
        assert resp.status_code == 403

    async def test_admin_cannot_reset_circuit_breaker(
        self, client: AsyncClient, admin_with_session
    ):
        """Admin cannot reset circuit breaker."""
        user, ds, token = admin_with_session
        breaker_id = str(uuid4())
        resp = await client.post(
            f"/v1/continuity/circuit-breakers/{breaker_id}/reset",
            cookies={"agentnet_session": token},
        )
        assert resp.status_code == 403


class TestContinuityHealthCheck:
    """Verify continuity:manage permission for health checks."""

    async def test_regular_user_cannot_check_relay_health(
        self, client: AsyncClient, user_with_session
    ):
        """Regular user cannot check relay health."""
        user, ds, token = user_with_session
        relay_id = str(uuid4())
        resp = await client.get(
            f"/v1/continuity/relay-health/{relay_id}",
            cookies={"agentnet_session": token},
        )
        assert resp.status_code == 403

    async def test_admin_cannot_check_relay_health(
        self, client: AsyncClient, admin_with_session
    ):
        """Admin cannot check relay health (requires manage permission)."""
        user, ds, token = admin_with_session
        relay_id = str(uuid4())
        resp = await client.get(
            f"/v1/continuity/relay-health/{relay_id}",
            cookies={"agentnet_session": token},
        )
        assert resp.status_code == 403
