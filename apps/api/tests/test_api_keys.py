"""API key lifecycle tests."""

from __future__ import annotations

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


async def _register(client: AsyncClient) -> str:
    response = await client.post(
        "/v1/auth/register",
        json={"username": f"api-key-{uuid.uuid4().hex[:8]}", "key_name": "bootstrap"},
    )
    assert response.status_code == 200
    return response.json()["api_key"]


class TestApiKeyLifecycle:
    async def test_list_create_and_revoke_api_key(self, client: AsyncClient):
        old_key = await _register(client)

        listed = await client.get(
            "/v1/auth/api-keys",
            headers={"Authorization": f"Bearer {old_key}"},
        )
        assert listed.status_code == 200
        keys = listed.json()["api_keys"]
        assert len(keys) == 1
        assert keys[0]["name"] == "bootstrap"
        assert "api_key" not in keys[0]

        created = await client.post(
            "/v1/auth/api-keys",
            json={"name": "rotated"},
            headers={"Authorization": f"Bearer {old_key}"},
        )
        assert created.status_code == 201
        new_key = created.json()["api_key"]
        assert new_key.startswith("ak_")
        assert created.json()["key_prefix"] == new_key[:16]

        listed = await client.get(
            "/v1/auth/api-keys",
            headers={"Authorization": f"Bearer {new_key}"},
        )
        assert listed.status_code == 200
        assert listed.json()["total"] == 2
        old_key_id = next(k["api_key_id"] for k in listed.json()["api_keys"] if k["name"] == "bootstrap")

        revoked = await client.post(
            f"/v1/auth/api-keys/{old_key_id}/revoke",
            json={},
            headers={"Authorization": f"Bearer {new_key}"},
        )
        assert revoked.status_code == 200
        assert revoked.json()["is_revoked"] is True

        rejected = await client.get(
            "/v1/agents",
            headers={"Authorization": f"Bearer {old_key}"},
        )
        assert rejected.status_code == 401

        accepted = await client.get(
            "/v1/agents",
            headers={"Authorization": f"Bearer {new_key}"},
        )
        assert accepted.status_code == 200

    async def test_refuses_to_revoke_last_active_key_by_default(self, client: AsyncClient):
        api_key = await _register(client)
        listed = await client.get(
            "/v1/auth/api-keys",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        api_key_id = listed.json()["api_keys"][0]["api_key_id"]

        response = await client.post(
            f"/v1/auth/api-keys/{api_key_id}/revoke",
            json={},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "INVALID_REQUEST"

    async def test_can_explicitly_revoke_last_active_key(self, client: AsyncClient):
        api_key = await _register(client)
        listed = await client.get(
            "/v1/auth/api-keys",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        api_key_id = listed.json()["api_keys"][0]["api_key_id"]

        response = await client.post(
            f"/v1/auth/api-keys/{api_key_id}/revoke",
            json={"allow_last_key": True},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert response.status_code == 200
        assert response.json()["is_revoked"] is True

        rejected = await client.get(
            "/v1/agents",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert rejected.status_code == 401
