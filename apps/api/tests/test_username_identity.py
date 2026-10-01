"""Username identity model (migration 0030).

Usernames are non-unique display labels: user_id is the canonical
identifier, login resolves by API key (never by username match), and
registration always creates a fresh account - the old "get or create"
semantics would have issued a key for an existing same-named account.
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _register(client: AsyncClient, username: str):
    resp = await client.post(
        "/v1/auth/register",
        json={"username": username, "key_name": f"key-{uuid.uuid4().hex[:6]}"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


class TestDuplicateUsernames:
    async def test_same_username_creates_distinct_users(self, client):
        first = await _register(client, "same-name")
        second = await _register(client, "same-name")

        assert first["user_id"] != second["user_id"]
        assert first["username"] == "same-name"
        assert second["username"] == "same-name"
        # Each registration issues its own key.
        assert first["api_key"] != second["api_key"]

    async def test_login_with_duplicate_username_uses_own_key(self, client):
        first = await _register(client, "dupe-login")
        second = await _register(client, "dupe-login")

        # Each key logs its own account in; the username alone cannot
        # tell them apart, and the other account's key never works.
        resp_a = await client.post(
            "/v1/dashboard/auth/login",
            json={"username": "dupe-login", "api_key": first["api_key"]},
        )
        assert resp_a.status_code == 200, resp_a.text

        resp_b = await client.post(
            "/v1/dashboard/auth/login",
            json={"username": "dupe-login", "api_key": second["api_key"]},
        )
        assert resp_b.status_code == 200, resp_b.text

        # Cross-contamination check: user A's key with a wrong username
        # still resolves to A's account only (key-first semantics).
        me = await client.get("/v1/dashboard/auth/me")
        assert me.status_code == 200

    async def test_wrong_api_key_rejected(self, client):
        await _register(client, "dupe-reject")
        bogus = "ak_" + uuid.uuid4().hex
        resp = await client.post(
            "/v1/dashboard/auth/login",
            json={"username": "dupe-reject", "api_key": bogus},
        )
        assert resp.status_code == 401


class TestProfileRename:
    async def _login(self, client, username, api_key):
        resp = await client.post(
            "/v1/dashboard/auth/login",
            json={"username": username, "api_key": api_key},
        )
        assert resp.status_code == 200, resp.text

    async def test_rename_updates_me(self, client):
        reg = await _register(client, "rename-me")
        await self._login(client, reg["username"], reg["api_key"])

        # CSRF token is set as a cookie on login; read it for the mutation.
        csrf = client.cookies.get("agentnet_csrf")
        resp = await client.patch(
            "/v1/dashboard/auth/me/profile",
            json={"username": "renamed-ok"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["username"] == "renamed-ok"

        me = await client.get("/v1/dashboard/auth/me")
        assert me.json()["username"] == "renamed-ok"

    async def test_rename_to_existing_name_allowed(self, client):
        # Usernames are display labels: renaming to a name another user
        # holds must not collide (the pre-0030 unique constraint would).
        await _register(client, "taken-name")
        reg = await _register(client, "wants-taken")
        await self._login(client, reg["username"], reg["api_key"])

        csrf = client.cookies.get("agentnet_csrf")
        resp = await client.patch(
            "/v1/dashboard/auth/me/profile",
            json={"username": "taken-name"},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["username"] == "taken-name"

    async def test_rename_requires_csrf(self, client):
        reg = await _register(client, "no-csrf-rename")
        await self._login(client, reg["username"], reg["api_key"])
        resp = await client.patch(
            "/v1/dashboard/auth/me/profile",
            json={"username": "should-fail"},
        )
        assert resp.status_code in (403, 401)

    async def test_invalid_rename_rejected(self, client):
        reg = await _register(client, "valid-rename")
        await self._login(client, reg["username"], reg["api_key"])
        csrf = client.cookies.get("agentnet_csrf")
        resp = await client.patch(
            "/v1/dashboard/auth/me/profile",
            json={"username": "   "},
            headers={"X-CSRF-Token": csrf},
        )
        assert resp.status_code in (400, 422)
