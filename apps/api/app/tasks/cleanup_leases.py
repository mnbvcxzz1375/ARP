"""Background task to clean up expired route leases."""

import asyncio
import logging

from app.database import SessionLocal
from app.services.lease_service import cleanup_expired_leases

logger = logging.getLogger(__name__)


async def cleanup_expired_leases_task():
    """Periodically clean up expired route leases.

    This task runs every 5 minutes and marks expired leases as revoked.
    """
    while True:
        try:
            async with SessionLocal() as session:
                count = await cleanup_expired_leases(session)
                await session.commit()

                if count > 0:
                    logger.info("Cleaned up %d expired route leases", count)

        except Exception as e:
            logger.error("Error cleaning up expired leases: %s", e, exc_info=True)

        # Run every 5 minutes
        await asyncio.sleep(300)


def start_cleanup_leases_task():
    """Start the cleanup leases background task."""
    asyncio.create_task(cleanup_expired_leases_task())
    logger.info("Started cleanup_expired_leases background task")
