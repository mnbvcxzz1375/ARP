"""Routing service: resolve, deliver online, queue offline, handle ack, retry."""

import json
import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal
from app.exceptions import DomainException
from app.metrics import ROUTE_DECISIONS_TOTAL, ROUTE_FALLBACK_TOTAL
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
    route_decision: "RouteDecision | None" = None,
) -> str:
    """Deliver a task.request message to the target agent.

    Args:
        task: The task to deliver
        message: The message to deliver
        assigned_to: The target agent
        route_decision: Optional route decision from path optimizer (Phase 13+)

    Returns:
        The delivery_status: 'delivered' (online) or 'pending' (queued for offline).

    Phase 13: When route_decision is provided, delivery follows the selected route.
    For central_relay routes, the message is delivered through the relay infrastructure.
    Phase 13: Verifies and consumes route lease if present.
    """
    from app.websocket.manager import get_connection_manager
    from app.models.message_delivery_event import MessageDeliveryEvent
    from app.services.lease_service import verify_route_lease, consume_route_lease

    mgr = get_connection_manager()
    is_online = await mgr.is_agent_online(assigned_to.id)

    ws_payload = {
        "type": MessageType.TASK_REQUEST.value,
        "message_id": message.message_id,
        "task_id": str(task.id),
        "payload": message.content,
        "timestamp": datetime.now(UTC).isoformat(),
    }

    # Estimate message size for lease consumption
    message_size_bytes = len(json.dumps(ws_payload).encode("utf-8"))

    # Phase 13: Verify route lease if route decision exists
    lease = None
    if route_decision and route_decision.lease_id:
        async with SessionLocal() as session:
            lease = await verify_route_lease(
                session,
                source_agent_id=task.created_by,
                target_agent_id=assigned_to.id,
                route_type=route_decision.selected_route_type,
                task=task,
                message_size_bytes=message_size_bytes,
                lease_id=route_decision.lease_id,
            )
            if not lease:
                logger.warning(
                    "Route lease %s invalid or exhausted for task %s",
                    route_decision.lease_id,
                    task.id,
                )

    # Phase 13: Log route decision and create route_selected event
    if route_decision:
        logger.info(
            "Delivering task %s via route_type=%s relay=%s lease=%s (enforced mode)",
            task.id,
            route_decision.selected_route_type,
            route_decision.selected_relay_node_id,
            route_decision.lease_id,
        )
        # Record route selection event
        async with SessionLocal() as session:
            event = MessageDeliveryEvent(
                message_id=message.message_id,
                task_id=task.id,
                event_type="route_selected",
                route_type=route_decision.selected_route_type,
                relay_node_id=route_decision.selected_relay_node_id,
            )
            session.add(event)
            await session.commit()

    delivery_start = datetime.now(UTC)

    if is_online:
        # Record delivering event
        async with SessionLocal() as session:
            event = MessageDeliveryEvent(
                message_id=message.message_id,
                task_id=task.id,
                event_type="delivering",
                route_type=route_decision.selected_route_type if route_decision else None,
                relay_node_id=route_decision.selected_relay_node_id if route_decision else None,
            )
            session.add(event)
            await session.commit()

        success = await mgr.send_to_agent(
            assigned_to.id,
            json.dumps(ws_payload),
            track_pending=True,
        )
        if success:
            latency_ms = int((datetime.now(UTC) - delivery_start).total_seconds() * 1000)
            logger.info("Delivered task %s to online agent %s", task.id, assigned_to.agent_number)
            metrics.MESSAGES_DELIVERED_TOTAL.inc()

            # Consume route lease after successful delivery
            if lease:
                from app.models.route_lease import RouteLease

                async with SessionLocal() as session:
                    result = await session.execute(
                        select(RouteLease).where(RouteLease.id == lease.id)
                    )
                    lease_obj = result.scalar_one_or_none()
                    if lease_obj:
                        await consume_route_lease(
                            session,
                            lease=lease_obj,
                            message_size_bytes=message_size_bytes,
                        )
                        await session.commit()
                        logger.debug(
                            "Consumed lease %s: messages=%d bytes=%d",
                            lease.id,
                            lease_obj.messages_sent,
                            lease_obj.bytes_sent,
                        )

            # Record delivered event
            async with SessionLocal() as session:
                event = MessageDeliveryEvent(
                    message_id=message.message_id,
                    task_id=task.id,
                    event_type="delivered",
                    route_type=route_decision.selected_route_type if route_decision else None,
                    relay_node_id=route_decision.selected_relay_node_id if route_decision else None,
                    latency_ms=latency_ms,
                )
                session.add(event)
                await session.commit()

            # Phase 18: Record route metric for SLA monitoring
            if route_decision:
                await _record_route_metric(
                    route_decision_id=route_decision.id,
                    latency_ms=latency_ms,
                    success=True,
                    relay_node_id=route_decision.selected_relay_node_id,
                )

            return DeliveryStatus.DELIVERED.value
        else:
            # Phase 18: Record failed delivery metric
            if route_decision:
                await _record_route_metric(
                    route_decision_id=route_decision.id,
                    latency_ms=0,
                    success=False,
                    error_code="DELIVERY_FAILED",
                    relay_node_id=route_decision.selected_relay_node_id,
                )

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

    # Record queued event
    async with SessionLocal() as session:
        event = MessageDeliveryEvent(
            message_id=message.message_id,
            task_id=task.id,
            event_type="queued",
            route_type=route_decision.selected_route_type if route_decision else None,
            relay_node_id=route_decision.selected_relay_node_id if route_decision else None,
        )
        session.add(event)
        await session.commit()

    return DeliveryStatus.QUEUED.value


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
    from app.models.message_delivery_event import MessageDeliveryEvent

    async with SessionLocal() as session:
        result = await session.execute(
            select(Message).where(Message.message_id == message_id)
        )
        msg = result.scalar_one_or_none()
        if msg is None:
            logger.debug("Ack for unknown message %s, ignoring", message_id)
            return

        if msg.delivery_status == DeliveryStatus.ACKNOWLEDGED.value:
            logger.debug("Message %s already acked, ignoring duplicate ack", message_id)
            return

        # Capture task_id before clearing fields for Redis cleanup
        task_id = msg.task_id

        msg.delivery_status = DeliveryStatus.ACKNOWLEDGED.value
        msg.next_retry_at = None
        await session.commit()
        metrics.MESSAGES_ACKED_TOTAL.inc()
        logger.info("Message %s acked", message_id)

        # Record acknowledged event
        event = MessageDeliveryEvent(
            message_id=message_id,
            task_id=task_id,
            event_type="acknowledged",
        )
        session.add(event)
        await session.commit()

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
    from app.models.message_delivery_event import MessageDeliveryEvent

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
                msg.delivery_status = DeliveryStatus.DELIVERY_FAILED.value
                # Record delivery_failed event
                event = MessageDeliveryEvent(
                    message_id=msg.message_id,
                    task_id=msg.task_id,
                    event_type="delivery_failed",
                    error_code="TASK_OR_AGENT_NOT_FOUND",
                    error_message="Task or assigned agent not found during retry",
                )
                session.add(event)
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
                # Record delivered event for retry
                event = MessageDeliveryEvent(
                    message_id=msg.message_id,
                    task_id=msg.task_id,
                    event_type="delivered",
                    extra_metadata={"retry_count": msg.retry_count},
                )
                session.add(event)
            else:
                msg.next_retry_at = now + timedelta(seconds=RETRY_BACKOFF_BASE_S)

            if msg.retry_count >= msg.max_retries:
                msg.delivery_status = DeliveryStatus.DELIVERY_FAILED.value
                logger.warning("Message %s exceeded max retries", msg.message_id)
                # Record delivery_failed event
                event = MessageDeliveryEvent(
                    message_id=msg.message_id,
                    task_id=msg.task_id,
                    event_type="delivery_failed",
                    error_code="MAX_RETRIES_EXCEEDED",
                    error_message=f"Exceeded max retries ({msg.max_retries})",
                )
                session.add(event)

        await session.commit()

        if retried:
            logger.info("Retried %d messages", retried)
        return retried


