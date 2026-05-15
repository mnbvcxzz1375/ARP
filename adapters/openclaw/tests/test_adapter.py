"""Tests for OpenClaw adapter safety, runner, and adapter modules."""

import os
import sys
import tempfile

import pytest

from agentnet_openclaw.safety import (
    SafetyError,
    check_path_traversal,
    is_sensitive_env_key,
    resolve_safe,
    review_command,
    sanitize_env,
    truncate_output,
)


class TestPathSafety:
    def test_resolve_safe_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            sub = os.path.join(tmp, "sub")
            os.makedirs(sub)
            resolved = resolve_safe(sub, [tmp], [])
            assert str(resolved).startswith(tmp)

    def test_resolve_safe_denied(self):
        with tempfile.TemporaryDirectory() as allow_dir:
            with tempfile.TemporaryDirectory() as deny_dir:
                with pytest.raises(SafetyError, match="denied"):
                    resolve_safe(deny_dir, [allow_dir], [deny_dir])

    def test_resolve_safe_not_allowed(self):
        with tempfile.TemporaryDirectory() as d1:
            with tempfile.TemporaryDirectory() as d2:
                with pytest.raises(SafetyError, match="not within"):
                    resolve_safe(d2, [d1], [])

    def test_check_path_traversal_detects(self):
        assert check_path_traversal("../etc/passwd") is True
        assert check_path_traversal("..\\windows\\system32") is True
        assert check_path_traversal("normal/path/file.txt") is False


class TestEnvSanitization:
    def test_sensitive_keys_stripped(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-secret")
        monkeypatch.setenv("MY_APP_KEY", "secret2")
        monkeypatch.setenv("SAFE_VAR", "hello")
        monkeypatch.setenv("HOME", "/home/user")

        result = sanitize_env(pass_env=["SAFE_VAR"])

        assert "OPENAI_API_KEY" not in result
        assert "MY_APP_KEY" not in result
        assert "SAFE_VAR" in result
        assert "HOME" in result

    def test_explicit_env_override(self):
        result = sanitize_env(env={"MY_CUSTOM": "val"})
        assert result["MY_CUSTOM"] == "val"

    def test_is_sensitive_env_key(self):
        assert is_sensitive_env_key("API_KEY") is True
        assert is_sensitive_env_key("DATABASE_URL") is True
        assert is_sensitive_env_key("MY_APP_KEY") is True
        assert is_sensitive_env_key("AWS_SECRET_KEY") is True
        assert is_sensitive_env_key("HOME") is False
        assert is_sensitive_env_key("LANG") is False


class TestCommandReview:
    def test_dangerous_commands_detected(self):
        reasons = review_command(["sudo", "rm", "-rf", "/"])
        assert len(reasons) > 0

    def test_safe_commands_pass(self):
        reasons = review_command(["echo", "hello"])
        assert len(reasons) == 0

    def test_chmod_777_rejected(self):
        reasons = review_command(["chmod", "777", "file.txt"])
        assert len(reasons) > 0


class TestOutputTruncation:
    def test_string_within_limit(self):
        data, was_cut = truncate_output("short", 1024)
        assert data == "short"
        assert was_cut is False

    def test_string_exceeds_limit(self):
        data, was_cut = truncate_output("x" * 2000, 1024)
        assert was_cut is True
        assert len(data.encode("utf-8")) <= 1024

    def test_bytes_exceeds_limit(self):
        data, was_cut = truncate_output(b"x" * 2000, 1024)
        assert was_cut is True
        assert len(data) == 1024


class TestRunnerNoBinary:
    @pytest.mark.asyncio
    async def test_missing_binary_fails(self):
        from agentnet_openclaw.config import OpenClawConfig
        from agentnet_openclaw.runner import OpenClawRunner, RunnerError

        config = OpenClawConfig(
            command="nonexistent_openclaw_binary_xyz",
            working_dir="/tmp",
        )
        runner = OpenClawRunner(config)
        with pytest.raises(RunnerError, match="not found"):
            async for _ in runner.run(["--help"]):
                pass

    @pytest.mark.asyncio
    async def test_existing_binary_runs_command(self):
        from agentnet_openclaw.config import OpenClawConfig
        from agentnet_openclaw.runner import OpenClawRunner

        with tempfile.TemporaryDirectory() as tmp:
            config = OpenClawConfig(
                command=sys.executable,
                working_dir=tmp,
            )
            runner = OpenClawRunner(config)

            chunks = []
            async for chunk in runner.run(["-c", "print('openclaw-runner-ok')"], working_dir=tmp):
                chunks.append(chunk)

        stdout = "\n".join(
            chunk.get("line", "")
            for chunk in chunks
            if chunk.get("type") == "stdout"
        )
        exit_chunks = [chunk for chunk in chunks if chunk.get("type") == "exit"]
        assert "openclaw-runner-ok" in stdout
        assert exit_chunks[-1]["code"] == 0


class TestAdapterConfig:
    def test_config_validation(self):
        from agentnet_openclaw.config import AdapterConfig, AgentConfig, OpenClawConfig

        cfg = AdapterConfig(
            agent=AgentConfig(number="AN-GLOBAL-TEST-01"),
            openclaw=OpenClawConfig(
                working_dir="/tmp/test",
                allow_paths=["/tmp/test"],
            ),
        )
        assert cfg.openclaw.working_dir == "/tmp/test"
        assert cfg.openclaw.command == "openclaw"
