"""CLI config manager tests."""

import json
import os
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from agentnet_cli.config import ConfigManager
from agentnet_cli.main import main


class TestConfigManager:
    def test_defaults(self):
        tmp = tempfile.mktemp(suffix=".json")
        try:
            cfg = ConfigManager(tmp)
            assert cfg.base_url == "http://localhost:8000"
            assert cfg.api_key == ""
            assert cfg.agent_token == ""
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_set_and_get(self):
        tmp = tempfile.mktemp(suffix=".json")
        try:
            cfg = ConfigManager(tmp)
            cfg.set("api_key", "an_key_secret")
            assert cfg.get("api_key") == "an_key_secret"
            loaded = json.loads(Path(tmp).read_text())
            assert loaded["api_key"] == "an_key_secret"
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_set_credentials(self):
        tmp = tempfile.mktemp(suffix=".json")
        try:
            cfg = ConfigManager(tmp)
            cfg.set_credentials("http://example.com:9000", "an_key_abc")
            assert cfg.base_url == "http://example.com:9000"
            assert cfg.api_key == "an_key_abc"
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def test_persistence(self):
        tmp = tempfile.mktemp(suffix=".json")
        try:
            cfg1 = ConfigManager(tmp)
            cfg1.set("agent_token", "agt_sk_test")

            cfg2 = ConfigManager(tmp)
            assert cfg2.get("agent_token") == "agt_sk_test"
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)


class TestCLIHelp:
    def test_main_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "AgentNet" in result.output

    def test_agent_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["agent", "--help"])
        assert result.exit_code == 0
        assert "create" in result.output

    def test_task_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["task", "--help"])
        assert result.exit_code == 0
        assert "send" in result.output

    def test_task_send_help_includes_sender_agent(self):
        runner = CliRunner()
        result = runner.invoke(main, ["task", "send", "--help"])
        assert result.exit_code == 0
        assert "--from-agent-number" in result.output

    def test_approve_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["approve", "--help"])
        assert result.exit_code == 0
        assert "accept" in result.output

    def test_connect_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["connect", "--help"])
        assert result.exit_code == 0
        assert "token" in result.output

    def test_login_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["login", "--help"])
        assert result.exit_code == 0
        assert "base-url" in result.output

    def test_key_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["key", "--help"])
        assert result.exit_code == 0
        assert "revoke" in result.output

    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output
