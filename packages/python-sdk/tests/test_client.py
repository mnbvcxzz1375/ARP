"""Tests for REST Client (unit, no network)."""

import httpx
import pytest

from agentnet.client import AgentNetError, Client


class TestClientUnit:
    def test_headers_include_auth(self):
        client = Client(api_key="an_key_secret")
        h = client._headers()
        assert h["Authorization"] == "Bearer an_key_secret"
        assert h["Content-Type"] == "application/json"

    def test_default_base_url(self, monkeypatch):
        monkeypatch.delenv("AGENTNET_BASE_URL", raising=False)
        client = Client()
        assert client.base_url == "http://localhost:8000"

    def test_env_base_url(self, monkeypatch):
        monkeypatch.setenv("AGENTNET_BASE_URL", "http://api.example:9000")
        client = Client()
        assert client.base_url == "http://api.example:9000"

    def test_from_env(self):
        client = Client.from_env()
        assert isinstance(client, Client)

    def test_check_success(self):
        client = Client()
        resp = httpx.Response(200, json={"ok": True})
        result = client._check(resp)
        assert result == {"ok": True}

    def test_check_error_with_code(self):
        client = Client()
        resp = httpx.Response(
            400,
            json={"error": {"code": "INVALID_TOKEN", "message": "Bad token"}},
        )
        with pytest.raises(AgentNetError) as exc:
            client._check(resp)
        assert exc.value.code == "INVALID_TOKEN"
        assert exc.value.status_code == 400
        assert "Bad token" in str(exc.value)

    def test_check_error_without_json_body(self):
        client = Client()
        resp = httpx.Response(500, content=b"Internal Server Error")
        with pytest.raises(AgentNetError) as exc:
            client._check(resp)
        assert exc.value.code == "UNKNOWN"
        assert exc.value.status_code == 500

    def test_context_manager(self):
        with Client() as c:
            assert isinstance(c, Client)

    def test_agentnet_error_repr(self):
        err = AgentNetError("TASK_NOT_FOUND", "No such task", 404)
        assert str(err) == "[TASK_NOT_FOUND] No such task"
        assert err.code == "TASK_NOT_FOUND"
        assert err.status_code == 404

    def test_create_task_includes_sender_agent_number(self, monkeypatch):
        captured = {}
        client = Client()

        def fake_post(path, body=None):
            captured["path"] = path
            captured["body"] = body
            return {"task_id": "task-1"}

        monkeypatch.setattr(client, "_post", fake_post)

        client.create_task(
            "AN-GLOBAL-TARGET-1",
            from_agent_number="AN-GLOBAL-SENDER-1",
            payload={"x": 1},
            idempotency_key="idem-1",
        )

        assert captured["path"] == "/v1/tasks"
        assert captured["body"]["assigned_to"] == "AN-GLOBAL-TARGET-1"
        assert captured["body"]["from_agent_number"] == "AN-GLOBAL-SENDER-1"
        assert captured["body"]["idempotency_key"] == "idem-1"
