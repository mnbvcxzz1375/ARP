
"""WebSocket connection manager with presence tracking and connection limits."""

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from fastapi import WebSocket
from redis.asyncio import Redis

from app.config import get_settings

logger = logging.getLogger(__name__)

_PRESENCE_KEY_PREFIX = "ws:presence:"


class ConnectionState:
    """Tracks a single WebSocket connection."""

    def __init__(self, websocket: WebSocket, agent_id: uuid.UUID, agent_number: str, session_id: str):
        self.websocket = websocket
        self.agent_id = agent_id
        self.agent_number = agent_number
        self.connection_id = str(uuid.uuid4())
        self.session_id = session_id
        self.last_heartbeat: datetime = datetime.now(UTC)
        self.connected_at: datetime = datetime.now(UTC)


class ConnectionManager:
    """Manages all active WebSocket connections."""

    def __init__(self, redis: Redis):
        self._redis = redis
        self._connections: dict[str, ConnectionState] = {}
        self._agent_connections: dict[uuid.UUID, set[str]] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task | None = None

    @property
    def settings(self):
        return get_settings()

    def _presence_key(self, agent_id: uuid.UUID) -> str:
        return f"{_PRESENCE_KEY_PREFIX}{agent_id}"

    async def _set_redis_presence(self, agent_id: uuid.UUID) -> None:
        key = self._presence_key(agent_id)
        await self._redis.set(
            key, "online", ex=self.settings.ws_heartbeat_timeout_s
        )

    async def _refresh_redis_presence(self, agent_id: uuid.UUID) -> None:
        key = self._presence_key(agent_id)
        await self._redis.expire(key, self.settings.ws_heartbeat_timeout_s)

    async def _remove_redis_presence(self, agent_id: uuid.UUID) -> None:
        key = self._presence_key(agent_id)
        await self._redis.delete(key)

    async def is_agent_online(self, agent_id: uuid.UUID) -> bool:
        key = self._presence_key(agent_id)
        return bool(await self._redis.exists(key))

    async def get_connection_count(self, agent_id: uuid.UUID) -> int:
        async with self._lock:
            conns = self._agent_connections.get(agent_id, set())
            return len(conns)

    async def register(
        self, websocket: WebSocket, agent_id: uuid.UUID,
        agent_number: str, session_id: str
    ) -> ConnectionState:
        from app.exceptions import DomainException
        from app.protocol.constants import ErrorCode

        async with self._lock:
            agent_conns = self._agent_connections.get(agent_id, set())
            if len(agent_conns) >= self.settings.ws_max_connections_per_agent:
                raise DomainException(
                    ErrorCode.RATE_LIMITED,
                    f"Agent {agent_number} has reached max connections "
                    f"({self.settings.ws_max_connections_per_agent})",
                    status_code=429,
                )

            state = ConnectionState(websocket, agent_id, agent_number, session_id)
            self._connections[state.connection_id] = state
            if agent_id not in self._agent_connections:
                self._agent_connections[agent_id] = set()
            self._agent_connections[agent_id].add(state.connection_id)

        await self._set_redis_presence(agent_id)
        logger.info(
            "Agent %s connected (conn_id=%s, session=%s, total=%d)",
            agent_number,
            state.connection_id,
            session_id,
            len(self._agent_connections[agent_id]),
        )
        return state

    async def unregister(self, connection_id: str) -> tuple[uuid.UUID | None, str | None]:
        """Remove a WebSocket connection.

        Returns (agent_id, agent_number) if this was the last connection
        for the agent, otherwise (None, None). Caller should update DB status.
        """
        async with self._lock:
            state = self._connections.pop(connection_id, None)
            if state is None:
                return (None, None)
            agent_conns = self._agent_connections.get(state.agent_id, set())
            agent_conns.discard(connection_id)

            was_last = False
            agent_id = state.agent_id
            agent_number = state.agent_number

            if not agent_conns:
                self._agent_connections.pop(state.agent_id, None)
                await self._remove_redis_presence(state.agent_id)
                was_last = True

            logger.info(
                "Agent %s disconnected (conn_id=%s, remaining=%d)",
                agent_number,
                connection_id,
                len(agent_conns),
            )
            return (agent_id if was_last else None, agent_number if was_last else None)

    async def record_heartbeat(self, connection_id: str) -> None:
        async with self._lock:
            state = self._connections.get(connection_id)
            if state is None:
                return
            state.last_heartbeat = datetime.now(UTC)
            agent_id = state.agent_id
        await self._refresh_redis_presence(agent_id)

    async def start_cleanup_loop(self) -> None:
        if self._cleanup_task is not None:
            return
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self) -> None:
        while True:
            await asyncio.sleep(self.settings.ws_heartbeat_timeout_s / 3)
            now = datetime.now(UTC)
            timeout = self.settings.ws_heartbeat_timeout_s
            stale: list[str] = []

            async with self._lock:
                for conn_id, state in list(self._connections.items()):
                    elapsed = (now - state.last_heartbeat).total_seconds()
                    if elapsed > timeout:
                        stale.append(conn_id)

            for conn_id in stale:
                logger.warning("Closing stale connection %s", conn_id)
                state = self._connections.get(conn_id)
                if state:
                    try:
                        await state.websocket.close(code=4001, reason="Heartbeat timeout")
                    except Exception:
                        logger.debug("Error closing stale connection %s", conn_id, exc_info=True)
                await self.unregister(conn_id)

    async def send_to_agent(
        self,
        agent_id: uuid.UUID,
        message: str,
        *,
        track_pending: bool = False,
    ) -> bool:
        """Send a message to the agent — once, on the first reachable connection.

        Fanning out to every connection previously delivered (and queued) a
        duplicate for each extra connection, causing double task execution.
        Delivery is now single-shot: if that connection drops before the
        agent acks, the un-acked message is redelivered on session resume or
        by the retry worker. Falls through to the next connection when a
        send fails.
        Returns True if at least one connection received the message.
        """
        async with self._lock:
            conn_ids = list(self._agent_connections.get(agent_id, set()))

        sent = False
        for conn_id in conn_ids:
            state = self._connections.get(conn_id)
            if state is None:
                continue
            try:
                if track_pending:
                    from app.services.session_service import store_pending_message
                    await store_pending_message(agent_id, state.session_id, message)
                await state.websocket.send_text(message)
                sent = True
                break
            except Exception:
                logger.debug(
                    "Failed to send to connection %s for agent %s",
                    conn_id, agent_id, exc_info=True,
                )
        return sent

    async def shutdown(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        async with self._lock:
            for conn_id, state in list(self._connections.items()):
                try:
                    await state.websocket.close(code=1001, reason="Server shutdown")
                except Exception:
                    pass
            self._connections.clear()
            self._agent_connections.clear()


_manager: ConnectionManager | None = None


def get_connection_manager(redis: Redis | None = None) -> ConnectionManager:
    global _manager
    if _manager is None:
        if redis is None:
            from app.redis import redis_client
            redis = redis_client
        _manager = ConnectionManager(redis)
    return _manager
