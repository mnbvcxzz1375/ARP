"""Continuity worker: monitors relay health and triggers auto-failover."""

import asyncio
import logging

from app.database import SessionLocal
from app.services.continuity_service import check_and_trigger_auto_failover
from app.workers.locking import acquire_worker_lock, release_worker_lock

logger = logging.getLogger(__name__)


async def continuity_monitoring_loop(interval_s: float = 30.0) -> None:
    """Background worker that monitors relay health and triggers auto-failover.

    Args:
        interval_s: Check interval in seconds (default: 30s)

    M3: each cycle is guarded by a SET NX lock so only one replica runs a
    failover-evaluation cycle.
    """
    logger.info("Starting continuity monitoring worker (interval=%ss)", interval_s)

    while True:
        try:
            if not await acquire_worker_lock("continuity", max(interval_s * 2, 60)):
                await asyncio.sleep(interval_s)
                continue
            try:
                async with SessionLocal() as session:
                    triggered_events = await check_and_trigger_auto_failover(session)

                    if triggered_events:
                        logger.info(
                            "Continuity worker triggered %d auto-failovers",
                            len(triggered_events),
                        )
            finally:
                await release_worker_lock("continuity")

        except asyncio.CancelledError:
            logger.info("Continuity monitoring worker cancelled")
            raise
        except Exception:
            logger.exception("Continuity monitoring worker error")

        await asyncio.sleep(interval_s)
