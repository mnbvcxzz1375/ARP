"""Periodic cleanup workers: expired route leases and stale edge relays.

M1 testability: each worker exposes a single-cycle function
(lease_cleanup_cycle / stale_relay_cleanup_cycle) that takes an injected
AsyncSession, plus a loop wrapper (lease_cleanup_loop /
stale_relay_cleanup_loop) following retry_worker.py's pattern — per-cycle
SET NX lock via app.workers.locking (acquire/release), CancelledError
exits gracefully, and a single cycle's exception is isolated so one bad
round never kills the worker.

M2 transaction-signature split (explicit, known divergence): the cleanup
service functions (lease_service.cleanup_expired_leases,
edge_discovery.cleanup_stale_edge_relays) accept an injected session and
only FLUSH — they never commit, so the COMMIT lives in the single-cycle
functions below. This differs from the other workers (retry / timeout /
sla / continuity / offline), whose services manage their own transactions
end to end (e.g. routing_service.py's claim-then-commit in
claim_message_for_retry). Both shapes coexist on purpose; do not push a
commit into the service functions without removing it here.
"""

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal
from app.services.edge_discovery import cleanup_stale_edge_relays
from app.services.lease_service import cleanup_expired_leases
from app.workers.locking import acquire_worker_lock, release_worker_lock

logger = logging.getLogger(__name__)

# Lock TTLs must exceed the worst-case cycle runtime: the lease cycle is
# capped at 10 batches × 500 row updates, the stale-relay cycle at a
# single unbounded-ish UPDATE set.
_LEASE_LOCK_TTL_S = 120.0
_STALE_RELAY_LOCK_TTL_S = 60.0


async def lease_cleanup_cycle(session: AsyncSession) -> int:
    """One lease-cleanup cycle: mark expired leases revoked, then commit."""
    count = await cleanup_expired_leases(session)
    await session.commit()
    if count > 0:
        logger.info("Cleaned up %d expired route leases", count)
    return count


async def stale_relay_cleanup_cycle(session: AsyncSession) -> int:
    """One stale-relay cycle: mark stale edge relays down, then commit."""
    count = await cleanup_stale_edge_relays(session)
    await session.commit()
    if count > 0:
        logger.info("Marked %d stale edge relays as down", count)
    return count


async def lease_cleanup_loop(interval_s: float = 300.0) -> None:
    """Periodically revoke expired route leases.

    M3: each cycle is guarded by a SET NX lock so that in a multi-replica
    deployment only one replica runs the cleanup cycle.
    """
    logger.info("Lease cleanup worker started (interval=%ss)", interval_s)
    while True:
        try:
            await asyncio.sleep(interval_s)
            if not await acquire_worker_lock("lease_cleanup", _LEASE_LOCK_TTL_S):
                continue
            try:
                async with SessionLocal() as session:
                    await lease_cleanup_cycle(session)
            finally:
                await release_worker_lock("lease_cleanup")
        except asyncio.CancelledError:
            logger.info("Lease cleanup worker cancelled")
            return
        except Exception:
            logger.exception("Lease cleanup worker error")


async def stale_relay_cleanup_loop(interval_s: float = 60.0) -> None:
    """Periodically mark edge relays with stale heartbeats as down.

    M3: each cycle is guarded by a SET NX lock so that in a multi-replica
    deployment only one replica runs the cleanup cycle.
    """
    logger.info("Stale relay cleanup worker started (interval=%ss)", interval_s)
    while True:
        try:
            await asyncio.sleep(interval_s)
            if not await acquire_worker_lock(
                "stale_relay_cleanup", _STALE_RELAY_LOCK_TTL_S
            ):
                continue
            try:
                async with SessionLocal() as session:
                    await stale_relay_cleanup_cycle(session)
            finally:
                await release_worker_lock("stale_relay_cleanup")
        except asyncio.CancelledError:
            logger.info("Stale relay cleanup worker cancelled")
            return
        except Exception:
            logger.exception("Stale relay cleanup worker error")
