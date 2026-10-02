"""Retry worker: periodically re-deliver unacked messages with backoff."""

import asyncio
import logging

from app.services.routing_service import retry_unacked_messages, expire_ttl_messages
from app.workers.locking import acquire_worker_lock, release_worker_lock

logger = logging.getLogger(__name__)

# Lock TTL must exceed the worst-case cycle runtime (one unbounded SKIP
# LOCKED claim batch plus its send round-trips).
_LOCK_TTL_S = 60.0


async def retry_loop(interval_s: float = 10.0) -> None:
    """Main retry loop: retry unacked + expire TTL messages.

    M3: each cycle is guarded by a SET NX lock so that in a multi-replica
    deployment only one replica runs the retry cycle; SKIP LOCKED then keeps
    concurrent in-flight instances of this loop on disjoint rows as well.
    """
    logger.info("Retry worker started (interval=%ss)", interval_s)
    while True:
        try:
            await asyncio.sleep(interval_s)
            if not await acquire_worker_lock("retry", _LOCK_TTL_S):
                continue
            try:
                retried = await retry_unacked_messages()
                expired = await expire_ttl_messages()
                if retried or expired:
                    logger.debug("Worker cycle: retried=%d expired=%d", retried, expired)
            finally:
                await release_worker_lock("retry")
        except asyncio.CancelledError:
            logger.info("Retry worker cancelled")
            return
        except Exception:
            logger.exception("Retry worker error")
