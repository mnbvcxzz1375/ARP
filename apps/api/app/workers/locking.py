"""Worker leadership locks (SET NX).

M3: with the cleanup workers there are seven periodic workers
per API process. In a multi-replica deployment each cycle of every worker
should run on exactly one replica — e.g. two retry_unacked_messages
instances must not re-send the same delivered-unacked message.

The lock is per CYCLE, not per process: a replica acquires
worker_lock:{name} with SET NX (auto-expiring via EX, so a crashed holder
never blocks a worker forever), runs the cycle, and releases. A holder
that loses the lock mid-cycle is detected on the next acquire. This is
not a global scheduler — it is the same single-winner semantics the
SKIP LOCKED claims rely on, at the loop level.
"""

import logging

logger = logging.getLogger(__name__)

_LOCK_KEY_PREFIX = "worker_lock:"


async def acquire_worker_lock(name: str, ttl_s: float) -> bool:
    """Try to take the per-cycle lock for a worker. True when acquired.

    Falls closed: if Redis is unreachable the lock is reported as NOT
    acquired (no worker may run leader-only cycles against a split brain),
    which the loops treat as "skip this cycle".
    """
    from app.redis import redis_client

    try:
        result = await redis_client.set(
            _LOCK_KEY_PREFIX + name, "1", ex=int(max(ttl_s, 1)), nx=True
        )
    except Exception:
        logger.debug(
            "Worker lock %s could not be acquired (Redis unavailable)", name
        )
        return False
    return bool(result)


async def release_worker_lock(name: str) -> None:
    """Release a per-cycle lock held by this process (best-effort)."""
    from app.redis import redis_client

    try:
        await redis_client.delete(_LOCK_KEY_PREFIX + name)
    except Exception:
        logger.debug("Worker lock %s release failed", name)
