
"""Session resume service for recovering un-acked messages.

Uses Redis lists to track pending deliveries per session.
Full delivery queue arrives in Phase 4.
"""

import json
import logging
import uuid

from redis.asyncio import Redis

from app.redis import redis_client

logger = logging.getLogger(__name__)

_SESSION_PENDING_KEY = "ws:session_pending:{agent_id}:{session_id}"


def _session_key(agent_id: uuid.UUID, session_id: str) -> str:
    return _SESSION_PENDING_KEY.format(agent_id=agent_id, session_id=session_id)


async def store_pending_message(
    agent_id: uuid.UUID,
    session_id: str,
    message: str,
    redis: Redis | None = None,
) -> None:
    r = redis or redis_client
    key = _session_key(agent_id, session_id)
    await r.lpush(key, message)
    await r.expire(key, 86400)


async def get_pending_messages(
    agent_id: uuid.UUID,
    session_id: str,
    after_message_id: str | None = None,
    redis: Redis | None = None,
) -> list[str]:
    """Retrieve pending messages for a session.

    Does NOT delete the queue; messages are removed only via explicit ack_message
    to prevent data loss if the WS drops mid-delivery.
    """
    r = redis or redis_client
    key = _session_key(agent_id, session_id)

    messages_raw = await r.lrange(key, 0, -1)
    if not messages_raw:
        return []

    messages_raw.reverse()

    result: list[str] = []
    found_after = after_message_id is None

    for raw in messages_raw:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue
        mid = msg.get("message_id", "")

        if after_message_id and mid == after_message_id:
            found_after = True
            continue

        if found_after:
            result.append(raw)

    return result


async def ack_message(
    agent_id: uuid.UUID,
    session_id: str,
    message_id: str,
    redis: Redis | None = None,
) -> None:
    """Atomically remove an acked message from the pending queue.

    Uses a Redis Lua script for atomic read-filter-rewrite to avoid
    the race condition where a crash between delete and re-push loses all messages.
    """
    r = redis or redis_client
    key = _session_key(agent_id, session_id)
    await _remove_message_from_key(r, key, message_id)


async def _remove_message_from_key(r: Redis, key: str, message_id: str) -> None:
    lua_remove = """
    local key = KEYS[1]
    local target_mid = ARGV[1]
    local items = redis.call('LRANGE', key, 0, -1)
    redis.call('DEL', key)
    for i = #items, 1, -1 do
        local ok, msg = pcall(cjson.decode, items[i])
        if ok and msg['message_id'] ~= target_mid then
            redis.call('LPUSH', key, items[i])
        end
    end
    return 1
    """
    await r.eval(lua_remove, 1, key, message_id)


async def ack_message_for_agent(
    agent_id: uuid.UUID,
    message_id: str,
    redis: Redis | None = None,
) -> None:
    """Remove an acked message from all pending queues for an agent."""
    r = redis or redis_client
    pattern = _SESSION_PENDING_KEY.format(agent_id=agent_id, session_id="*")
    keys = await r.keys(pattern)
    for key in keys:
        await _remove_message_from_key(r, key, message_id)


async def clear_session(
    agent_id: uuid.UUID,
    session_id: str,
    redis: Redis | None = None,
) -> None:
    r = redis or redis_client
    await r.delete(_session_key(agent_id, session_id))


async def has_pending_messages(
    agent_id: uuid.UUID,
    session_id: str,
    redis: Redis | None = None,
) -> bool:
    r = redis or redis_client
    key = _session_key(agent_id, session_id)
    return bool(await r.exists(key))
