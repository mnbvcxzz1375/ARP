"""Timeout worker: periodically expire stale tasks and release expired leases.

Phase 10: Hardening.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.database import SessionLocal
from app.models.task import Task
from app.protocol.constants import TaskStatus, ErrorCode

logger = logging.getLogger(__name__)

# Non-terminal statuses that can be timed out
_TIMEOUTABLE_STATUSES = {
    TaskStatus.CREATED.value,
    TaskStatus.QUEUED.value,
    TaskStatus.DELIVERED.value,
    TaskStatus.ACCEPTED.value,
    TaskStatus.RUNNING.value,
    TaskStatus.AWAITING_APPROVAL.value,
}


async def expire_stale_tasks() -> int:
    """Find tasks whose lease has expired and mark them EXPIRED.

    Returns the number of tasks expired.
    """
    now = datetime.now(UTC)

    async with SessionLocal() as session:
        result = await session.execute(
            select(Task).where(
                Task.status.in_(_TIMEOUTABLE_STATUSES),
                Task.lease_expires_at.isnot(None),
                Task.lease_expires_at <= now,
            ).limit(500)
        )
        tasks = result.scalars().all()

        if not tasks:
            return 0

        for task in tasks:
            old_status = task.status
            expired_at = task.lease_expires_at
            task.status = TaskStatus.EXPIRED.value
            task.lease_expires_at = None
            task.lease_agent_id = None
            task.error_message = (
                task.error_message or "Task lease expired"
            )
            logger.info(
                "Task %s expired: %s -> expired (lease expired at %s)",
                task.id, old_status, expired_at,
            )

        await session.commit()

        if tasks:
            logger.info("Expired %d stale tasks", len(tasks))
        return len(tasks)


async def expire_long_running_tasks(max_runtime_s: int) -> int:
    """Find tasks that have been running too long (exceeded max task timeout)
    and mark them EXPIRED. Uses created_at to measure total task lifetime.

    Returns the number of tasks expired.
    """
    now = datetime.now(UTC)

    async with SessionLocal() as session:
        from sqlalchemy import text
        result = await session.execute(
            text(
                """
                UPDATE tasks
                SET status = :expired,
                    error_message = COALESCE(error_message, 'Task exceeded maximum runtime'),
                    lease_expires_at = NULL,
                    lease_agent_id = NULL
                WHERE id IN (
                    SELECT id FROM tasks
                    WHERE status IN ('running', 'accepted', 'delivered', 'awaiting_approval')
                      AND created_at < :cutoff
                    LIMIT 500
                )
                RETURNING id
                """
            ),
            {
                "expired": TaskStatus.EXPIRED.value,
                "cutoff": datetime.now(UTC) - timedelta(seconds=max_runtime_s),
            },
        )
        expired_ids = result.fetchall()
        await session.commit()

        count = len(expired_ids)
        if count:
            logger.info("Expired %d long-running tasks (max_runtime=%ds)", count, max_runtime_s)
        return count


async def expire_stale_approvals() -> int:
    """Delegate to approval_service.expire_stale_approvals."""
    from app.services.approval_service import expire_stale_approvals as _expire
    return await _expire()


async def timeout_loop(
    interval_s: float = 30.0,
    max_task_runtime_s: int = 600,
) -> None:
    """Main timeout worker loop.

    Runs periodically to:
    1. Expire stale tasks with expired leases
    2. Expire long-running tasks exceeding max runtime
    3. Expire stale approval requests
    """
    logger.info(
        "Timeout worker started (interval=%ss, max_runtime=%ds)",
        interval_s, max_task_runtime_s,
    )
    while True:
        try:
            await asyncio.sleep(interval_s)
            lease_expired = await expire_stale_tasks()
            long_running = await expire_long_running_tasks(max_task_runtime_s)
            approvals = await expire_stale_approvals()
            if lease_expired or long_running or approvals:
                logger.debug(
                    "Timeout cycle: lease=%d runtime=%d approvals=%d",
                    lease_expired, long_running, approvals,
                )
        except asyncio.CancelledError:
            logger.info("Timeout worker cancelled")
            return
        except Exception:
            logger.exception("Timeout worker error")
