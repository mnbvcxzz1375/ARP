"""Network topology admin CRUD tests – scopes & zones create/update/delete."""
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
    user = User(username="topo_crud_admin", role="super_admin")
    session.add(user)
    await session.flush()

    raw_key, key_hash, key_prefix = generate_api_key()
    api_key = ApiKey(user_id=user.id, key_hash=key_hash, key_prefix=key_prefix, name="test")
    session.add(api_key)
    await session.commit()

    resp = await client.post(
        "/v1/dashboard/auth/login",
        json={"username": "topo_crud_admin", "api_key": raw_key},
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


async def test_create_scope(client: AsyncClient, session):
    admin = await _create_admin_with_session(client, session)
    resp = await client.post(
        "/v1/dashboard/admin/network/scopes",
        json={
            "user_id": admin["user_id"],
            "scope_name": "Test Scope",
            "scope_type": "personal",
            "network_cidr": "10.0.0.0/8",
        },
        headers=_csrf_headers(client),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["scope_name"] == "Test Scope"
    assert data["scope_type"] == "personal"
    assert data["network_cidr"] == "10.0.0.0/8"


async def test_create_scope_invalid_type(client: AsyncClient, session):
    admin = await _create_admin_with_session(client, session)
    resp = await client.post(
        "/v1/dashboard/admin/network/scopes",
        json={
            "user_id": admin["user_id"],
            "scope_name": "Bad Scope",
            "scope_type": "invalid_type",
        },
        headers=_csrf_headers(client),
    )
    assert resp.status_code == 400
    body = resp.json()
    assert "scope_type" in body.get("error", {}).get("message", "")


async def test_update_scope(client: AsyncClient, session):
    admin = await _create_admin_with_session(client, session)
    create = await client.post(
        "/v1/dashboard/admin/network/scopes",
        json={
            "user_id": admin["user_id"],
            "scope_name": "Original",
            "scope_type": "personal",
        },
        headers=_csrf_headers(client),
    )
    assert create.status_code == 201
    scope_id = create.json()["scope_id"]

    resp = await client.put(
        f"/v1/dashboard/admin/network/scopes/{scope_id}",
        json={"scope_name": "Updated", "network_cidr": "172.16.0.0/12"},
        headers=_csrf_headers(client),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["scope_name"] == "Updated"
    assert data["network_cidr"] == "172.16.0.0/12"


async def test_delete_scope(client: AsyncClient, session):
    admin = await _create_admin_with_session(client, session)
    create = await client.post(
        "/v1/dashboard/admin/network/scopes",
        json={
            "user_id": admin["user_id"],
            "scope_name": "To Delete",
            "scope_type": "enterprise",
        },
        headers=_csrf_headers(client),
    )
    assert create.status_code == 201
    scope_id = create.json()["scope_id"]

    resp = await client.delete(
        f"/v1/dashboard/admin/network/scopes/{scope_id}",
        headers=_csrf_headers(client),
    )
    assert resp.status_code == 204


async def test_create_zone(client: AsyncClient, session):
    admin = await _create_admin_with_session(client, session)
    scope = await client.post(
        "/v1/dashboard/admin/network/scopes",
        json={
            "user_id": admin["user_id"],
            "scope_name": "Zone Scope",
            "scope_type": "enterprise",
        },
        headers=_csrf_headers(client),
    )
    assert scope.status_code == 201
    scope_id = scope.json()["scope_id"]

    resp = await client.post(
        "/v1/dashboard/admin/network/zones",
        json={
            "scope_id": scope_id,
            "zone_name": "US West",
            "zone_type": "regional",
        },
        headers=_csrf_headers(client),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["zone_name"] == "US West"
    assert data["zone_type"] == "regional"


async def test_create_zone_invalid_type(client: AsyncClient, session):
    admin = await _create_admin_with_session(client, session)
    scope = await client.post(
        "/v1/dashboard/admin/network/scopes",
        json={
            "user_id": admin["user_id"],
            "scope_name": "Zone Scope 2",
            "scope_type": "enterprise",
        },
        headers=_csrf_headers(client),
    )
    scope_id = scope.json()["scope_id"]

    resp = await client.post(
        "/v1/dashboard/admin/network/zones",
        json={
            "scope_id": scope_id,
            "zone_name": "Bad Zone",
            "zone_type": "space_station",
        },
        headers=_csrf_headers(client),
    )
    assert resp.status_code == 400
    body = resp.json()
    assert "zone_type" in body.get("error", {}).get("message", "")


async def test_update_zone(client: AsyncClient, session):
    admin = await _create_admin_with_session(client, session)
    scope = await client.post(
        "/v1/dashboard/admin/network/scopes",
        json={
            "user_id": admin["user_id"],
            "scope_name": "Zone Scope 3",
            "scope_type": "enterprise",
        },
        headers=_csrf_headers(client),
    )
    scope_id = scope.json()["scope_id"]

    zone = await client.post(
        "/v1/dashboard/admin/network/zones",
        json={
            "scope_id": scope_id,
            "zone_name": "Original Zone",
            "zone_type": "local",
        },
        headers=_csrf_headers(client),
    )
    assert zone.status_code == 201
    zone_id = zone.json()["zone_id"]

    resp = await client.put(
        f"/v1/dashboard/admin/network/zones/{zone_id}",
        json={"zone_name": "Renamed Zone"},
        headers=_csrf_headers(client),
    )
    assert resp.status_code == 200
    assert resp.json()["zone_name"] == "Renamed Zone"


async def test_delete_zone(client: AsyncClient, session):
    admin = await _create_admin_with_session(client, session)
    scope = await client.post(
        "/v1/dashboard/admin/network/scopes",
        json={
            "user_id": admin["user_id"],
            "scope_name": "Zone Scope 4",
            "scope_type": "enterprise",
        },
        headers=_csrf_headers(client),
    )
    scope_id = scope.json()["scope_id"]

    zone = await client.post(
        "/v1/dashboard/admin/network/zones",
        json={
            "scope_id": scope_id,
            "zone_name": "Delete Me",
            "zone_type": "cloud",
        },
        headers=_csrf_headers(client),
    )
    assert zone.status_code == 201
    zone_id = zone.json()["zone_id"]

    resp = await client.delete(
        f"/v1/dashboard/admin/network/zones/{zone_id}",
        headers=_csrf_headers(client),
    )
    assert resp.status_code == 204


async def test_scope_crud_unauthenticated_fails(client: AsyncClient, session):
    resp = await client.post(
        "/v1/dashboard/admin/network/scopes",
        json={"user_id": "00000000-0000-0000-0000-000000000001", "scope_name": "X", "scope_type": "personal"},
    )
    assert resp.status_code == 401

    resp = await client.delete(
        "/v1/dashboard/admin/network/scopes/00000000-0000-0000-0000-000000000001",
    )
    assert resp.status_code == 401


async def test_zone_crud_unauthenticated_fails(client: AsyncClient, session):
    resp = await client.post(
        "/v1/dashboard/admin/network/zones",
        json={"scope_id": "00000000-0000-0000-0000-000000000001", "zone_name": "X", "zone_type": "local"},
    )
    assert resp.status_code == 401

    resp = await client.delete(
        "/v1/dashboard/admin/network/zones/00000000-0000-0000-0000-000000000001",
    )
    assert resp.status_code == 401


async def test_scope_create_produces_audit(client: AsyncClient, session):
    admin = await _create_admin_with_session(client, session)
    resp = await client.post(
        "/v1/dashboard/admin/network/scopes",
        json={
            "user_id": admin["user_id"],
            "scope_name": "Audited Scope",
            "scope_type": "personal",
        },
        headers=_csrf_headers(client),
    )
    assert resp.status_code == 201
    scope_id = resp.json()["scope_id"]

    audit_resp = await client.get(
        "/v1/dashboard/admin/audit-logs",
        params={"resource_type": "network_scope", "resource_id": scope_id},
    )
    assert audit_resp.status_code == 200
    entries = audit_resp.json()["audit_logs"]
    assert any(e["action"] == "network_scope.create" for e in entries)


async def test_zone_create_produces_audit(client: AsyncClient, session):
    admin = await _create_admin_with_session(client, session)
    scope = await client.post(
        "/v1/dashboard/admin/network/scopes",
        json={
            "user_id": admin["user_id"],
            "scope_name": "Zone Audit Scope",
            "scope_type": "enterprise",
        },
        headers=_csrf_headers(client),
    )
    scope_id = scope.json()["scope_id"]

    zone = await client.post(
        "/v1/dashboard/admin/network/zones",
        json={
            "scope_id": scope_id,
            "zone_name": "Audited Zone",
            "zone_type": "regional",
        },
        headers=_csrf_headers(client),
    )
    zone_id = zone.json()["zone_id"]

    audit_resp = await client.get(
        "/v1/dashboard/admin/audit-logs",
        params={"resource_type": "network_zone", "resource_id": zone_id},
    )
    assert audit_resp.status_code == 200
    entries = audit_resp.json()["audit_logs"]
    assert any(e["action"] == "network_zone.create" for e in entries)


# ── Step-up enforcement tests ─────────────────────────────────────


async def _create_admin_without_stepup(client: AsyncClient, session) -> dict:
    """Create a super_admin user + API key, login but do NOT step-up."""
    uid = uuid.uuid4().hex[:8]
    user = User(username=f"topo_nosu_{uid}", role="super_admin")
    session.add(user)
    await session.flush()

    raw_key, key_hash, key_prefix = generate_api_key()
    api_key = ApiKey(user_id=user.id, key_hash=key_hash, key_prefix=key_prefix, name="test")
    session.add(api_key)
    await session.commit()

    resp = await client.post(
        "/v1/dashboard/auth/login",
        json={"username": f"topo_nosu_{uid}", "api_key": raw_key},
    )
    assert resp.status_code == 200

    return {"user_id": str(user.id), "raw_key": raw_key}


async def test_scope_create_without_stepup_rejected(client: AsyncClient, session):
    """super_admin without step-up cannot create a scope — must get 403 STEP_UP_REQUIRED."""
    admin = await _create_admin_without_stepup(client, session)
    resp = await client.post(
        "/v1/dashboard/admin/network/scopes",
        json={
            "user_id": admin["user_id"],
            "scope_name": "No Stepup Scope",
            "scope_type": "personal",
        },
        headers=_csrf_headers(client),
    )
    assert resp.status_code == 403
    body = resp.json()
    # Must be a step-up-required error, not a generic permission error
    assert body.get("error", {}).get("code") == "STEP_UP_REQUIRED" or "step" in body.get("error", {}).get("message", "").lower()


async def test_scope_delete_without_stepup_rejected(client: AsyncClient, session):
    """super_admin without step-up cannot delete a scope."""
    # First create with step-up admin
    admin_su = await _create_admin_with_session(client, session)
    create = await client.post(
        "/v1/dashboard/admin/network/scopes",
        json={
            "user_id": admin_su["user_id"],
            "scope_name": "Stepup Created Del",
            "scope_type": "enterprise",
        },
        headers=_csrf_headers(client),
    )
    assert create.status_code == 201
    scope_id = create.json()["scope_id"]

    # Now login as a different admin without step-up — this replaces the session cookies
    admin_no_su = await _create_admin_without_stepup(client, session)
    resp = await client.delete(
        f"/v1/dashboard/admin/network/scopes/{scope_id}",
        headers=_csrf_headers(client),
    )
    assert resp.status_code == 403
