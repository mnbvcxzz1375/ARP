"""Real API + WebSocket end-to-end tests."""

from __future__ import annotations

import asyncio
import json
import uuid

import httpx
import pytest
import websockets
import websockets.asyncio.client

from app.protocol.constants import DeliveryStatus, MessageType
from helpers.ws_e2e import run_live_server


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def _create_user_and_agents(client: httpx.AsyncClient):
    suffix = uuid.uuid4().hex[:8]
    register = await client.post(
        "/v1/auth/register",
        json={"username": f"ws-e2e-{suffix}", "key_name": "ws-e2e"},
    )
    assert register.status_code == 200
    api_key = register.json()["api_key"]
    headers = {"Authorization": f"Bearer {api_key}"}

    sender = await client.post(
        "/v1/agents",
        json={"name": "E2E Sender", "runtime": "pytest"},
        headers=headers,
    )
    assert sender.status_code == 201

    receiver = await client.post(
        "/v1/agents",
        json={"name": "E2E Receiver", "runtime": "pytest", "inbound_policy": "public"},
        headers=headers,
    )
    assert receiver.status_code == 201

    return api_key, sender.json(), receiver.json()


async def _recv_until(ws, expected_type: str, timeout: float = 3.0) -> dict:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            raise TimeoutError(f"Timed out waiting for {expected_type}")
        raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
        msg = json.loads(raw)
        if msg.get("type") == expected_type:
            return msg


async def _connect_agent(ws_url: str, token: str, session_id: str):
    return await websockets.asyncio.client.connect(
        f"{ws_url}?session_id={session_id}",
        additional_headers={"Authorization": f"Bearer {token}"},
        close_timeout=1,
    )


@pytest.mark.anyio
async def test_agent_authentication_accepts_agent_token_and_rejects_bad_tokens(monkeypatch):
    async with run_live_server(monkeypatch) as server:
        async with httpx.AsyncClient(base_url=server.base_url) as client:
            api_key, _, receiver = await _create_user_and_agents(client)

        ws = await _connect_agent(server.ws_url, receiver["agent_token"], "auth-ok")
        try:
            msg = await _recv_until(ws, MessageType.SESSION_RESUME_RESULT.value)
            assert msg["payload"]["connection_id"]
        finally:
            await ws.close()

        for label, headers in [
            ("missing token", {}),
            ("api key as agent token", {"Authorization": f"Bearer {api_key}"}),
            ("wrong token", {"Authorization": "Bearer agt_sk_wrong"}),
        ]:
            ws = await websockets.asyncio.client.connect(
                f"{server.ws_url}?session_id=bad-{uuid.uuid4().hex}",
                additional_headers=headers,
                close_timeout=1,
            )
            try:
                error = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
                assert error["type"] == MessageType.ERROR.value, label
                assert error["payload"]["code"] == "INVALID_TOKEN", label
            finally:
                await ws.close()


@pytest.mark.anyio
async def test_online_task_delivery_and_ack_updates_message_status(monkeypatch):
    async with run_live_server(monkeypatch) as server:
        async with httpx.AsyncClient(base_url=server.base_url) as client:
            api_key, sender, receiver = await _create_user_and_agents(client)
            headers = {"Authorization": f"Bearer {api_key}"}

            ws = await _connect_agent(server.ws_url, receiver["agent_token"], "online-delivery")
            try:
                await _recv_until(ws, MessageType.SESSION_RESUME_RESULT.value)
                created = await client.post(
                    "/v1/tasks",
                    json={
                        "assigned_to": receiver["agent_number"],
                        "from_agent_number": sender["agent_number"],
                        "payload": {"kind": "echo", "text": "hello"},
                    },
                    headers=headers,
                )
                assert created.status_code == 201
                task = created.json()

                delivered = await _recv_until(ws, MessageType.TASK_REQUEST.value)
                assert delivered["task_id"] == task["task_id"]
                assert delivered["message_id"] == task["message_id"]
                assert delivered["payload"] == {"kind": "echo", "text": "hello"}

                await ws.send(
                    json.dumps(
                        {
                            "type": MessageType.ACK.value,
                            "message_id": str(uuid.uuid4()),
                            "payload": {"message_id": delivered["message_id"]},
                        }
                    )
                )

                for _ in range(20):
                    messages = await client.get(f"/v1/tasks/{task['task_id']}/messages", headers=headers)
                    assert messages.status_code == 200
                    status = messages.json()["messages"][0]["delivery_status"]
                    if status == DeliveryStatus.ACKED.value:
                        break
                    await asyncio.sleep(0.1)
                assert status == DeliveryStatus.ACKED.value
            finally:
                await ws.close()


@pytest.mark.anyio
async def test_offline_queue_and_session_resume_redeliver_unacked_message(monkeypatch):
    async with run_live_server(monkeypatch) as server:
        async with httpx.AsyncClient(base_url=server.base_url) as client:
            api_key, sender, receiver = await _create_user_and_agents(client)
            headers = {"Authorization": f"Bearer {api_key}"}

            created = await client.post(
                "/v1/tasks",
                json={
                    "assigned_to": receiver["agent_number"],
                    "from_agent_number": sender["agent_number"],
                    "payload": {"offline": True},
                },
                headers=headers,
            )
            assert created.status_code == 201
            task = created.json()

            ws = await _connect_agent(server.ws_url, receiver["agent_token"], "resume-e2e")
            first_delivery = await _recv_until(ws, MessageType.TASK_REQUEST.value)
            assert first_delivery["message_id"] == task["message_id"]
            await ws.close()

            ws2 = await _connect_agent(server.ws_url, receiver["agent_token"], "resume-e2e")
            try:
                redelivery = await _recv_until(ws2, MessageType.TASK_REQUEST.value)
                assert redelivery["message_id"] == first_delivery["message_id"]
                await ws2.send(
                    json.dumps(
                        {
                            "type": MessageType.ACK.value,
                            "message_id": str(uuid.uuid4()),
                            "payload": {"message_id": redelivery["message_id"]},
                        }
                    )
                )
            finally:
                await ws2.close()
