"""SLA monitoring worker: periodically check SLA compliance."""

import asyncio
import logging

from app.database import SessionLocal
from app.services import sla_service

logger = logging.getLogger(__name__)


async def sla_monitoring_loop(interval_s: float = 60.0) -> None:
    """Background worker that checks SLA compliance every interval_s seconds.

    Default: check every 60 seconds (1 minute).
    """
    logger.info("SLA monitoring worker started (interval=%ss)", interval_s)

    while True:
        try:
            await asyncio.sleep(interval_s)

            async with SessionLocal() as session:
                violations_detected = await sla_service.check_sla_compliance(session)
                if violations_detected > 0:
                    logger.warning("SLA monitoring detected %d new violations", violations_detected)
                else:
                    logger.debug("SLA monitoring check completed, no new violations")

        except asyncio.CancelledError:
            logger.info("SLA monitoring worker cancelled")
            break
        except Exception:
            logger.error("SLA monitoring worker error", exc_info=True)
            # Continue running despite errors