async def _record_route_metric(
    route_decision_id: uuid.UUID,
    latency_ms: int,
    success: bool,
    error_code: str | None = None,
    relay_node_id: uuid.UUID | None = None,
) -> None:
    """Record route metric for SLA monitoring (Phase 18).

    Phase 18: Also updates circuit breaker state based on delivery results.
    """
    from app.models.route_metric import RouteMetric

    async with SessionLocal() as session:
        # Get zone_id from relay_node if available
        zone_id = None
        if relay_node_id:
            from app.models.relay_node import RelayNode
            result = await session.execute(
                select(RelayNode).where(RelayNode.id == relay_node_id)
            )
            relay_node = result.scalar_one_or_none()
            if relay_node:
                zone_id = relay_node.zone

        metric = RouteMetric(
            route_decision_id=route_decision_id,
            metric_time=datetime.now(UTC),
            latency_ms=latency_ms,
            success=success,
            error_code=error_code,
            relay_node_id=relay_node_id,
            zone_id=zone_id,
        )
        session.add(metric)

        # Phase 18: Update circuit breaker if relay is involved
        if relay_node_id:
            try:
                from app.services.continuity_service import update_circuit_breaker
                await update_circuit_breaker(
                    session,
                    relay_node_id=relay_node_id,
                    success=success,
                    error_code=error_code,
                )
            except Exception as e:
                logger.warning(
                    "Failed to update circuit breaker for relay %s: %s",
                    relay_node_id,
                    e,
                )

        await session.commit()


async def expire_ttl_messages() -> int:
    """Expire messages that have exceeded their TTL."""
    from app.models.message_delivery_event import MessageDeliveryEvent

    now = datetime.now(UTC)

    async with SessionLocal() as session:
        from sqlalchemy import and_, or_

        # Find messages with TTL that have exceeded their time
        stmt = (
            select(Message)
            .where(
                Message.ttl_seconds.isnot(None),
                Message.delivery_status.in_([
                    DeliveryStatus.QUEUED.value,
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
                    # Record expired event
                    event = MessageDeliveryEvent(
                        message_id=msg.message_id,
                        task_id=msg.task_id,
                        event_type="expired",
                        error_message=f"Message exceeded TTL of {msg.ttl_seconds}s",
                    )
                    session.add(event)

        if expired:
            await session.commit()
            logger.info("Expired %d TTL-exceeded messages", expired)
        return expired
