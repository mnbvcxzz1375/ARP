"""Retry worker: periodically re-deliver unacked messages with backoff."""

import asyncio
import logging

from app.services.routing_service import retry_unacked_messages, expire_ttl_messages

logger = logging.getLogger(__name__)


async def retry_loop(interval_s: float = 10.0) -> None:
    """Main retry loop: retry unacked + expire TTL messages."""
    logger.info("Retry worker started (interval=%ss)", interval_s)
    while True:
        try:
            await asyncio.sleep(interval_s)
            retried = await retry_unacked_messages()
            expired = await expire_ttl_messages()
            if retried or expired:
                logger.debug("Worker cycle: retried=%d expired=%d", retried, expired)
        except asyncio.CancelledError:
            logger.info("Retry worker cancelled")
            return
        except Exception:
            logger.exception("Retry worker error")
