import pytest
import uuid
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models import Agent, AgentToken, ApiKey, User




@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac





@pytest.fixture
async def user_api_key(client):
    resp = await client.post(
        "/v1/auth/register",
        json={"username": f"testuser-{uuid.uuid4().hex[:8]}", "key_name": "test-key"},
    )
    assert resp.status_code == 200
    data = resp.json()
    return data["api_key"]


@pytest.fixture
async def other_api_key(client):
    resp = await client.post(
        "/v1/auth/register",
        json={"username": f"otheruser-{uuid.uuid4().hex[:8]}", "key_name": "other-key"},
    )
    assert resp.status_code == 200
    return resp.json()["api_key"]


class TestCreateAgent:
    async def test_create_agent(self, client, user_api_key):
        resp = await client.post(
            "/v1/agents",
            json={
                "name": "Test Agent",
                "runtime": "openclaw",
                "description": "A test agent",
                "capabilities": ["code_analysis"],
                "inbound_policy": "request_approval",
                "discoverable": False,
            },
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Agent"
        assert data["runtime"] == "openclaw"
        assert data["status"] == "offline"
        assert data["agent_number"].startswith("AN-GLOBAL-")
        assert data["agent_token"].startswith("agt_sk_")
        assert "agent_id" in data

    async def test_token_not_returned_on_list(self, client, user_api_key):
        resp = await client.post(
            "/v1/agents",
            json={"name": "A", "runtime": "test"},
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 201

        resp = await client.get(
            "/v1/agents", headers={"X-API-Key": user_api_key}
        )
        assert resp.status_code == 200
        agents = resp.json()["agents"]
        for a in agents:
            assert a["agent_token"] is None

    async def test_invalid_inbound_policy_rejected(self, client, user_api_key):
        resp = await client.post(
            "/v1/agents",
            json={
                "name": "Bad",
                "runtime": "test",
                "inbound_policy": "invalid_policy",
            },
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 422


class TestAgentAccessControl:
    async def test_cannot_read_other_user_agent(self, client, user_api_key, other_api_key):
        resp = await client.post(
            "/v1/agents",
            json={"name": "User1 Agent", "runtime": "test"},
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 201
        agent_id = resp.json()["agent_id"]

        resp = await client.get(
            f"/v1/agents/{agent_id}",
            headers={"X-API-Key": other_api_key},
        )
        assert resp.status_code == 404

    async def test_list_only_own_agents(self, client, user_api_key, other_api_key):
        await client.post(
            "/v1/agents",
            json={"name": "User1 A", "runtime": "test"},
            headers={"X-API-Key": user_api_key},
        )
        await client.post(
            "/v1/agents",
            json={"name": "User2 A", "runtime": "test"},
            headers={"X-API-Key": other_api_key},
        )

        resp = await client.get(
            "/v1/agents", headers={"X-API-Key": user_api_key}
        )
        assert resp.status_code == 200
        data = resp.json()
        names = {a["name"] for a in data["agents"]}
        assert "User1 A" in names
        assert "User2 A" not in names


class TestAgentTokenRotation:
    async def test_rotate_token_invalidates_old(self, client, user_api_key):
        resp = await client.post(
            "/v1/agents",
            json={"name": "RotateTest", "runtime": "test"},
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 201
        agent_id = resp.json()["agent_id"]
        old_token = resp.json()["agent_token"]

        resp = await client.post(
            f"/v1/agents/{agent_id}/rotate-token",
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 200
        new_token = resp.json()["agent_token"]
        assert new_token != old_token
        assert new_token.startswith("agt_sk_")


class TestAgentPaginationSearch:
    async def test_pagination(self, client, user_api_key):
        for i in range(5):
            await client.post(
                "/v1/agents",
                json={"name": f"Agent {i}", "runtime": "test"},
                headers={"X-API-Key": user_api_key},
            )

        resp = await client.get(
            "/v1/agents?page_size=2&page=1",
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["agents"]) == 2
        assert data["total"] >= 5
        assert data["page"] == 1

    async def test_search(self, client, user_api_key):
        await client.post(
            "/v1/agents",
            json={"name": "UniqueName", "runtime": "test"},
            headers={"X-API-Key": user_api_key},
        )
        await client.post(
            "/v1/agents",
            json={"name": "Other", "runtime": "test"},
            headers={"X-API-Key": user_api_key},
        )

        resp = await client.get(
            "/v1/agents?search=UniqueName",
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["agents"]) == 1
        assert data["agents"][0]["name"] == "UniqueName"


class TestTokenHashStorage:
    async def test_token_hash_stored_not_raw(self, client, user_api_key):
        resp = await client.post(
            "/v1/agents",
            json={"name": "HashTest", "runtime": "test"},
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 201
        data = resp.json()
        raw_token = data["agent_token"]

        from app.main import app as _app
        from app.database import SessionLocal
        from app.models.agent import Agent
        from app.models.agent_token import AgentToken
        from app.services.auth import hash_key
        from sqlalchemy import select

        async with SessionLocal() as session:
            agent_result = await session.execute(
                select(Agent).where(Agent.agent_number == data["agent_number"])
            )
            agent = agent_result.scalar_one()

            token_result = await session.execute(
                select(AgentToken).where(
                    AgentToken.agent_id == agent.id,
                    AgentToken.is_revoked == False,
                )
            )
            db_token = token_result.scalar_one()

            assert db_token.token_hash != raw_token
            assert db_token.token_prefix == raw_token[:16]


class TestAgentNumberUniqueness:
    def test_10000_agent_numbers_no_duplicates(self):
        from app.services.agent_number import generate_agent_number

        numbers = set()
        for _ in range(10_000):
            num = generate_agent_number()
            assert num.startswith("AN-GLOBAL-")
            assert len(num) > 12
            numbers.add(num)
        assert len(numbers) == 10_000


class TestAuthRequired:
    async def test_agents_endpoint_requires_auth(self, client):
        resp = await client.post(
            "/v1/agents", json={"name": "X", "runtime": "test"}
        )
        assert resp.status_code == 401

    async def test_list_agents_requires_auth(self, client):
        resp = await client.get("/v1/agents")
        assert resp.status_code == 401


class TestDeleteAgent:
    async def test_delete_agent(self, client, user_api_key):
        resp = await client.post(
            "/v1/agents",
            json={"name": "DeleteMe", "runtime": "test"},
            headers={"X-API-Key": user_api_key},
        )
        agent_id = resp.json()["agent_id"]

        resp = await client.delete(
            f"/v1/agents/{agent_id}",
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 204

        resp = await client.get(
            f"/v1/agents/{agent_id}",
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 404