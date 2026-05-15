"""Subprocess runner with output streaming and safety enforcement."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
from typing import Any, AsyncIterator

from .config import OpenClawConfig
from .safety import (
    SafetyError,
    sanitize_env,
    truncate_output,
)

logger = logging.getLogger(__name__)


class RunnerError(Exception):
    """Raised when the subprocess runner encounters an error."""

    def __init__(self, message: str, exit_code: int | None = None) -> None:
        self.exit_code = exit_code
        super().__init__(message)


class OpenClawRunner:
    """Runs an OpenClaw CLI command as a subprocess with streaming output.

    In production mode, expects a real OpenClaw binary. If the binary is
    missing, the runner fails explicitly — it does NOT fall back to a mock.

    A test runner is provided separately in tests/ for test-only usage.
    """

    MAX_OUTPUT_BYTES = 1_048_576  # 1 MiB default

    def __init__(self, config: OpenClawConfig) -> None:
        self._config = config
        self._command = config.command

    async def run(
        self,
        args: list[str],
        *,
        working_dir: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Run OpenClaw CLI and stream output line by line.

        Yields progress dicts: {"type": "stdout"|"stderr"|"exit", ...}

        Raises RunnerError if the binary is missing (no fallback).
        """
        # Verify binary exists
        if not await self._binary_exists():
            raise RunnerError(
                f"OpenClaw CLI binary '{self._command}' not found. "
                "Install OpenClaw or configure a valid command path."
            )

        # Build environment
        env = sanitize_env(
            env=self._config.env_vars if self._config.env_policy == "minimal" else None,
            pass_env=list(self._config.pass_env) if self._config.pass_env else None,
        )

        cwd = working_dir or self._config.working_dir
        full_cmd = [self._command] + args

        logger.info("Running OpenClaw: %s (cwd=%s)", " ".join(full_cmd), cwd)

        try:
            proc = await asyncio.create_subprocess_exec(
                *full_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=cwd,
            )
        except FileNotFoundError:
            raise RunnerError(
                f"OpenClaw CLI binary '{self._command}' not found at execution time."
            )

        try:
            total_stdout = 0
            total_stderr = 0
            total_limit = self.MAX_OUTPUT_BYTES
            done = asyncio.Event()

            async def read_stream(stream, label: str):
                nonlocal total_stdout, total_stderr
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    text = line.decode("utf-8", errors="replace").rstrip("\n\r")
                    truncated_line, was_cut = truncate_output(text, total_limit // 100)
                    if label == "stdout":
                        total_stdout += len(text.encode("utf-8", errors="replace"))
                    else:
                        total_stderr += len(text.encode("utf-8", errors="replace"))

                    if total_stdout + total_stderr > total_limit:
                        if not done.is_set():
                            done.set()
                        break

                    yield (label, truncated_line, was_cut)

            async def collect(stream, label: str) -> list[dict[str, Any]]:
                chunks: list[dict[str, Any]] = []
                async for lbl, line, was_cut in read_stream(stream, label):
                    if done.is_set():
                        break
                    chunks.append({"type": lbl, "line": line, "truncated": was_cut})
                return chunks

            # Read stdout and stderr concurrently to avoid pipe-buffer deadlock
            task_stdout = asyncio.create_task(collect(proc.stdout, "stdout"))
            task_stderr = asyncio.create_task(collect(proc.stderr, "stderr"))

            stdout_chunks, stderr_chunks = await asyncio.gather(task_stdout, task_stderr)

            # Yield chunks in order: stdout first, then stderr
            for chunk in stdout_chunks:
                yield chunk
            for chunk in stderr_chunks:
                yield chunk

            if done.is_set():
                yield {"type": "warning", "message": "Max output size reached, output truncated"}

        finally:
            # Always clean up the subprocess
            try:
                proc.terminate()
                await proc.wait()
            except Exception:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass

        # Check exit code after cleanup
        exit_code = proc.returncode if proc.returncode is not None else -1
        yield {"type": "exit", "code": exit_code}

    async def _binary_exists(self) -> bool:
        """Check if the configured command binary exists."""
        if os.path.isabs(self._command):
            return os.path.isfile(self._command) and os.access(self._command, os.X_OK)
        which = shutil.which(self._command)
        return which is not None
