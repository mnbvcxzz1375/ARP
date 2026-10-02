"""Offline delivery worker: drains the offline queue for reachable agents.

M3 (was a one-line stub). Boundary with retry_worker, by construction the
two scans are over MUTUALLY EXCLUSIVE row sets, so there is no
cross-worker concurrency to guard:

- THIS worker scans delivery_status IN ('queued', 'delivering'):
  'queued' = never handed to a live connection (agent was offline),
  'delivering' = a claim this worker took and may have lost to a crash.
  In both cases the message is NOT in the delivered-unacked set.
- retry_worker scans delivery_status = 'delivered' (delivered-unacked).

SKIP LOCKED therefore only matters for concurrent instances of THIS SAME
worker statement (multiple replicas / two event-loop instances), which is
exactly what its acceptance test exercises.

Claim protocol (lock held only for the claim, never across the send
round-trip):

    claim:  parameterized SELECT ... FOR UPDATE SKIP LOCKED
            + parameterized UPDATE to 'delivering' with a claim window
    COMMIT  <- row locks released here
    send:   transport round-trip (no row locks held)
    finish: parameterized UPDATE with the final status

A crashed claim leaves the row in 'delivering' with next_retry_at in the
future; once CLAIM_WINDOW_S passes, this worker re-claims it (the
'delivering' rescue clause), so nothing is stuck forever.

All SQL is parameterized text(): every value (:now, :deadline, row ids,
status literals) is a bound parameter, never interpolated into SQL text.
"""

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from app.database import SessionLocal
from app.models.message import Message
from app.models.message_delivery_event import MessageDeliveryEvent
from app.models.task import Task
from app.protocol.constants import DeliveryStatus
from app.services.routing_service import RETRY_BACKOFF_BASE_S

logger = logging.getLogger(__name__)

BATCH_LIMIT = 50
# How long a claim hides a row from other instances of this worker. Must
# comfortably exceed a send round-trip.
CLAIM_WINDOW_S = 30

_CLAIM_SELECT_SQL = text(
    """
    SELECT id FROM messages
    WHERE task_id IN (
            SELECT id FROM tasks WHERE assigned_to = ANY (:online_agent_ids)
          )
      AND (
            (
              delivery_status = :queued_status
              AND (next_retry_at IS NULL OR next_retry_at <= :now)
            )
          OR
            (
              delivery_status = :delivering_status
              AND next_retry_at <= :claim_deadline
            )
          )
    ORDER BY next_retry_at ASC NULLS LAST
    LIMIT :batch_limit
    FOR UPDATE SKIP LOCKED
    """
)

_CLAIM_UPDATE_SQL = text(
    """
    UPDATE messages
    SET delivery_status = :delivering_status,
        next_retry_at = :claim_until
    WHERE id = :row_id
    """
)


async def _online_agent_ids() -> list[uuid.UUID]:
    """Agent ids with a live presence entry (connected on SOME node).

    The offline worker exists to hand queued messages to REACHABLE agents;
    restricting the claim to their messages keeps a large backlog of
    offline-agent messages from crowding out every cycle.
    """
    from app.redis import redis_client

    try:
        keys = await redis_client.keys("ws:presence:*")
    except Exception:
        return []
    ids = []
    for key in keys or []:
        raw = str(key)
        suffix = raw[len("ws:presence:") :]
        try:
            ids.append(uuid.UUID(suffix))
        except ValueError:
            continue
    return ids


