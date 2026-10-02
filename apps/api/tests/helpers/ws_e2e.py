from __future__ import annotations

import asyncio
import json
import socket
from contextlib import asynccontextmanager
from dataclasses import dataclass
from fnmatch import fnmatch
from typing import Any, AsyncIterator

import uvicorn


class InMemoryPubSub:
    """Minimal pubsub stub backing InMemoryRedis.publish/subscribe.

    M3: cross-node delivery in tests is exercised for real — node A's
    ConnectionManager publishes to `agentnet:node:{node_b}` and node B's
    instance, which subscribed on start_pubsub(), receives the payload on
    its own queue and hands it to its local connection.
    """

    def __init__(self, redis: "InMemoryRedis") -> None:
        self._redis = redis
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._channels: set[str] = set()
        self._closed = False

    async def subscribe(self, *channels: str) -> None:
        for channel in channels:
            self._channels.add(channel)
            self._redis._subscribers.setdefault(channel, []).append(self._queue)

    async def unsubscribe(self, *channels: str) -> None:
        for channel in channels:
            self._channels.discard(channel)
            queues = self._redis._subscribers.get(channel, [])
            if self._queue in queues:
                queues.remove(self._queue)

    async def aclose(self) -> None:
        await self.unsubscribe(*list(self._channels))
        self._closed = True

    async def close(self) -> None:
        await self.aclose()

    async def get_message(
        self, ignore_subscribe_messages: bool = True, timeout: float = 1.0
    ) -> dict[str, Any] | None:
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    async def listen(self):
        while not self._closed:
            msg = await self.get_message(timeout=1.0)
            if msg is not None:
                yield msg


class InMemoryRedis:
    """Small async Redis subset for WebSocket E2E tests.

    M3 additions:
    - set(nx=True) for worker leadership locks,
    - publish/subscribe for cross-node delivery,
    - pubsub_failing: fault injection for the Redis-down degradation path
      (an AsyncMock's publish never raises, so the degraded outcome can
      only be tested with a controllable fake).
    """

    def __init__(self) -> None:
        self.values: dict[str, Any] = {}
        self.lists: dict[str, list[str]] = {}
        self.eval_calls: list[tuple[Any, ...]] = []
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        self.pubsub_failing = False

    def pubsub(self) -> InMemoryPubSub:
        return InMemoryPubSub(self)

    async def publish(self, channel: str, message: str) -> int:
        if self.pubsub_failing:
            raise RuntimeError("publish failed: pubsub disabled (fault injection)")
        count = 0
        for queue in list(self._subscribers.get(channel, [])):
            await queue.put(
                {"type": "message", "channel": channel, "data": message}
            )
            count += 1
        return count

    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        return None

    async def set(
        self,
        key: str,
        value: Any,
        ex: int | None = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool | None:
        if nx and key in self.values:
            return None
        if xx and key not in self.values:
            return None
        self.values[key] = value
        return True

    async def get(self, key: str) -> Any:
        return self.values.get(key)

    async def expire(self, key: str, seconds: int) -> None:
        return None

    async def delete(self, key: str) -> None:
        self.values.pop(key, None)
        self.lists.pop(key, None)

    async def exists(self, key: str) -> int:
        return int(key in self.values or key in self.lists)

    async def keys(self, pattern: str) -> list[str]:
        candidates = set(self.values) | set(self.lists)
        return [key for key in candidates if fnmatch(key, pattern)]

    async def lpush(self, key: str, value: str) -> int:
        self.lists.setdefault(key, []).insert(0, value)
        return len(self.lists[key])

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        values = self.lists.get(key, [])
        if end == -1:
            return values[start:]
        return values[start : end + 1]

    async def eval(self, script: str, numkeys: int, *args: Any) -> int:
        self.eval_calls.append((script, numkeys, *args))
        if numkeys == 1 and len(args) == 2:
            key, target_mid = str(args[0]), str(args[1])
            kept: list[str] = []
            for raw in self.lists.get(key, []):
                try:
                    if json.loads(raw).get("message_id") == target_mid:
                        continue
                except json.JSONDecodeError:
                    pass
                kept.append(raw)
            if kept:
                self.lists[key] = kept
            else:
                self.lists.pop(key, None)
        return 0

    async def zremrangebyscore(self, key: str, start: Any, end: Any) -> None:
        return None

    async def zcard(self, key: str) -> int:
        return 0

    async def zadd(self, key: str, mapping: dict[str, float]) -> None:
        return None


@dataclass
class LiveServer:
    base_url: str
    ws_url: str
    redis: InMemoryRedis


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@asynccontextmanager
async def run_live_server(monkeypatch) -> AsyncIterator[LiveServer]:
    redis = InMemoryRedis()

    import app.redis as redis_module
    import app.services.rate_limit_service as rate_limit_service
    import app.services.session_service as session_service
    import app.websocket.manager as manager_module
    from app.main import app

    monkeypatch.setattr(redis_module, "redis_client", redis)
    monkeypatch.setattr(rate_limit_service, "redis_client", redis)
    # M3: session_service binds `redis_client` at module import
    # (from app.redis import redis_client), so patching app.redis alone
    # leaves the module-level binding pointed at the real client (or the
    # autouse mock). Patch the binding in session_service too.
    monkeypatch.setattr(session_service, "redis_client", redis)
    manager_module._manager = None
    manager_module._managers_by_node.clear()

    port = _free_port()
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        lifespan="on",
    )
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())

    try:
        for _ in range(100):
            if server.started:
                break
            await asyncio.sleep(0.05)
        if not server.started:
            raise RuntimeError("uvicorn test server did not start")

        yield LiveServer(
            base_url=f"http://127.0.0.1:{port}",
            ws_url=f"ws://127.0.0.1:{port}/v1/ws",
            redis=redis,
        )
    finally:
        server.should_exit = True
        await task
        manager_module._manager = None
        manager_module._managers_by_node.clear()
