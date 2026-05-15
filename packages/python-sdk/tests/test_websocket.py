"""Tests for AgentWebSocket (unit tests, no network)."""

import json
import tempfile
import os

import pytest

from agentnet.session_store import SessionStore
from agentnet.websocket import AgentWebSocket
from agentnet.types import MessageType


class TestAgentWebSocketStatic:
    def test_build_message_format(self):
        msg = AgentWebSocket._build_message("task.progress", {"pct": 50})
        assert msg["type"] == "task.progress"
        assert msg["payload"] == {"pct": 50}
        assert "message_id" in msg
        assert "timestamp" in msg
        assert len(msg["message_id"]) > 0

    def test_handler_registration(self):
        tmp = tempfile.mktemp(suffix=".json")
        try:
            store = SessionStore(tmp)
            ws = AgentWebSocket(store)

            called_with = []

            async def handler(payload):
                called_with.append(payload)

            assert ws._on_task_request is None
            ws.on_task_request(handler)
            assert ws._on_task_request is handler

            ws.on_connection_request(handler)
            assert ws._on_connection_request is handler

            ws.on_approval_request(handler)
            assert ws._on_approval_request is handler
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_connected_property_when_disconnected(self):
        tmp = tempfile.mktemp(suffix=".json")
        try:
            store = SessionStore(tmp)
            ws = AgentWebSocket(store)
            # Not connected
            assert not ws.connected
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_session_id_consistency(self):
        tmp = tempfile.mktemp(suffix=".json")
        try:
            store = SessionStore(tmp)
            ws = AgentWebSocket(store)
            sid = ws.session_id
            assert len(sid) > 0
            assert ws.session_id == sid  # stable
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
