"""SLA monitoring worker: periodically check SLA compliance."""

import asyncio
import logging

from app.database import SessionLocal
from app.services import sla_service
from app.workers.locking import acquire_worker_lock, release_worker_lock

logger = logging.getLogger(__name__)


async def sla_monitoring_loop(interval_s: float = 60.0) -> None:
    """Background worker that checks SLA compliance every interval_s seconds.

    Default: check every 60 seconds (1 minute).

    M3: each cycle is guarded by a SET NX lock so only one replica runs an
    SLA check cycle.
    """
    logger.info("SLA monitoring worker started (interval=%ss)", interval_s)

    while True:
        try:
            await asyncio.sleep(interval_s)
            if not await acquire_worker_lock("sla_monitoring", max(interval_s * 2, 120)):
                continue
            try:
                async with SessionLocal() as session:
                    violations_detected = await sla_service.check_sla_compliance(session)
                    if violations_detected > 0:
                        logger.warning("SLA monitoring detected %d new violations", violations_detected)
                    else:
                        logger.debug("SLA monitoring check completed, no new violations")
            finally:
                await release_worker_lock("sla_monitoring")

        except asyncio.CancelledError:
            logger.info("SLA monitoring worker cancelled")
            break
        except Exception:
            logger.error("SLA monitoring worker error", exc_info=True)
            # Continue running despite errors
