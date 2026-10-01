"""Phase 3: Task + Message Storage tests."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.protocol.constants import TaskStatus, ErrorCode
from app.exceptions import DomainException



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
        json={"username": "tasktestuser", "key_name": "task-test-key"},
    )
    assert resp.status_code == 200
    return resp.json()["api_key"]


@pytest.fixture
async def agent_a(client, user_api_key):
    resp = await client.post(
        "/v1/agents",
        json={"name": "Task Sender", "runtime": "test", "description": "Sender"},
        headers={"X-API-Key": user_api_key},
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def agent_b(client, user_api_key):
    resp = await client.post(
        "/v1/agents",
        json={"name": "Task Receiver", "runtime": "test", "description": "Receiver"},
        headers={"X-API-Key": user_api_key},
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def agent_b_number(agent_b):
    return agent_b["agent_number"]


class TestCreateTask:
    async def test_create_task_creates_message(self, client, user_api_key, agent_b_number):
        resp = await client.post(
            "/v1/tasks",
            json={
                "assigned_to": agent_b_number,
                "payload": {"text": "Hello, please analyze this repo"},
            },
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == TaskStatus.CREATED.value
        assert data["task_id"]
        assert data["message_id"]
        assert data["idempotency_key"] is None

        # Verify message was created
        task_id = data["task_id"]
        resp2 = await client.get(
            f"/v1/tasks/{task_id}/messages",
            headers={"X-API-Key": user_api_key},
        )
        assert resp2.status_code == 200
        msgs = resp2.json()["messages"]
        assert len(msgs) == 1
        assert msgs[0]["type"] == "task.request"

    async def test_idempotency_key_returns_same_task(self, client, user_api_key, agent_b_number):
        ikey = "idem-test-001"
        resp1 = await client.post(
            "/v1/tasks",
            json={"assigned_to": agent_b_number, "idempotency_key": ikey, "payload": {"x": 1}},
            headers={"X-API-Key": user_api_key},
        )
        assert resp1.status_code == 201
        tid1 = resp1.json()["task_id"]

        resp2 = await client.post(
            "/v1/tasks",
            json={"assigned_to": agent_b_number, "idempotency_key": ikey, "payload": {"x": 2}},
            headers={"X-API-Key": user_api_key},
        )
        assert resp2.status_code == 201
        assert resp2.json()["task_id"] == tid1
        # Payload should be from first request
        msgs = await client.get(f"/v1/tasks/{tid1}/messages", headers={"X-API-Key": user_api_key})
        assert msgs.json()["messages"][0]["content"] == {"x": 1}

    async def test_create_task_requires_auth(self, client):
        resp = await client.post("/v1/tasks", json={"assigned_to": "AN-GLOBAL-XX", "payload": {}})
        assert resp.status_code == 401

    async def test_create_task_invalid_target(self, client, user_api_key):
        # The calling user needs a sender agent: registration always
        # creates a fresh account now (usernames are non-unique labels),
        # so the caller cannot inherit one from an earlier test.
        resp_a = await client.post(
            "/v1/agents",
            json={"name": "Caller", "runtime": "test"},
            headers={"X-API-Key": user_api_key},
        )
        assert resp_a.status_code == 201
        resp = await client.post(
            "/v1/tasks",
            json={"assigned_to": "AN-GLOBAL-NONEXIST", "payload": {}},
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == ErrorCode.AGENT_NOT_FOUND.value


class TestGetTask:
    async def test_get_task(self, client, user_api_key, agent_b_number):
        create = await client.post(
            "/v1/tasks",
            json={"assigned_to": agent_b_number, "payload": {}},
            headers={"X-API-Key": user_api_key},
        )
        tid = create.json()["task_id"]

        resp = await client.get(f"/v1/tasks/{tid}", headers={"X-API-Key": user_api_key})
        assert resp.status_code == 200
        assert resp.json()["task_id"] == tid

    async def test_get_nonexistent_task(self, client, user_api_key):
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/v1/tasks/{fake_id}", headers={"X-API-Key": user_api_key})
        assert resp.status_code == 404

    async def test_list_tasks(self, client, user_api_key, agent_b_number):
        await client.post(
            "/v1/tasks",
            json={"assigned_to": agent_b_number, "payload": {}},
            headers={"X-API-Key": user_api_key},
        )
        resp = await client.get("/v1/tasks", headers={"X-API-Key": user_api_key})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["tasks"]) >= 1

    async def test_list_tasks_with_status_filter(self, client, user_api_key, agent_b_number):
        resp = await client.get("/v1/tasks?status=created", headers={"X-API-Key": user_api_key})
        assert resp.status_code == 200
        for t in resp.json()["tasks"]:
            assert t["status"] == "created"


class TestStateMachine:
    async def test_valid_transition_to_running_sets_lease(self, client, user_api_key, agent_b_number):
        from app.services.task_service import transition_state, get_task
        from app.database import SessionLocal

        # Create a task
        create = await client.post(
            "/v1/tasks",
            json={"assigned_to": agent_b_number, "payload": {}},
            headers={"X-API-Key": user_api_key},
        )
        tid = create.json()["task_id"]
        agent_id = uuid.UUID(create.json()["created_by"])

        # Transition created -> queued -> delivered -> accepted -> running
        async with SessionLocal() as session:
            task = await get_task(session, uuid.UUID(tid))
            await transition_state(session, task, "queued")
            await transition_state(session, task, "delivered")
            await transition_state(session, task, "accepted")
            await transition_state(session, task, "running", lease_agent_id=agent_id)

        resp = await client.get(f"/v1/tasks/{tid}", headers={"X-API-Key": user_api_key})
        assert resp.json()["status"] == "running"
        assert resp.json()["lease_expires_at"] is not None
        assert resp.json()["lease_agent_id"] == str(agent_id)

    async def test_invalid_transition_returns_error(self, client, user_api_key, agent_b_number):
        from app.services.task_service import transition_state, get_task
        from app.database import SessionLocal
        from app.exceptions import DomainException

        create = await client.post(
            "/v1/tasks",
            json={"assigned_to": agent_b_number, "payload": {}},
            headers={"X-API-Key": user_api_key},
        )
        tid = create.json()["task_id"]

        async with SessionLocal() as session:
            task = await get_task(session, uuid.UUID(tid))
            with pytest.raises(DomainException) as exc_info:
                await transition_state(session, task, "completed")
            assert exc_info.value.code == ErrorCode.INVALID_TASK_STATE_TRANSITION.value

    async def test_completed_is_terminal(self, client, user_api_key, agent_b_number):
        from app.services.task_service import transition_state, get_task
        from app.database import SessionLocal
        from app.exceptions import DomainException

        create = await client.post(
            "/v1/tasks",
            json={"assigned_to": agent_b_number, "payload": {}},
            headers={"X-API-Key": user_api_key},
        )
        tid = create.json()["task_id"]

        async with SessionLocal() as session:
            task = await get_task(session, uuid.UUID(tid))
            await transition_state(session, task, "queued")
            await transition_state(session, task, "delivered")
            await transition_state(session, task, "accepted")
            await transition_state(session, task, "running")
            await transition_state(session, task, "completed")

            with pytest.raises(DomainException) as exc_info:
                await transition_state(session, task, "running")
            assert exc_info.value.code == ErrorCode.INVALID_TASK_STATE_TRANSITION.value


class TestTaskHeartbeat:
    async def test_heartbeat_refreshes_lease(self, client, user_api_key, agent_b_number):
        from app.services.task_service import transition_state, get_task, heartbeat_task
        from app.database import SessionLocal

        create = await client.post(
            "/v1/tasks",
            json={"assigned_to": agent_b_number, "payload": {}},
            headers={"X-API-Key": user_api_key},
        )
        tid = create.json()["task_id"]
        agent_id = uuid.UUID(create.json()["created_by"])

        async with SessionLocal() as session:
            task = await get_task(session, uuid.UUID(tid))
            await transition_state(session, task, "queued")
            await transition_state(session, task, "delivered")
            await transition_state(session, task, "accepted")
            await transition_state(session, task, "running", lease_agent_id=agent_id)

            old_lease = task.lease_expires_at

            await heartbeat_task(session, task, agent_id)
            assert task.lease_expires_at > old_lease
            assert task.last_heartbeat_at is not None
            assert task.last_progress_at is not None

    async def test_heartbeat_on_non_running_task_fails(self, client, user_api_key, agent_b_number):
        from app.services.task_service import heartbeat_task, get_task
        from app.database import SessionLocal
        from app.exceptions import DomainException

        create = await client.post(
            "/v1/tasks",
            json={"assigned_to": agent_b_number, "payload": {}},
            headers={"X-API-Key": user_api_key},
        )
        tid = create.json()["task_id"]

        async with SessionLocal() as session:
            task = await get_task(session, uuid.UUID(tid))
            with pytest.raises(DomainException):
                await heartbeat_task(session, task, uuid.uuid4())


class TestMessages:
    async def test_get_task_messages_paginated(self, client, user_api_key, agent_b_number):
        create = await client.post(
            "/v1/tasks",
            json={"assigned_to": agent_b_number, "payload": {"msg": "test"}},
            headers={"X-API-Key": user_api_key},
        )
        tid = create.json()["task_id"]

        resp = await client.get(
            f"/v1/tasks/{tid}/messages?offset=0&limit=10",
            headers={"X-API-Key": user_api_key},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["offset"] == 0
        assert data["limit"] == 10
        assert len(data["messages"]) == 1

    async def test_get_messages_nonexistent_task(self, client, user_api_key):
        resp = await client.get(
            f"/v1/tasks/{uuid.uuid4()}/messages",
            headers={"X-API-Key": user_api_key},
        )
        # Nonexistent task returns 404 (ownership check fails first)
        assert resp.status_code == 404


class TestIdempotencyEdgeCases:
    async def test_idempotency_without_key_creates_new_task(self, client, user_api_key, agent_b_number):
        resp1 = await client.post(
            "/v1/tasks",
            json={"assigned_to": agent_b_number, "payload": {}},
            headers={"X-API-Key": user_api_key},
        )
        resp2 = await client.post(
            "/v1/tasks",
            json={"assigned_to": agent_b_number, "payload": {}},
            headers={"X-API-Key": user_api_key},
        )
        assert resp1.json()["task_id"] != resp2.json()["task_id"]
