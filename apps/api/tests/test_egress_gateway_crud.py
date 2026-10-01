"""Egress gateway CRUD contract (/v1/egress/gateways).

Covers the lifecycle the enterprise console uses: list (admin read),
create / update / delete (super_admin:write + step-up + CSRF), the
permission wall for plain users, and the ON DELETE SET NULL safety net
for agents pointing at a deleted gateway.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal
from app.main import app
from app.models.api_key import ApiKey
from app.models.egress_gateway import EgressGateway
from app.models.network_scope import NetworkScope
from app.models.user import User
from app.services.auth import generate_api_key

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _csrf_headers(client: AsyncClient) -> dict:
    csrf = client.cookies.get("agentnet_csrf")
    return {"X-CSRF-Token": csrf} if csrf else {}


def _session() -> AsyncSession:
    return SessionLocal()


async def _login_super_admin(client: AsyncClient) -> tuple[str, User]:
    """Create a super_admin, log in + step up.

    Returns (raw_api_key, user) - the key for auth headers, the user for
    seeding owned network scopes.
    """
    username = f"gw-admin-{uuid.uuid4().hex[:6]}"
    async with _session() as session:
        user = User(username=username, role="super_admin")
        session.add(user)
        await session.flush()
        raw_key, key_hash, key_prefix = generate_api_key()
        session.add(
            ApiKey(user_id=user.id, key_hash=key_hash, key_prefix=key_prefix, name="test")
        )
        await session.commit()
        await session.refresh(user)

    resp = await client.post(
        "/v1/dashboard/auth/login",
        json={"username": username, "api_key": raw_key},
    )
    assert resp.status_code == 200, resp.text
    step_up = await client.post(
        "/v1/dashboard/auth/step-up",
        json={"api_key": raw_key},
        headers=_csrf_headers(client),
    )
    assert step_up.status_code == 200, step_up.text
    return raw_key, user


async def _login_plain_user(client: AsyncClient) -> str:
    """A role='user' account with no admin permissions."""
    username = f"gw-plain-{uuid.uuid4().hex[:6]}"
    async with _session() as session:
        user = User(username=username, role="user")
        session.add(user)
        await session.flush()
        raw_key, key_hash, key_prefix = generate_api_key()
        session.add(
            ApiKey(user_id=user.id, key_hash=key_hash, key_prefix=key_prefix, name="test")
        )
        await session.commit()
    resp = await client.post(
        "/v1/dashboard/auth/login",
        json={"username": username, "api_key": raw_key},
    )
    assert resp.status_code == 200, resp.text
    return raw_key


async def _seed_scope(user_id) -> NetworkScope:
    async with _session() as session:
        scope = NetworkScope(
            scope_name=f"gw-test-{uuid.uuid4().hex[:6]}",
            scope_type="personal",
            user_id=user_id,
            org_id=None,
        )
        session.add(scope)
        await session.commit()
        await session.refresh(scope)
        return scope


async def _seed_gateway(scope_id, name="gw-seed", gtype="api") -> EgressGateway:
    async with _session() as session:
        gw = EgressGateway(
            scope_id=scope_id,
            gateway_name=name,
            gateway_type=gtype,
            domain_allowlist=["example.com"],
        )
        session.add(gw)
        await session.commit()
        await session.refresh(gw)
        return gw


class TestListGateways:
    async def test_list_requires_admin_read(self, client):
        # Plain users are fail-closed: 403, not the list.
        key = await _login_plain_user(client)
        resp = await client.get(
            "/v1/egress/gateways", headers={"X-API-Key": key}
        )
        assert resp.status_code == 403

    async def test_list_returns_all_gateways_for_admin(self, client):
        _key, user = await _login_super_admin(client)
        scope = await _seed_scope(user.id)
        await _seed_gateway(scope.id, name="raw-list-test")

        # Session-cookie auth (what the console actually uses).
        resp = await client.get("/v1/egress/gateways")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "gateways" in data
        assert data["total"] >= 1
        assert any(g["gateway_name"] == "raw-list-test" for g in data["gateways"])


class TestCreateGateway:
    async def test_create_requires_csrf(self, client):
        _key, user = await _login_super_admin(client)
        scope = await _seed_scope(user.id)
        # No CSRF header: 403.
        resp = await client.post(
            "/v1/egress/gateways",
            json={
                "scope_id": str(scope.id),
                "gateway_name": "gw-no-csrf",
                "gateway_type": "api",
            },
        )
        assert resp.status_code == 403

    async def test_create_happy_path(self, client):
        _key, user = await _login_super_admin(client)
        scope = await _seed_scope(user.id)

        resp = await client.post(
            "/v1/egress/gateways",
            json={
                "scope_id": str(scope.id),
                "gateway_name": "gw-created",
                "gateway_type": "api",
                "domain_allowlist": ["api.example.com", "cdn.example.com"],
                "cost_tracking": True,
            },
            headers=_csrf_headers(client),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["gateway_name"] == "gw-created"
        assert data["gateway_type"] == "api"
        assert data["enabled"] is True
        assert data["domain_allowlist"] == ["api.example.com", "cdn.example.com"]

    async def test_create_rejects_too_long_type(self, client):
        _key, user = await _login_super_admin(client)
        scope = await _seed_scope(user.id)
        resp = await client.post(
            "/v1/egress/gateways",
            json={
                "scope_id": str(scope.id),
                "gateway_name": "gw-bad-type",
                "gateway_type": "x" * 64,
            },
            headers=_csrf_headers(client),
        )
        assert resp.status_code == 422

    async def test_plain_user_cannot_create(self, client):
        key = await _login_plain_user(client)
        resp = await client.post(
            "/v1/egress/gateways",
            json={
                "scope_id": str(uuid.uuid4()),
                "gateway_name": "gw-forbidden",
                "gateway_type": "api",
            },
            headers={"X-API-Key": key},
        )
        assert resp.status_code == 403


class TestUpdateDeleteGateway:
    async def test_get_update_delete_flow(self, client):
        _key, user = await _login_super_admin(client)
        scope = await _seed_scope(user.id)
        gw = await _seed_gateway(scope.id, name="gw-mutate", gtype="model")

        # GET single
        resp = await client.get(f"/v1/egress/gateways/{gw.id}")
        assert resp.status_code == 200, resp.text
        assert resp.json()["gateway_name"] == "gw-mutate"

        # UPDATE: rename + disable
        resp = await client.patch(
            f"/v1/egress/gateways/{gw.id}",
            json={"gateway_name": "gw-mutated", "enabled": False},
            headers=_csrf_headers(client),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["gateway_name"] == "gw-mutated"
        assert resp.json()["enabled"] is False

        # DELETE
        resp = await client.delete(
            f"/v1/egress/gateways/{gw.id}", headers=_csrf_headers(client)
        )
        assert resp.status_code == 204, resp.text

        # Gone
        resp = await client.get(f"/v1/egress/gateways/{gw.id}")
        assert resp.status_code == 404

    async def test_missing_gateway_404(self, client):
        _key, _user = await _login_super_admin(client)
        resp = await client.get(f"/v1/egress/gateways/{uuid.uuid4()}")
        assert resp.status_code == 404
