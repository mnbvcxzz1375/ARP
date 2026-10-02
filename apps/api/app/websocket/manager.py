
"""WebSocket connection manager with presence tracking and connection limits.

M3 (relay dataplane dispatch): the manager is no longer an implicit process
singleton. Each API process is one *node* identified by node_id (settings.
node_id, overridable per instance via get_connection_manager(node_id=...)).
An agent's WebSocket lives on exactly one node:

- presence key ws:presence:{agent_id} now stores the OWNING node_id
  (previously the constant "online") — is_agent_online() semantics are
  unchanged since it only checks existence.
- every instance subscribes to its node channel agentnet:node:{node_id}
  on start_pubsub(); cross-node delivery publishes the message to the
  target node's channel, where the receiving instance hands it to its own
  local connection.
- pub/sub failure is observable: publish() raises, and transports degrade
  to the offline queue with an explicit degraded outcome.
"""

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime

from fastapi import WebSocket
from redis.asyncio import Redis

from app.config import get_settings

logger = logging.getLogger(__name__)

_PRESENCE_KEY_PREFIX = "ws:presence:"
_NODE_CHANNEL_PREFIX = "agentnet:node:"


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

    def __init__(self, redis: Redis, node_id: str | None = None):
        self._redis = redis
        # Which API node this manager instance owns connections for.
        self.node_id = node_id or get_settings().node_id
        self._connections: dict[str, ConnectionState] = {}
        self._agent_connections: dict[uuid.UUID, set[str]] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task | None = None
        self._pubsub_task: asyncio.Task | None = None

    @property
    def settings(self):
        return get_settings()

    def _presence_key(self, agent_id: uuid.UUID) -> str:
        return f"{_PRESENCE_KEY_PREFIX}{agent_id}"

    def _node_channel(self) -> str:
        return f"{_NODE_CHANNEL_PREFIX}{self.node_id}"

    async def _set_redis_presence(self, agent_id: uuid.UUID) -> None:
        key = self._presence_key(agent_id)
        # The presence VALUE is the owning node id, so a peer node can
        # dispatch cross-node messages to the right channel.
        await self._redis.set(
            key, self.node_id, ex=self.settings.ws_heartbeat_timeout_s
        )

    async def get_agent_node(self, agent_id: uuid.UUID) -> str | None:
        """Return the node_id owning the agent's connection, if any."""
        raw = await self._redis.get(self._presence_key(agent_id))
        if raw is None:
            return None
        return raw if isinstance(raw, str) else str(raw)

    async def publish_cross_node(self, node_id: str, payload: str) -> None:
        """Publish a cross-node delivery payload to another node's channel.

        Raises when Redis pub/sub is broken; callers must surface the
        degradation instead of swallowing it.
        """
        await self._redis.publish(f"{_NODE_CHANNEL_PREFIX}{node_id}", payload)

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

    async def start_pubsub(self) -> None:
        """Subscribe to this node's channel for cross-node delivery.

        Safe to call when the Redis backend has no pub/sub capability: the
        subscription failure is logged and the node keeps serving local
        connections (cross-node dispatch will then report degradation).
        """
        if self._pubsub_task is not None:
            return
        self._pubsub_task = asyncio.create_task(self._pubsub_loop())

    async def _pubsub_loop(self) -> None:
        pubsub = None
        try:
            pubsub = self._redis.pubsub()
            await pubsub.subscribe(self._node_channel())
        except Exception:
            logger.warning(
                "Cross-node pubsub subscription unavailable on node %s "
                "(channel %s); cross-node delivery will be reported as degraded",
                self.node_id,
                self._node_channel(),
                exc_info=True,
            )
            if pubsub is not None:
                close = getattr(pubsub, "aclose", None) or getattr(pubsub, "close", None)
                if close is not None:
                    try:
                        await close()
                    except Exception:
                        pass
            return

        logger.info(
            "Node %s subscribed to cross-node channel %s",
            self.node_id,
            self._node_channel(),
        )
        try:
            async for msg in pubsub.listen():
                if not isinstance(msg, dict) or msg.get("type") != "message":
                    continue
                try:
                    await self._handle_cross_node_message(msg.get("data"))
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception(
                        "Error handling cross-node message on node %s",
                        self.node_id,
                    )
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception(
                "Cross-node pubsub loop failed on node %s", self.node_id
            )
        finally:
            close = getattr(pubsub, "aclose", None) or getattr(pubsub, "close", None)
            if close is not None:
                try:
                    await close()
                except Exception:
                    pass

    async def _handle_cross_node_message(self, data) -> None:
        """Deliver a message published by a peer node to a local connection."""
        payload = json.loads(data)
        agent_id = uuid.UUID(str(payload["agent_id"]))
        message = payload["message"]
        track_pending = bool(payload.get("track_pending", False))
        # Local hop only: the peer node already determined this node owns
        # the connection, so never re-publish (loop protection).
        await self.send_to_agent(agent_id, message, track_pending=track_pending)

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

        if self._pubsub_task:
            self._pubsub_task.cancel()
            try:
                await self._pubsub_task
            except (asyncio.CancelledError, Exception):
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
# Named instances for multi-node setups (one ConnectionManager per node_id).
# The default singleton (node_id=None) is NOT in this registry; it keeps its
# own _manager slot so existing reset patterns keep working.
_managers_by_node: dict[str, ConnectionManager] = {}


def get_connection_manager(
    redis: Redis | None = None,
    node_id: str | None = None,
) -> ConnectionManager:
    """Return the manager for a node.

    node_id=None -> the process default singleton (backwards compatible).
    node_id="node_a" -> a dedicated instance for that node, created once
    and cached. Tests pass an InMemoryRedis shared between two nodes to
    exercise real cross-node publish -> subscribe delivery; a single
    instance talking to itself can never demonstrate that.
    """
    global _manager
    if node_id is None:
        if _manager is None:
            if redis is None:
                from app.redis import redis_client
                redis = redis_client
            _manager = ConnectionManager(redis)
        return _manager

    mgr = _managers_by_node.get(node_id)
    if mgr is None:
        if redis is None:
            from app.redis import redis_client
            redis = redis_client
        mgr = ConnectionManager(redis, node_id=node_id)
        _managers_by_node[node_id] = mgr
    return mgr


def reset_connection_managers() -> None:
    """Drop the default singleton and all named instances (tests)."""
    global _manager
    _manager = None
    _managers_by_node.clear()
