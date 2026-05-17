"""SDK WebSocket integration tests against a real local WebSocket server."""

from __future__ import annotations

import asyncio
import json
import socket
from typing import Any

import pytest
from websockets.asyncio.server import serve

from agentnet.idempotency import IdempotencyCache
from agentnet.session_store import SessionStore
from agentnet.types import MessageType
from agentnet.websocket import AgentWebSocket


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.mark.asyncio
async def test_sdk_auto_ack_session_resume_and_deduplicates_task_handler(tmp_path):
    received_acks: list[dict[str, Any]] = []
    handler_calls: list[dict[str, Any]] = []
    done = asyncio.Event()

    async def ws_handler(conn):
        resume = json.loads(await asyncio.wait_for(conn.recv(), timeout=3))
        assert resume["type"] == MessageType.SESSION_RESUME
        assert resume["payload"]["session_id"] == "sdk-integration-session"

        await conn.send(
            json.dumps(
                {
                    "type": MessageType.SESSION_RESUME_RESULT,
                    "message_id": "resume-result-1",
                    "payload": {"connection_id": "local-test", "pending_delivered": 0},
                }
            )
        )

        task_request = {
            "type": MessageType.TASK_REQUEST,
            "message_id": "message-sdk-1",
            "task_id": "task-sdk-1",
            "payload": {"kind": "echo", "text": "hello"},
        }

        await conn.send(json.dumps(task_request))
        received_acks.append(json.loads(await asyncio.wait_for(conn.recv(), timeout=3)))

        await conn.send(json.dumps(task_request))
        received_acks.append(json.loads(await asyncio.wait_for(conn.recv(), timeout=3)))
        done.set()

    async def on_task_request(message: dict[str, Any]) -> None:
        handler_calls.append(message)

    port = _free_port()
    async with serve(ws_handler, "127.0.0.1", port):
        store = SessionStore(tmp_path / "session.json")
        store.open()
        ws = AgentWebSocket(store, idempotency_cache=IdempotencyCache())
        ws.on_task_request(on_task_request)
        await ws.connect(
            f"ws://127.0.0.1:{port}/v1/ws",
            session_id="sdk-integration-session",
            token="agt_sk_local",
        )
        try:
            await asyncio.wait_for(done.wait(), timeout=5)
        finally:
            await ws.disconnect()

    assert len(handler_calls) == 1
    assert handler_calls[0]["task_id"] == "task-sdk-1"
    assert handler_calls[0]["payload"] == {"kind": "echo", "text": "hello"}
    assert store.last_message_id == "message-sdk-1"

    assert [ack["type"] for ack in received_acks] == [MessageType.ACK, MessageType.ACK]
    assert [ack["payload"]["message_id"] for ack in received_acks] == [
        "message-sdk-1",
        "message-sdk-1",
    ]
