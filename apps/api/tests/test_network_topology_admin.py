"""Tests for network topology admin list/detail endpoints."""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.network_scope import NetworkScope
from app.models.network_zone import NetworkZone
from app.models.user import User
from app.models.api_key import ApiKey
from app.services.auth import generate_api_key


pytestmark = pytest.mark.asyncio


def _csrf_headers(client: AsyncClient) -> dict:
    csrf = client.cookies.get("agentnet_csrf")
    if csrf:
        return {"X-CSRF-Token": csrf}
    return {}


async def _create_admin_with_session(client: AsyncClient, session) -> dict:
    """Create a super_admin user + API key, login + step-up, get session cookies."""
    user = User(username="topo_admin_test", role="super_admin")
    session.add(user)
    await session.flush()

    raw_key, key_hash, key_prefix = generate_api_key()
    api_key = ApiKey(user_id=user.id, key_hash=key_hash, key_prefix=key_prefix, name="test")
    session.add(api_key)
    await session.commit()

    resp = await client.post(
        "/v1/dashboard/auth/login",
        json={"username": "topo_admin_test", "api_key": raw_key},
    )
    assert resp.status_code == 200

    csrf = client.cookies.get("agentnet_csrf")
    csrf_headers = {"X-CSRF-Token": csrf} if csrf else {}
    step_up_resp = await client.post(
        "/v1/dashboard/auth/step-up",
        json={"api_key": raw_key},
        headers=csrf_headers,
    )
    assert step_up_resp.status_code == 200

    return {"user_id": str(user.id), "raw_key": raw_key}


@pytest.fixture
async def seed_topology(session: AsyncSession, client: AsyncClient):
    """Seed a scope and zone for testing."""
    user = User(username="topo_scope_owner", role="user")
    session.add(user)
    await session.flush()

    scope = NetworkScope(
        scope_name="Test Scope",
        scope_type="enterprise",
        user_id=user.id,
        network_cidr="10.0.0.0/16",
        agent_ids=[],
        zone_ids=[],
    )
    session.add(scope)
    await session.flush()

    zone = NetworkZone(
        zone_name="Test Zone",
        zone_type="regional",
        scope_id=scope.id,
        parent_zone_id=None,
        relay_node_ids=[],
        zone_metadata={"region": "us-west-2"},
    )
    session.add(zone)
    await session.flush()

    return {"scope": scope, "zone": zone, "user": user}


async def test_list_network_scopes_admin(client: AsyncClient, session, seed_topology):
    """Admin can list network scopes."""
    admin = await _create_admin_with_session(client, session)

    resp = await client.get("/v1/dashboard/admin/network/scopes")
    assert resp.status_code == 200
    data = resp.json()
    assert "scopes" in data
    assert "total" in data
    assert data["total"] >= 1
    found = [s for s in data["scopes"] if s["scope_name"] == "Test Scope"]
    assert len(found) == 1
    s = found[0]
    assert s["scope_type"] == "enterprise"
    assert s["network_cidr"] == "10.0.0.0/16"
    assert "scope_id" in s
    assert "created_at" in s


async def test_list_network_scopes_filter_by_type(client: AsyncClient, session, seed_topology):
    """Admin can filter scopes by type."""
    admin = await _create_admin_with_session(client, session)

    resp = await client.get("/v1/dashboard/admin/network/scopes?scope_type=enterprise")
    assert resp.status_code == 200
    data = resp.json()
    assert all(s["scope_type"] == "enterprise" for s in data["scopes"])


async def test_get_network_scope_detail(client: AsyncClient, session, seed_topology):
    """Admin can get scope detail by ID."""
    admin = await _create_admin_with_session(client, session)

    scope_id = str(seed_topology["scope"].id)
    resp = await client.get(f"/v1/dashboard/admin/network/scopes/{scope_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["scope_id"] == scope_id
    assert data["scope_name"] == "Test Scope"
    assert data["scope_type"] == "enterprise"
    assert data["network_cidr"] == "10.0.0.0/16"
    assert isinstance(data["agent_ids"], list)
    assert isinstance(data["zone_ids"], list)


async def test_get_network_scope_detail_not_found(client: AsyncClient, session, seed_topology):
    """Admin gets 404 for non-existent scope."""
    admin = await _create_admin_with_session(client, session)

    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await client.get(f"/v1/dashboard/admin/network/scopes/{fake_id}")
    assert resp.status_code == 404


async def test_get_network_scope_detail_invalid_id(client: AsyncClient, session, seed_topology):
    """Admin gets 422 for invalid scope ID format."""
    admin = await _create_admin_with_session(client, session)

    resp = await client.get("/v1/dashboard/admin/network/scopes/not-a-uuid")
    assert resp.status_code == 422


async def test_list_network_zones_admin(client: AsyncClient, session, seed_topology):
    """Admin can list network zones."""
    admin = await _create_admin_with_session(client, session)

    resp = await client.get("/v1/dashboard/admin/network/zones")
    assert resp.status_code == 200
    data = resp.json()
    assert "zones" in data
    assert "total" in data
    assert data["total"] >= 1
    found = [z for z in data["zones"] if z["zone_name"] == "Test Zone"]
    assert len(found) == 1
    z = found[0]
    assert z["zone_type"] == "regional"
    assert "zone_id" in z
    assert "scope_id" in z
    assert "created_at" in z


async def test_list_network_zones_filter_by_scope(client: AsyncClient, session, seed_topology):
    """Admin can filter zones by scope_id."""
    admin = await _create_admin_with_session(client, session)

    scope_id = str(seed_topology["scope"].id)
    resp = await client.get(f"/v1/dashboard/admin/network/zones?scope_id_filter={scope_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert all(z["scope_id"] == scope_id for z in data["zones"])


async def test_get_network_zone_detail(client: AsyncClient, session, seed_topology):
    """Admin can get zone detail by ID."""
    admin = await _create_admin_with_session(client, session)

    zone_id = str(seed_topology["zone"].id)
    resp = await client.get(f"/v1/dashboard/admin/network/zones/{zone_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["zone_id"] == zone_id
    assert data["zone_name"] == "Test Zone"
    assert data["zone_type"] == "regional"
    assert isinstance(data["relay_node_ids"], list)
    assert data["zone_metadata"] == {"region": "us-west-2"}


async def test_get_network_zone_detail_not_found(client: AsyncClient, session, seed_topology):
    """Admin gets 404 for non-existent zone."""
    admin = await _create_admin_with_session(client, session)

    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await client.get(f"/v1/dashboard/admin/network/zones/{fake_id}")
    assert resp.status_code == 404