async def deliver_offline_queued_messages() -> int:
    """Deliver queued messages to agents that are currently reachable.

    Returns the number of messages delivered. Messages whose Redis pending
    entry is still intact are skipped: connect-time delivery owns them.
    """
    from app.transports import select_transport

    now = datetime.now(UTC)
    claim_deadline = now - timedelta(seconds=CLAIM_WINDOW_S)
    claim_until = now + timedelta(seconds=CLAIM_WINDOW_S)

    online_agents = await _online_agent_ids()
    if not online_agents:
        return 0

    async with SessionLocal() as session:
        claim_result = await session.execute(
            _CLAIM_SELECT_SQL,
            {
                "online_agent_ids": online_agents,
                "queued_status": DeliveryStatus.QUEUED.value,
                "delivering_status": DeliveryStatus.DELIVERING.value,
                "now": now,
                "claim_deadline": claim_deadline,
                "batch_limit": BATCH_LIMIT,
            },
        )
        claimed_ids = [uuid.UUID(str(row.id)) for row in claim_result]

        for row_id in claimed_ids:
            await session.execute(
                _CLAIM_UPDATE_SQL,
                {
                    "delivering_status": DeliveryStatus.DELIVERING.value,
                    "claim_until": claim_until,
                    "row_id": row_id,
                },
            )
        await session.commit()
        # Row locks are released at this commit — the send round-trip
        # below never holds them.

    if not claimed_ids:
        return 0

    transport = select_transport(None)  # final hop: central transport
    delivered = 0

    for mid in claimed_ids:
        async with SessionLocal() as session:
            msg = await session.get(Message, mid)
            if msg is None:
                continue

            task = await session.get(Task, msg.task_id)

            # Skip messages connect-time delivery still owns (queue intact).
            agent_id = task.assigned_to if task else None
            if agent_id is not None:
                from app.services.session_service import message_in_pending_queue

                if await message_in_pending_queue(agent_id, msg.message_id):
                    await session.execute(
                        text(
                            "UPDATE messages SET delivery_status = :status, "
                            "next_retry_at = :next WHERE id = :row_id"
                        ),
                        {
                            "status": DeliveryStatus.QUEUED.value,
                            "next": now
                            + timedelta(
                                seconds=RETRY_BACKOFF_BASE_S * (2 ** msg.retry_count)
                            ),
                            "row_id": mid,
                        },
                    )
                    await session.commit()
                    continue

            if task is None or agent_id is None:
                await session.execute(
                    text(
                        "UPDATE messages SET delivery_status = :status, "
                        "next_retry_at = NULL WHERE id = :row_id"
                    ),
                    {"status": DeliveryStatus.DELIVERY_FAILED.value, "row_id": mid},
                )
                session.add(
                    MessageDeliveryEvent(
                        message_id=msg.message_id,
                        task_id=msg.task_id,
                        event_type="delivery_failed",
                        error_code="TASK_OR_AGENT_NOT_FOUND",
                        error_message="Task or assigned agent not found during "
                        "offline delivery",
                    )
                )
                await session.commit()
                continue

            ws_payload = {
                "type": msg.type,
                "message_id": msg.message_id,
                "task_id": str(task.id),
                "payload": msg.content,
                "timestamp": datetime.now(UTC).isoformat(),
            }

            send_result = await transport.deliver(
                agent_id=agent_id,
                message=json.dumps(ws_payload),
                message_id=msg.message_id,
                task_id=task.id,
                source_agent_id=task.created_by,
                track_pending=True,
            )

            if send_result.is_sent:
                await session.execute(
                    text(
                        "UPDATE messages SET delivery_status = :status, "
                        "next_retry_at = :next WHERE id = :row_id"
                    ),
                    {
                        "status": DeliveryStatus.DELIVERED.value,
                        # Arm the retry worker: a delivered-unacked message
                        # that is never acked must be picked up again by
                        # retry_unacked_messages.
                        "next": datetime.now(UTC)
                        + timedelta(seconds=RETRY_BACKOFF_BASE_S),
                        "row_id": mid,
                    },
                )
                delivered += 1
                session.add(
                    MessageDeliveryEvent(
                        message_id=msg.message_id,
                        task_id=task.id,
                        event_type="delivered",
                        extra_metadata={
                            "outcome": send_result.outcome,
                            "node_id": send_result.node_id,
                            "source": "offline_worker",
                        },
                    )
                )
            else:
                # Agent still unreachable (or degraded): back to the queue
                # with backoff. Do not consume a retry attempt for this —
                # the transport never failed.
                await session.execute(
                    text(
                        "UPDATE messages SET delivery_status = :status, "
                        "next_retry_at = :next WHERE id = :row_id"
                    ),
                    {
                        "status": DeliveryStatus.QUEUED.value,
                        "next": datetime.now(UTC)
                        + timedelta(
                            seconds=RETRY_BACKOFF_BASE_S * (2 ** msg.retry_count)
                        ),
                        "row_id": mid,
                    },
                )
            await session.commit()

    if delivered:
        logger.info("Offline delivery worker delivered %d messages", delivered)
    return delivered


async def offline_delivery_loop(interval_s: float = 10.0) -> None:
    """Main loop: drain the offline queue for reachable agents.

    M3: each cycle is guarded by a SET NX lock; combined with the SKIP
    LOCKED claim, both multiple replicas and two in-flight instances of
    this loop stay on disjoint rows.
    """
    from app.workers.locking import acquire_worker_lock, release_worker_lock

    logger.info("Offline delivery worker started (interval=%ss)", interval_s)
    while True:
        try:
            await asyncio.sleep(interval_s)
            if not await acquire_worker_lock("offline_delivery", max(interval_s * 2, 60)):
                continue
            try:
                delivered = await deliver_offline_queued_messages()
                if delivered:
                    logger.debug("Worker cycle: offline_delivered=%d", delivered)
            finally:
                await release_worker_lock("offline_delivery")
        except asyncio.CancelledError:
            logger.info("Offline delivery worker cancelled")
            return
        except Exception:
            logger.exception("Offline delivery worker error")
