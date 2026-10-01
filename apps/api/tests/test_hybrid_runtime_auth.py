"""Hybrid auth on runtime REST endpoints.

The web console authenticates with the dashboard session cookie set at
login, while programmatic clients (agents, SDK, CLI) use X-API-Key /
Bearer tokens. Runtime routers (routing, tasks, personal) must accept
either; otherwise a console page hitting /v1/routes/decisions receives
401 and the axios interceptor kicks the signed-in user to /login,
which PublicLayout then bounces to /app/overview (the reported
"clicking Route Decisions jumps to personal overview" bug).
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import SessionLocal
from app.main import app
from app.models.user import User
from app.services.auth import create_api_key_for_user


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _make_user_with_key() -> tuple[User, str]:
    """Create a user + plain API key directly (no register endpoint)."""
    async with SessionLocal() as session:
        user = User(username=f"hybrid-{uuid.uuid4().hex[:8]}")
        session.add(user)
        await session.flush()
        raw_key = await create_api_key_for_user(user, "hybrid-test", session)
        await session.commit()
        await session.refresh(user)
        return user, raw_key


async def _login(client: AsyncClient, username: str, api_key: str):
    resp = await client.post(
        "/v1/dashboard/auth/login", json={"username": username, "api_key": api_key}
    )
    assert resp.status_code == 200
    return resp


class TestRuntimeEndpointSessionAuth:
    """Console session cookie must work on runtime endpoints."""

    async def test_routes_decisions_with_session_cookie(self, client):
        user, raw_key = await _make_user_with_key()
        await _login(client, user.username, raw_key)
        resp = await client.get("/v1/routes/decisions", params={"limit": 5})
        assert resp.status_code == 200, resp.text
        assert "decisions" in resp.json()

    async def test_personal_scope_with_session_cookie(self, client):
        user, raw_key = await _make_user_with_key()
        await _login(client, user.username, raw_key)
        resp = await client.get("/v1/personal/scope")
        assert resp.status_code == 200, resp.text

    async def test_tasks_list_with_session_cookie(self, client):
        user, raw_key = await _make_user_with_key()
        await _login(client, user.username, raw_key)
        resp = await client.get("/v1/tasks", params={"limit": 5})
        assert resp.status_code == 200, resp.text


class TestRuntimeEndpointApiKeyAuth:
    """Programmatic API-key auth must keep working."""

    async def test_routes_decisions_with_api_key_header(self, client):
        _, raw_key = await _make_user_with_key()
        resp = await client.get(
            "/v1/routes/decisions",
            params={"limit": 5},
            headers={"X-API-Key": raw_key},
        )
        assert resp.status_code == 200, resp.text

    async def test_routes_decisions_with_bearer_token(self, client):
        _, raw_key = await _make_user_with_key()
        resp = await client.get(
            "/v1/routes/decisions",
            params={"limit": 5},
            headers={"Authorization": f"Bearer {raw_key}"},
        )
        assert resp.status_code == 200, resp.text

    async def test_personal_scope_with_api_key(self, client):
        _, raw_key = await _make_user_with_key()
        resp = await client.get(
            "/v1/personal/scope", headers={"X-API-Key": raw_key}
        )
        assert resp.status_code == 200, resp.text


class TestRuntimeEndpointAuthFailure:
    async def test_routes_decisions_without_credentials(self, client):
        resp = await client.get("/v1/routes/decisions")
        assert resp.status_code == 401

    async def test_invalid_api_key_rejected(self, client):
        # Dynamically generated bogus key; no real credential is ever
        # written into the source tree.
        bogus = "ak_" + uuid.uuid4().hex
        resp = await client.get(
            "/v1/routes/decisions", headers={"X-API-Key": bogus}
        )
        assert resp.status_code == 401

    async def test_invalid_session_cookie_rejected(self, client):
        bogus_session = uuid.uuid4().hex
        resp = await client.get(
            "/v1/routes/decisions",
            cookies={"agentnet_session": bogus_session},
        )
        assert resp.status_code == 401
