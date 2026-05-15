"""OpenClaw Adapter: bridges AgentNet tasks to local OpenClaw CLI executions."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from agentnet_adapter.interface import AdapterContext, AdapterInterface

from .config import AdapterConfig, OpenClawConfig
from .constants import ErrorCode
from .runner import OpenClawRunner, RunnerError
from .safety import SafetyError, check_path_traversal, resolve_safe, review_command

logger = logging.getLogger(__name__)


class OpenClawAdapter(AdapterInterface):
    """Adapter that executes OpenClaw CLI commands in response to AgentNet tasks.

    Workflow:
      1. Receives task.request with payload containing command args
      2. Validates working directory against allow-path / deny-path
      3. Checks high-risk commands and requests approval if needed
      4. Streams stdout/stderr as task.progress
      5. Returns result or failure

    Production safety:
      - Real OpenClaw CLI must exist (no mock fallback)
      - Path traversal is detected and rejected
      - Sensitive env vars are stripped from subprocess env
      - Output exceeding max_output_bytes is truncated
    """

    def __init__(self, config: AdapterConfig) -> None:
        self._config = config
        self._runner = OpenClawRunner(config.openclaw)
        self._running = False
        self._on_progress = None
        self._on_approval = None

    # ------------------------------------------------------------------
    # AdapterInterface
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._running = True
        logger.info("OpenClaw adapter started: agent=%s", self._config.agent.number)

    async def stop(self) -> None:
        self._running = False
        logger.info("OpenClaw adapter stopped")

    async def handle_task(
        self,
        context: AdapterContext,
        content: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Process a task: parse args, validate safety, execute, return result."""
        args = self._parse_args(content)
        if not args:
            return {"error_code": ErrorCode.INVALID_REQUEST, "error": "No command arguments provided in task payload"}

        working_dir = self._resolve_working_dir(context)

        # Safety: check args for dangerous patterns
        full_cmd = [self._config.openclaw.command] + args
        dangerous = review_command(full_cmd)
        if dangerous:
            require_approval = self._config.openclaw.require_approval

            # Only request approval if any of the dangerous patterns match
            # a configured approval category, or if the list is empty (approve all)
            if require_approval:
                reasons_str = "; ".join(dangerous).lower()
                needs_approval = any(
                    action.lower() in reasons_str
                    for action in require_approval
                )
            else:
                # Empty require_approval means don't request approval
                needs_approval = False

            if needs_approval and self._on_approval:
                approved = await self._on_approval(
                    task_id=context.task_id,
                    risk_level="high",
                    action_kind="execute_openclaw",
                    action_preview=" ".join(full_cmd),
                    reason="; ".join(dangerous),
                )
                if not approved:
                    return {"error_code": ErrorCode.APPROVAL_REJECTED, "error": "Approval rejected for dangerous command"}
            elif needs_approval:
                # No approval callback registered and command needs approval
                return {"error_code": ErrorCode.APPROVAL_REQUIRED, "error": "Approval required but no approval handler configured"}

        # Stream execution
        progress_count = 0
        runner_result = {"exit_code": -1, "stdout": "", "stderr": ""}
        stdout_parts: list[str] = []
        stderr_parts: list[str] = []

        try:
            async for chunk in self._runner.run(args, working_dir=working_dir):
                if chunk["type"] == "stdout":
                    stdout_parts.append(chunk.get("line", ""))
                elif chunk["type"] == "stderr":
                    stderr_parts.append(chunk.get("line", ""))
                elif chunk["type"] == "exit":
                    runner_result["exit_code"] = chunk["code"]
                elif chunk["type"] == "warning":
                    if self._on_progress:
                        await self._on_progress(
                            task_id=context.task_id,
                            progress_pct=None,
                            message=f"Warning: {chunk['message']}",
                            data={"type": "warning"},
                        )

                # Send progress periodically (not line-count-based; use timer in production)
                progress_count += 1
                if progress_count % 10 == 0 and self._on_progress:
                    await self._on_progress(
                        task_id=context.task_id,
                        progress_pct=None,
                        message=f"Executing... ({progress_count} lines output)",
                    )

            runner_result["stdout"] = "\n".join(stdout_parts)
            runner_result["stderr"] = "\n".join(stderr_parts)

            if runner_result["exit_code"] != 0:
                return {
                    "error_code": ErrorCode.INTERNAL_ERROR,
                    "error": f"Exit code {runner_result['exit_code']}",
                    "stdout": runner_result["stdout"],
                    "stderr": runner_result["stderr"],
                }

            return {
                "exit_code": runner_result["exit_code"],
                "stdout": runner_result["stdout"],
                "stderr": runner_result["stderr"],
            }

        except RunnerError as exc:
            logger.error("OpenClaw runner error: %s", exc)
            return {"error_code": ErrorCode.INTERNAL_ERROR, "error": str(exc)}
        except SafetyError as exc:
            logger.warning("Safety check failed: %s", exc)
            return {"error_code": ErrorCode.INVALID_REQUEST, "error": f"Safety check: {exc.reason}"}
        except Exception as exc:
            logger.exception("Unexpected error in openclaw adapter")
            return {"error_code": ErrorCode.INTERNAL_ERROR, "error": str(exc)}

    # ------------------------------------------------------------------
    # private
    # ------------------------------------------------------------------

    def _parse_args(self, content: list[dict[str, Any]]) -> list[str]:
        """Extract command args from task content.

        Expects content like:
          [{"mime": "text/plain", "text": "--prompt 'review the code'"}]
        or
          [{"mime": "application/json", "data": {"args": ["--prompt", "review..."]}}]
        """
        for part in content:
            mime = part.get("mime", "")
            if mime == "application/json":
                data = part.get("data", {})
                if isinstance(data, dict) and "args" in data:
                    return data["args"]
            elif mime == "text/plain":
                text = part.get("text", "")
                if text:
                    import shlex
                    try:
                        return shlex.split(text)
                    except ValueError:
                        return text.split()
        return []

    def _resolve_working_dir(self, context: AdapterContext) -> str:
        """Resolve and validate the working directory for this task.

        Uses the configured working_dir and validates against allow/deny paths.
        """
        wd = self._config.openclaw.working_dir

        # Defense-in-depth: explicit traversal check before resolve
        if check_path_traversal(wd):
            raise SafetyError(f"Working directory contains path traversal: {wd}")

        # resolve_safe does canonicalization via Path.resolve()
        resolved = resolve_safe(
            wd,
            self._config.openclaw.allow_paths,
            self._config.openclaw.deny_paths,
        )
        return str(resolved)
