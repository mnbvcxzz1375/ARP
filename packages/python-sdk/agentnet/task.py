"""TaskContext: per-task state exposed to user handler."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine

from .session_store import SessionStore
from .types import MessageType, TaskStatus

logger = logging.getLogger(__name__)

SendFn = Callable[..., Coroutine[Any, Any, str]]

#: Seals a reply body into a SealedMessage; returns None when the peer's
#: key material is unavailable (the caller must then NOT send plaintext).
SealFn = Callable[[dict[str, Any]], "Any"]


class TaskContext:
    """Per-task context passed to a user task_handler.

    The handler receives this object and can:
        await ctx.accept()
        await ctx.progress("Running analysis...", progress_pct=50)
        await ctx.result({"output": "done"})
        await ctx.fail("Something went wrong")
        await ctx.request_approval("shell", "rm -rf /", reason="Dangerous")

    M2: when the task arrived as a sealed e2ee message, ``seal_fn`` is
    set and ``result()`` seals the reply — the plaintext reply body
    rides in ``encrypted_payload`` and the platform-visible payload
    stays routing metadata only. If sealing is impossible the reply is
    never sent as plaintext: the task fails with an explicit error
    instead (fail closed).
    """

    def __init__(
        self,
        task_id: str,
        payload: dict[str, Any],
        session_store: SessionStore,
        send_fn: SendFn,
        seal_fn: SealFn | None = None,
    ) -> None:
        self.task_id = task_id
        self.payload = payload
        self._session_store = session_store
        self._send = send_fn
        self._seal = seal_fn
        self._status: str = TaskStatus.CREATED

    @property
    def status(self) -> str:
        return self._status

    # ------------------------------------------------------------------
    # lifecycle actions
    # ------------------------------------------------------------------

    async def accept(self) -> None:
        """Accept the task and transition to running."""
        if self._status not in (TaskStatus.CREATED, TaskStatus.QUEUED):
            logger.warning("Cannot accept task %s in status %s", self.task_id, self._status)
            return
        await self._send(MessageType.TASK_ACCEPTED, {"task_id": self.task_id})
        self._status = TaskStatus.RUNNING
        self._session_store.add_running_task(self.task_id)
        logger.info("Task %s accepted -> running", self.task_id)

    async def progress(
        self,
        message: str,
        *,
        progress_pct: int | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Report progress."""
        payload: dict[str, Any] = {"task_id": self.task_id, "message": message}
        if progress_pct is not None:
            payload["progress_pct"] = progress_pct
        if data is not None:
            payload["data"] = data
        await self._send(MessageType.TASK_PROGRESS, payload)

    async def result(self, result: dict[str, Any]) -> None:
        """Report successful completion.

        For an e2ee task the reply is sealed: the platform-visible WS
        payload carries only routing metadata (``task_id``) and the
        plaintext body rides in ``encrypted_payload``. If the seal is
        unavailable the reply is never downgraded to plaintext — the
        task fails closed with an explicit error.
        """
        if self._seal is not None:
            body = {"task_id": self.task_id, "result": result}
            sealed = self._seal(body)
            if sealed is None:
                await self._send(
                    MessageType.TASK_FAILED,
                    {
                        "task_id": self.task_id,
                        "error_message": (
                            "E2EE_REPLY_UNAVAILABLE: cannot seal the reply "
                            "(peer key material missing)"
                        ),
                    },
                )
                self._status = TaskStatus.FAILED
                self._session_store.remove_running_task(self.task_id)
                logger.warning("Task %s reply could not be sealed", self.task_id)
                return
            await self._send(
                MessageType.TASK_RESULT, {"task_id": self.task_id}, sealed=sealed
            )
            self._status = TaskStatus.COMPLETED
            self._session_store.remove_running_task(self.task_id)
            logger.info("Task %s completed (sealed reply)", self.task_id)
            return
        await self._send(MessageType.TASK_RESULT, {"task_id": self.task_id, "result": result})
        self._status = TaskStatus.COMPLETED
        self._session_store.remove_running_task(self.task_id)
        logger.info("Task %s completed", self.task_id)

    async def fail(self, error_message: str) -> None:
        """Report failure."""
        await self._send(MessageType.TASK_FAILED, {"task_id": self.task_id, "error_message": error_message})
        self._status = TaskStatus.FAILED
        self._session_store.remove_running_task(self.task_id)
        logger.info("Task %s failed: %s", self.task_id, error_message)

    # ------------------------------------------------------------------
    # approval
    # ------------------------------------------------------------------

    async def request_approval(
        self,
        action_kind: str,
        action_preview: str | None = None,
        *,
        risk_level: str = "medium",
        reason: str | None = None,
        expires_in_seconds: int = 120,
    ) -> None:
        """Request human-in-the-loop approval for a high-risk action."""
        payload: dict[str, Any] = {
            "task_id": self.task_id,
            "risk_level": risk_level,
            "action": {
                "kind": action_kind,
                "preview": action_preview,
            },
            "expires_in_seconds": expires_in_seconds,
        }
        if reason:
            payload["reason"] = reason
        await self._send(MessageType.APPROVAL_REQUEST, payload)
        self._status = TaskStatus.AWAITING_APPROVAL
        logger.info("Task %s awaiting approval: %s", self.task_id, action_kind)
