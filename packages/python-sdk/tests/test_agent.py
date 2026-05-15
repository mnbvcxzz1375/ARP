"""Tests for Agent runtime (unit, no API)."""

import os
import tempfile

import pytest

from agentnet.agent import Agent


class TestAgentUnit:
    def test_from_env_reads_token(self, monkeypatch):
        monkeypatch.setenv("AGENTNET_AGENT_TOKEN", "agt_sk_test123")
        monkeypatch.setenv("AGENTNET_BASE_URL", "http://localhost:8000")
        agent = Agent()
        assert agent._token == "agt_sk_test123"
        # Token is NOT in the URL (sent via Authorization header)
        assert "token=" not in agent._ws_url
        assert "session_id=" not in agent._ws_url

    def test_missing_token_rejected_by_validation(self):
        agent = Agent()
        agent._token = ""
        with pytest.raises(ValueError, match="AGENTNET_AGENT_TOKEN"):
            agent._validate_token()

    def test_invalid_token_prefix_rejected(self):
        agent = Agent()
        agent._token = "not_a_real_token"
        with pytest.raises(ValueError, match="AGENTNET_AGENT_TOKEN"):
            agent._validate_token()

    def test_task_handler_decorator(self):
        agent = Agent()

        called = []

        @agent.task_handler
        async def my_handler(ctx):
            called.append(ctx)

        assert agent._task_handler is my_handler

    def test_ws_url_no_token_leak(self):
        agent = Agent(
            base_url="http://relay.example:9000",
            agent_token="agt_sk_abc",
        )
        # Token should NOT appear in ws_url
        assert agent._ws_url == "ws://relay.example:9000/v1/ws"
        assert "agt_sk_abc" not in agent._ws_url
        assert "token" not in agent._ws_url
