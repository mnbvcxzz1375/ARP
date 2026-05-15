"""Agent runtime: WebSocket client + task handler integration."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Awaitable, Callable, Union

from .client import Client
from .idempotency import IdempotencyCache
from .session_store import SessionStore
from .task import TaskContext
from .types import MessageType
from .websocket import AgentWebSocket

logger = logging.getLogger(__name__)

TaskHandler = Callable[[TaskContext], Awaitable[None]]
_NOT_SET = object()


class Agent:
    """AgentNet agent runtime.

    Usage:
        agent = Agent.from_env()

        @agent.task_handler
        async def handle_echo(ctx: TaskContext):
            await ctx.accept()
            await ctx.progress("echoing...", progress_pct=50)
            await ctx.result({"echo": ctx.payload})

        agent.run()

    Environment variables:
        AGENTNET_BASE_URL    - relay base URL (default http://localhost:8000)
        AGENTNET_WS_URL      - WebSocket endpoint (default ws://localhost:8000/v1/ws)
        AGENTNET_AGENT_TOKEN - agent token (agt_sk_...)
        AGENTNET_SESSION_FILE - session store path (default ./agentnet_session.json)
    """

    def __init__(
        self,
        base_url: str | None = None,
        ws_url: str | None = None,
        agent_token: str | None = None,
        session_file: str | Path | None = None,
    ) -> None:
        self._base_url = base_url or os.getenv("AGENTNET_BASE_URL", "http://localhost:8000")
        ws_base = ws_url or os.getenv("AGENTNET_WS_URL") or self._base_url.replace("http", "ws")
        self._token = agent_token or os.getenv("AGENTNET_AGENT_TOKEN", "")
        self._session_store = SessionStore(
            session_file or os.getenv("AGENTNET_SESSION_FILE", "agentnet_session.json")
        )
        self._idempotency = IdempotencyCache()
        self._ws = AgentWebSocket(self._session_store, idempotency_cache=self._idempotency)

        # Build WS URL (token is NOT in the URL — sent via Authorization header)
        self._ws_url = ws_base.rstrip("/") + "/v1/ws"

        self._task_handler: TaskHandler | None = None
        self._client: Client | None = None

    # ------------------------------------------------------------------
    # decorator
    # ------------------------------------------------------------------

    def task_handler(self, fn: TaskHandler) -> TaskHandler:
        """Register a function as the task handler."""
        self._task_handler = fn
        return fn

    # ------------------------------------------------------------------
    # factories
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> "Agent":
        return cls()

    # ------------------------------------------------------------------
    # validation
    # ------------------------------------------------------------------

    def _validate_token(self) -> None:
        """Raise ValueError if the token is missing or malformed."""
        if not self._token or not self._token.startswith("agt_sk_"):
            raise ValueError(
                "AGENTNET_AGENT_TOKEN must be set to a valid agent token (agt_sk_...). "
                "Create an agent via the REST API or CLI first."
            )

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Run the agent (blocking)."""
        asyncio.run(self.start())

    async def start(self) -> None:
        """Async start: loads session, connects, and runs the message loop."""
        self._validate_token()

        self._session_store.open()
        self._client = Client(base_url=self._base_url)

        # Seed idempotency cache from session (if any)
        last_mid = self._session_store.last_message_id
        if last_mid:
            self._idempotency.add(last_mid)

        # Register WS handlers
        self._ws.on_task_request(self._handle_task_request)
        self._ws.on_connection_request(self._handle_connection_request)
        self._ws.on_approval_request(self._handle_approval_request)

        # Connect (token via Authorization header)
        await self._ws.connect(
            url=self._ws_url,
            session_id=self._ws.session_id,
            token=self._token,
        )

        # Wait until disconnected and not reconnecting
        try:
            while self._ws._running:
                await asyncio.sleep(0.5)
        except KeyboardInterrupt:
            logger.info("Agent shutting down on interrupt")
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """Clean shutdown: disconnect WS, close REST client, save session."""
        await self._ws.disconnect()
        if self._client:
            self._client.close()
        self._session_store.close()
        logger.info("Agent shut down")

    # ------------------------------------------------------------------
    # internal handlers
    # ------------------------------------------------------------------

    async def _handle_task_request(self, msg: dict[str, Any]) -> None:
        # msg is the full ARP envelope; task_id is at the top level,
        # task payload is nested inside msg["payload"].
        task_id = msg.get("task_id", "")
        task_payload = msg.get("payload", {}) or {}

        if not task_id:
            logger.warning("Received task.request without task_id")
            return

        if not self._task_handler:
            logger.warning("No task_handler registered; ignoring task %s", task_id)
            return

        ctx = TaskContext(
            task_id=task_id,
            payload=task_payload,
            session_store=self._session_store,
            send_fn=self._ws.send_message,
        )

        logger.info("Dispatching task %s to handler", task_id)
        try:
            await self._task_handler(ctx)
        except Exception as exc:
            logger.exception("Task handler raised for %s", task_id)
            if ctx._status not in ("completed", "failed", "cancelled", "rejected"):
                try:
                    await ctx.fail(str(exc))
                except Exception:
                    logger.exception("Failed to report task failure for %s", task_id)

    async def _handle_connection_request(self, msg: dict[str, Any]) -> None:
        payload = msg.get("payload", {}) or {}
        from_agent = payload.get("from", "unknown")
        logger.info("Connection request from %s (auto-rejecting in SDK default mode)", from_agent)
        await self._ws.send_message("connection.rejected", {"from_agent": from_agent, "reason": "SDK default: auto-reject"})

    async def _handle_approval_request(self, msg: dict[str, Any]) -> None:
        payload = msg.get("payload", {}) or {}
        task_id = payload.get("task_id", msg.get("task_id", "unknown"))
        risk_level = payload.get("risk_level", "unknown")
        action = payload.get("action", {})
        logger.warning(
            "Approval request for task %s: risk=%s action=%s (CLI hook placeholder)",
            task_id, risk_level, action.get("kind"),
        )
