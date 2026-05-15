"""WebSocket client for AgentNet with auto-ack, heartbeat, and reconnect."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import uuid
from datetime import UTC, datetime
from typing import Any, Callable, Coroutine

import websockets
import websockets.asyncio.client
from websockets.asyncio.client import ClientConnection

from .idempotency import IdempotencyCache
from .session_store import SessionStore
from .types import MessageType

logger = logging.getLogger(__name__)

MessageHandler = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class AgentWebSocket:
    """WebSocket client that auto-handles ack, heartbeat, reconnect, and resume.

    Lifecycle:
        1. connect(url, session_id, token) -> handshake
        2. Auto-starts presence.heartbeat loop
        3. On disconnect, schedules reconnect with exponential backoff
        4. On reconnect, sends session.resume and replays pending messages

    Security: token is sent via Authorization header, not URL query string.
    """

    HEARTBEAT_INTERVAL = 15  # seconds
    TASK_HEARTBEAT_INTERVAL = 20  # seconds
    RECONNECT_BASE_DELAY = 0.5
    RECONNECT_MAX_DELAY = 60.0
    RECONNECT_JITTER = 0.3  # 30% jitter

    def __init__(
        self,
        session_store: SessionStore,
        *,
        idempotency_cache: IdempotencyCache | None = None,
    ) -> None:
        self._url: str | None = None
        self._token: str | None = None
        # Reuse persisted session_id if available (for resume after restart)
        self._session_id = session_store.session_id or str(uuid.uuid4())
        self._ws: ClientConnection | None = None
        self._running = False
        self._reconnect_delay = self.RECONNECT_BASE_DELAY

        # background tasks
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._task_heartbeat_task: asyncio.Task[None] | None = None
        self._receive_task: asyncio.Task[None] | None = None
        self._reconnect_task: asyncio.Task[None] | None = None

        # storage
        self._session_store = session_store
        self._idempotency = idempotency_cache or IdempotencyCache()

        # registered handler
        self._on_task_request: MessageHandler | None = None
        self._on_connection_request: MessageHandler | None = None
        self._on_approval_request: MessageHandler | None = None

        # event for tracking connection state
        self._connected_event = asyncio.Event()

    # ------------------------------------------------------------------
    # properties
    # ------------------------------------------------------------------

    @property
    def connected(self) -> bool:
        return self._ws is not None and self._ws.state.value == 1  # OPEN

    @property
    def session_id(self) -> str:
        return self._session_id

    # ------------------------------------------------------------------
    # repr (safe - masks token)
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"AgentWebSocket(session_id={self._session_id!r}, "
            f"connected={self.connected})"
        )

    # ------------------------------------------------------------------
    # handler registration
    # ------------------------------------------------------------------

    def on_task_request(self, handler: MessageHandler) -> None:
        self._on_task_request = handler

    def on_connection_request(self, handler: MessageHandler) -> None:
        self._on_connection_request = handler

    def on_approval_request(self, handler: MessageHandler) -> None:
        self._on_approval_request = handler

    # ------------------------------------------------------------------
    # connect / disconnect
    # ------------------------------------------------------------------

    async def connect(
        self,
        url: str,
        session_id: str,
        token: str,
    ) -> None:
        """Connect to the relay WebSocket endpoint.

        Token is sent via Authorization header (not URL query) to avoid
        leaking agent tokens into server access logs.

        *url* example: ws://localhost:8000/v1/ws
        Session ID is appended as a query parameter (non-sensitive).
        """
        self._session_id = session_id
        self._session_store.set_session_id(session_id)
        self._url = f"{url.rstrip('/')}?session_id={session_id}"
        self._token = token
        self._running = True
        self._reconnect_delay = self.RECONNECT_BASE_DELAY
        await self._do_connect()

    async def disconnect(self) -> None:
        """Graceful shutdown. Cancels all background tasks."""
        self._running = False
        await self._cancel_all_tasks()
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
        self._connected_event.clear()

    # ------------------------------------------------------------------
    # send helpers
    # ------------------------------------------------------------------

    async def send_message(self, msg_type: str, payload: dict[str, Any] | None = None) -> str:
        """Send a typed WS message; returns the generated message_id."""
        msg = self._build_message(msg_type, payload or {})
        raw = json.dumps(msg)
        if self._ws and self.connected:
            await self._ws.send(raw)
        else:
            raise ConnectionError("WebSocket not connected")
        return msg["message_id"]

    async def ack(self, message_id: str) -> None:
        await self.send_message(MessageType.ACK, {"message_id": message_id})

    # ------------------------------------------------------------------
    # private: connection lifecycle
    # ------------------------------------------------------------------

    async def _do_connect(self) -> None:
        try:
            self._ws = await websockets.asyncio.client.connect(
                self._url or "",
                additional_headers={"Authorization": f"Bearer {self._token}"},
                close_timeout=5,
                max_size=2**22,  # 4 MB
            )
            self._connected_event.set()
            logger.info("WebSocket connected: session=%s", self._session_id)

            # Immediately try to resume
            await self._send_session_resume()

            # Start background loops
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            self._task_heartbeat_task = asyncio.create_task(self._task_heartbeat_loop())
            self._receive_task = asyncio.create_task(self._receive_loop())

        except Exception as exc:
            logger.warning("WebSocket connect failed: %s", exc)
            if self._running:
                await self._schedule_reconnect()

    async def _receive_loop(self) -> None:
        """Read messages from the WebSocket until disconnected."""
        try:
            assert self._ws is not None
            async for raw in self._ws:
                await self._handle(raw)
        except Exception as exc:
            logger.warning("WebSocket receive error: %s", exc)
        finally:
            self._connected_event.clear()
            self._ws = None
            if self._running:
                await self._schedule_reconnect()

    async def _heartbeat_loop(self) -> None:
        """Periodic presence.heartbeat."""
        while self._running and self.connected:
            await asyncio.sleep(self.HEARTBEAT_INTERVAL)
            if not self.connected or not self._running:
                break
            try:
                await self.send_message(MessageType.PRESENCE_HEARTBEAT)
            except Exception:
                logger.debug("Heartbeat failed; will retry after reconnect")
                break

    async def _task_heartbeat_loop(self) -> None:
        """Periodic task.heartbeat for each running task."""
        while self._running:
            await asyncio.sleep(self.TASK_HEARTBEAT_INTERVAL)
            if not self._running:
                break
            if not self.connected:
                continue
            tasks = list(self._session_store.running_tasks.keys())
            for task_id in tasks:
                if not self.connected or not self._running:
                    break
                try:
                    await self.send_message(
                        MessageType.TASK_HEARTBEAT,
                        {"task_id": task_id},
                    )
                except Exception:
                    break

    async def _schedule_reconnect(self) -> None:
        """Exponential backoff reconnect."""
        if self._reconnect_task and not self._reconnect_task.done():
            return
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def _reconnect_loop(self) -> None:
        while self._running:
            delay = self._reconnect_delay * (1 + random.uniform(-self.RECONNECT_JITTER, self.RECONNECT_JITTER))
            logger.info("Reconnecting in %.1fs (session=%s)", delay, self._session_id)
            await asyncio.sleep(delay)
            if not self._running:
                return
            try:
                await self._do_connect()
                # If connect succeeded, reset backoff
                self._reconnect_delay = self.RECONNECT_BASE_DELAY
                return
            except Exception as exc:
                logger.warning("Reconnect attempt failed: %s", exc)
                self._reconnect_delay = min(
                    self._reconnect_delay * 2,
                    self.RECONNECT_MAX_DELAY,
                )

    async def _send_session_resume(self) -> None:
        last_mid = self._session_store.last_message_id
        await self.send_message(
            MessageType.SESSION_RESUME,
            {
                "session_id": self._session_id,
                "last_message_id": last_mid,
            },
        )

    # ------------------------------------------------------------------
    # private: message handling
    # ------------------------------------------------------------------

    async def _handle(self, raw: str | bytes) -> None:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Received invalid JSON: %s", raw[:200])
            return

        msg_type = msg.get("type", "")
        message_id = msg.get("message_id", "")
        payload = msg.get("payload", {}) or {}

        logger.debug("WS recv: type=%s message_id=%s", msg_type, message_id)

        # Auto-ack all non-ack, non-error, non-heartbeat messages
        if msg_type not in (
            MessageType.ACK,
            MessageType.ERROR,
            MessageType.PRESENCE_HEARTBEAT,
            MessageType.SESSION_RESUME_RESULT,
        ):
            # Deduplicate
            if message_id and self._idempotency.has(message_id):
                logger.debug("Duplicate message_id=%s, re-acking", message_id)
                await self.ack(message_id)
                return
            if message_id:
                self._idempotency.add(message_id)
                self._session_store.set_last_message_id(message_id)
            # Ack
            if message_id:
                await self.ack(message_id)

        # Dispatch — pass the full envelope so handlers can access top-level
        # fields like task_id that the relay places outside the inner payload.
        if msg_type == MessageType.TASK_REQUEST and self._on_task_request:
            await self._on_task_request(msg)
        elif msg_type == MessageType.CONNECTION_REQUEST and self._on_connection_request:
            await self._on_connection_request(msg)
        elif msg_type == MessageType.APPROVAL_REQUEST and self._on_approval_request:
            await self._on_approval_request(msg)
        elif msg_type == MessageType.ERROR:
            logger.error("Server error: %s", payload)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_message(msg_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": msg_type,
            "message_id": str(uuid.uuid4()),
            "timestamp": datetime.now(UTC).isoformat(),
            "payload": payload,
        }

    async def _cancel_all_tasks(self) -> None:
        """Cancel all background tasks including reconnect."""
        for task in (
            self._heartbeat_task,
            self._task_heartbeat_task,
            self._receive_task,
            self._reconnect_task,
        ):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._heartbeat_task = None
        self._task_heartbeat_task = None
        self._receive_task = None
        self._reconnect_task = None
