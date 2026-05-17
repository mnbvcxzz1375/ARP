"""Routing service: resolve, deliver online, queue offline, handle ack, retry."""

import json
import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal
from app.exceptions import DomainException
from app.models.agent import Agent
from app.models.message import Message
from app.models.task import Task
from app.protocol.constants import ErrorCode, DeliveryStatus, MessageType
from app import metrics

logger = logging.getLogger(__name__)

DELIVERY_TIMEOUT_S = 30
RETRY_BACKOFF_BASE_S = 5


async def resolve_agent(session: AsyncSession, agent_number: str) -> Agent:
    """Resolve agent_number to Agent. Raises AGENT_NOT_FOUND."""
    result = await session.execute(
        select(Agent).where(Agent.agent_number == agent_number)
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise DomainException(
            ErrorCode.AGENT_NOT_FOUND,
            f"Agent {agent_number} not found",
            status_code=404,
        )
    return agent


async def deliver_task_request(
    task: Task,
    message: Message,
    assigned_to: Agent,
) -> str:
    """Deliver a task.request message to the target agent.

    Returns the delivery_status: 'delivered' (online) or 'pending' (queued for offline).
    """
    from app.websocket.manager import get_connection_manager

    mgr = get_connection_manager()
    is_online = await mgr.is_agent_online(assigned_to.id)

    ws_payload = {
        "type": MessageType.TASK_REQUEST.value,
        "message_id": message.message_id,
        "task_id": str(task.id),
        "payload": message.content,
        "timestamp": datetime.now(UTC).isoformat(),
    }

    if is_online:
        success = await mgr.send_to_agent(
            assigned_to.id,
            json.dumps(ws_payload),
            track_pending=True,
        )
        if success:
            logger.info("Delivered task %s to online agent %s", task.id, assigned_to.agent_number)
            metrics.MESSAGES_DELIVERED_TOTAL.inc()
            return DeliveryStatus.DELIVERED.value

    # Offline: queue under agent_id. When the agent reconnects,
    # deliver_pending_on_connect() picks up messages from both the
    # agent_id queue (offline) and the session_id queue (resume).
    from app.services.session_service import store_pending_message
    await store_pending_message(
        assigned_to.id,
        str(assigned_to.id),
        json.dumps(ws_payload),
    )
    metrics.PENDING_MESSAGES.inc()
    logger.info("Queued task %s for offline agent %s", task.id, assigned_to.agent_number)
    return DeliveryStatus.PENDING.value


async def deliver_pending_on_connect(
    agent: Agent,
    *,
    session_id: str | None = None,
) -> list[str]:
    """When an agent connects, deliver all pending offline messages.

    Checks both the actual session_id (for session.resume of un-acked messages)
    and the agent_id (for messages queued while the agent was fully offline).
    Deduplicates by message_id to avoid double-delivery.
    """
    from app.services.session_service import get_pending_messages

    seen_ids: set[str] = set()
    pending: list[str] = []

    # 1. Messages queued for this specific session (un-acked from prior connection)
    if session_id:
        for raw in await get_pending_messages(agent.id, session_id):
            try:
                mid = json.loads(raw).get("message_id", "")
            except json.JSONDecodeError:
                mid = ""
            if mid not in seen_ids:
                seen_ids.add(mid)
                pending.append(raw)

    # 2. Messages queued while agent was fully offline (stored with agent_id)
    agent_key = str(agent.id)
    if agent_key != session_id:
        for raw in await get_pending_messages(agent.id, agent_key):
            try:
                mid = json.loads(raw).get("message_id", "")
            except json.JSONDecodeError:
                mid = ""
            if mid not in seen_ids:
                seen_ids.add(mid)
                pending.append(raw)
    if not pending:
        return []

    from app.websocket.manager import get_connection_manager
    mgr = get_connection_manager()

    delivered: list[str] = []
    for raw in pending:
        success = await mgr.send_to_agent(agent.id, raw)
        if success:
            try:
                msg_data = json.loads(raw)
                delivered.append(msg_data.get("message_id", ""))
            except json.JSONDecodeError:
                pass

    logger.info("Delivered %d pending messages to agent %s", len(delivered), agent.agent_number)
    return delivered


async def ack_message(message_id: str) -> None:
    """Mark a message as acked. Idempotent ? re-acking is a no-op."""
    async with SessionLocal() as session:
        result = await session.execute(
            select(Message).where(Message.message_id == message_id)
        )
        msg = result.scalar_one_or_none()
        if msg is None:
            logger.debug("Ack for unknown message %s, ignoring", message_id)
            return

        if msg.delivery_status == DeliveryStatus.ACKED.value:
            logger.debug("Message %s already acked, ignoring duplicate ack", message_id)
            return

        # Capture task_id before clearing fields for Redis cleanup
        task_id = msg.task_id

        msg.delivery_status = DeliveryStatus.ACKED.value
        msg.next_retry_at = None
        await session.commit()
        metrics.MESSAGES_ACKED_TOTAL.inc()
        logger.info("Message %s acked", message_id)

        # Clean up Redis pending queue for this agent
        try:
            from app.services.session_service import ack_message_for_agent
            task_result = await session.execute(
                select(Task).where(Task.id == task_id)
            )
            task = task_result.scalar_one_or_none()
            if task and task.assigned_to:
                await ack_message_for_agent(task.assigned_to, message_id)
        except Exception:
            logger.debug("Redis ack cleanup failed for %s, ignoring", message_id)


async def retry_unacked_messages() -> int:
    """Retry worker: find delivered-but-unacked messages past their retry window,
    re-deliver them, and apply backoff.

    Returns number of messages retried.
    """
    now = datetime.now(UTC)

    async with SessionLocal() as session:
        result = await session.execute(
            select(Message).where(
                Message.delivery_status == DeliveryStatus.DELIVERED.value,
                Message.next_retry_at <= now,
                Message.retry_count < Message.max_retries,
            ).limit(50)
        )
        messages = result.scalars().all()

        if not messages:
            return 0

        from app.websocket.manager import get_connection_manager
        mgr = get_connection_manager()

        retried = 0
        for msg in messages:
            # Get the task to find assigned_to
            task_result = await session.execute(
                select(Task).where(Task.id == msg.task_id)
            )
            task = task_result.scalar_one_or_none()
            if task is None or task.assigned_to is None:
                msg.delivery_status = DeliveryStatus.FAILED.value
                continue

            agent_id = task.assigned_to
            is_online = await mgr.is_agent_online(agent_id)

            if not is_online:
                # Still offline, update next_retry_at but don't count as retry
                msg.next_retry_at = now + timedelta(seconds=RETRY_BACKOFF_BASE_S * (2 ** msg.retry_count))
                continue

            ws_payload = {
                "type": msg.type,
                "message_id": msg.message_id,
                "task_id": str(task.id),
                "payload": msg.content,
                "timestamp": now.isoformat(),
            }

            success = await mgr.send_to_agent(agent_id, json.dumps(ws_payload))
            if success:
                backoff = RETRY_BACKOFF_BASE_S * (2 ** msg.retry_count)
                msg.retry_count += 1
                msg.next_retry_at = now + timedelta(seconds=backoff)
                msg.delivery_status = DeliveryStatus.DELIVERED.value
                metrics.MESSAGES_RETRIED_TOTAL.inc()
                retried += 1
            else:
                msg.next_retry_at = now + timedelta(seconds=RETRY_BACKOFF_BASE_S)

            if msg.retry_count >= msg.max_retries:
                msg.delivery_status = DeliveryStatus.FAILED.value
                logger.warning("Message %s exceeded max retries", msg.message_id)

        await session.commit()

        if retried:
            logger.info("Retried %d messages", retried)
        return retried


async def expire_ttl_messages() -> int:
    """Expire messages that have exceeded their TTL."""
    now = datetime.now(UTC)

    async with SessionLocal() as session:
        from sqlalchemy import and_, or_
        
        # Find messages with TTL that have exceeded their time
        stmt = (
            select(Message)
            .where(
                Message.ttl_seconds.isnot(None),
                Message.delivery_status.in_([
                    DeliveryStatus.PENDING.value,
                    DeliveryStatus.DELIVERED.value,
                ]),
            )
            .limit(500)
        )
        result = await session.execute(stmt)
        candidates = result.scalars().all()
        
        expired = 0
        for msg in candidates:
            if msg.ttl_seconds is not None:
                expire_at = msg.created_at + timedelta(seconds=msg.ttl_seconds)
                if expire_at < now:
                    msg.delivery_status = DeliveryStatus.EXPIRED.value
                    msg.next_retry_at = None
                    metrics.MESSAGES_EXPIRED_TOTAL.inc()
                    expired += 1
        
        if expired:
            await session.commit()
            logger.info("Expired %d TTL-exceeded messages", expired)
        return expired
