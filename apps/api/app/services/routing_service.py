"""Routing service: resolve, deliver online, queue offline, handle ack, retry."""

import json
import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal
from app.exceptions import DomainException
from app.metrics import ROUTE_DECISIONS_TOTAL, ROUTE_FALLBACK_TOTAL
from app.models.agent import Agent
from app.models.message import Message
from app.models.route_decision import RouteDecision
from app.models.task import Task
from app.protocol.constants import ErrorCode, DeliveryStatus, MessageType, TaskStatus
from app import metrics

logger = logging.getLogger(__name__)

DELIVERY_TIMEOUT_S = 30
RETRY_BACKOFF_BASE_S = 5


def _copy_security_marker(ws_payload: dict, content: object) -> None:
    """Copy the envelope security block from stored content into a WS payload.

    M2 invariants:

    - copy only — the values are the sender's verbatim marker block;
    - never construct a block the sender did not send (no marker in the
      content means no marker in the delivered payload);
    - never rewrite it (no mode upgrade/downgrade, no nonce regeneration).

    The ``encrypted_payload`` / ``aad`` fields already ride inside
    ``ws_payload["payload"]`` (the full sender envelope), so only the
    ``security`` marker needs a top-level copy for cheap dispatch.
    """
    if not isinstance(content, dict):
        return
    security = content.get("security")
    if isinstance(security, dict):
        ws_payload["security"] = dict(security)


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
    M3: Delivery is dispatched on selected_route_type to the transport layer
    (app.transports). The transport reports what actually happened — sent
    locally, sent cross-node, queued offline, or queued-after-pub/sub-failure —
    and this function maps that truth onto delivery events and status. It no
    longer pre-guesses "online" from presence before sending: an online guess
    whose send fails used to fall through to the same "queued" code path as a
    genuinely offline agent, conflating the two; the transport result keeps
    them apart.
    """
    from app.models.message_delivery_event import MessageDeliveryEvent
    from app.services.lease_service import verify_route_lease, consume_route_lease
    from app.transports import select_transport

    route_type = route_decision.selected_route_type if route_decision else None

    # ws_payload["payload"] is the sender envelope verbatim: the M2 security
    # block (security / encrypted_payload / aad) is copied, never parsed or
    # rebuilt, by the platform.
    ws_payload = {
        "type": MessageType.TASK_REQUEST.value,
        "message_id": message.message_id,
        "task_id": str(task.id),
        "payload": message.content,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    # M2: copy the marker block from the sender's envelope verbatim — the
    # platform only relays it, it never constructs, infers, or rewrites
    # security material (never downgrades or upgrades a mode).
    _copy_security_marker(ws_payload, message.content)

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
                # Fail closed: an invalid or exhausted lease must block
                # delivery, never silently fall through.
                raise DomainException(
                    ErrorCode.NO_AVAILABLE_RELAY,
                    f"Route lease {route_decision.lease_id} is invalid or exhausted "
                    f"for task {task.id}",
                    status_code=403,
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

    # Record delivering event (the attempt starts now, whatever the outcome)
    async with SessionLocal() as session:
        event = MessageDeliveryEvent(
            message_id=message.message_id,
            task_id=task.id,
            event_type="delivering",
            route_type=route_type,
            relay_node_id=route_decision.selected_relay_node_id if route_decision else None,
        )
        session.add(event)
        await session.commit()

    # M3: dispatch on route_type to the transport layer.
    transport = select_transport(route_type)
    result = await transport.deliver(
        agent_id=assigned_to.id,
        message=json.dumps(ws_payload),
        message_id=message.message_id,
        task_id=task.id,
        source_agent_id=task.created_by,
        relay_node_id=route_decision.selected_relay_node_id if route_decision else None,
        track_pending=True,
    )
    latency_ms = int((datetime.now(UTC) - delivery_start).total_seconds() * 1000)

    if result.is_sent:
        logger.info(
            "Delivered task %s to agent %s via %s transport (outcome=%s node=%s)",
            task.id,
            assigned_to.agent_number,
            route_type or "central",
            result.outcome,
            result.node_id,
        )
        metrics.MESSAGES_DELIVERED_TOTAL.inc()

        # Consume route lease after successful delivery
        if lease:
            from app.models.route_lease import RouteLease

            async with SessionLocal() as session:
                lease_result = await session.execute(
                    select(RouteLease).where(RouteLease.id == lease.id)
                )
                lease_obj = lease_result.scalar_one_or_none()
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
                route_type=route_type,
                relay_node_id=route_decision.selected_relay_node_id if route_decision else None,
                latency_ms=result.latency_ms if result.latency_ms is not None else latency_ms,
                extra_metadata={"outcome": result.outcome, "node_id": result.node_id},
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

    # Not sent: queue under agent_id. When the agent reconnects,
    # deliver_pending_on_connect() picks up messages from both the
    # agent_id queue (offline) and the session_id queue (resume).
    from app.services.session_service import store_pending_message
    await store_pending_message(
        assigned_to.id,
        str(assigned_to.id),
        json.dumps(ws_payload),
    )
    metrics.PENDING_MESSAGES.inc()
    logger.info(
        "Queued task %s for agent %s (outcome=%s%s)",
        task.id,
        assigned_to.agent_number,
        result.outcome,
        f" error={result.error_code}" if result.error_code else "",
    )

    # Record queued event. A degraded outcome (pub/sub broke mid-dispatch)
    # is recorded with its error code so the timeline stays truthful —
    # "queued" alone would read as "agent was offline".
    async with SessionLocal() as session:
        event = MessageDeliveryEvent(
            message_id=message.message_id,
            task_id=task.id,
            event_type="queued",
            route_type=route_type,
            relay_node_id=route_decision.selected_relay_node_id if route_decision else None,
            error_code=result.error_code,
            error_message=result.error_message,
            extra_metadata={"outcome": result.outcome, "node_id": result.node_id},
        )
        session.add(event)
        await session.commit()

    # M3: a queued message is NOT a relay delivery failure — the transport
    # never failed, the agent is simply not reachable right now. Feeding
    # queued outcomes into the route metric would trip the relay's circuit
    # breaker on ordinary offline traffic (and a pub/sub degradation is a
    # bus problem, not the relay node's). Only a transport-level FAILED
    # outcome counts as a delivery failure for SLA/circuit-breaker purposes.
    if route_decision and result.outcome == "failed":
        await _record_route_metric(
            route_decision_id=route_decision.id,
            latency_ms=latency_ms,
            success=False,
            error_code=result.error_code or "DELIVERY_FAILED",
            relay_node_id=route_decision.selected_relay_node_id,
        )

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
            mid = ""
            try:
                msg_data = json.loads(raw)
                mid = msg_data.get("message_id", "")
                delivered.append(mid)
            except json.JSONDecodeError:
                pass
            # M2: the bytes just reached a live connection, so a queued
            # message must flip to delivered — otherwise an offline-created
            # task stays "created" forever and the receiver's
            # accept/complete state machine can never fire. This mirrors
            # exactly what the online delivery path does.
            await _mark_delivered_after_reconnect(mid)

    logger.info("Delivered %d pending messages to agent %s", len(delivered), agent.agent_number)
    return delivered


async def _mark_delivered_after_reconnect(message_id: str) -> None:
    """Flip a queued message (and its task) to delivered on reconnect.

    Idempotent-ish: only touches rows still in queued status; already
    delivered/acked rows are left alone. Also arms the retry worker for
    the un-acked case, like the online path.
    """
    if not message_id:
        return
    async with SessionLocal() as session:
        result = await session.execute(
            select(Message).where(Message.message_id == message_id)
        )
        msg = result.scalar_one_or_none()
        if msg is None or msg.delivery_status != DeliveryStatus.QUEUED.value:
            return
        msg.delivery_status = DeliveryStatus.DELIVERED.value
        msg.next_retry_at = datetime.now(UTC) + timedelta(seconds=RETRY_BACKOFF_BASE_S)
        if msg.task_id is not None:
            task_result = await session.execute(
                select(Task).where(Task.id == msg.task_id)
            )
            task = task_result.scalar_one_or_none()
            if task is not None and task.status in (
                TaskStatus.CREATED.value,
                TaskStatus.QUEUED.value,
            ):
                task.status = TaskStatus.DELIVERED.value
        await session.commit()


async def ack_message(message_id: str) -> None:
    """Mark a message as acked. Idempotent — re-acking is a no-op for
    bookkeeping, but a duplicate ack still removes any pending copy that
    landed after the first ack (redelivery/queue race), so an ack is
    always convergent."""
    from app.models.message_delivery_event import MessageDeliveryEvent

    async with SessionLocal() as session:
        result = await session.execute(
            select(Message).where(Message.message_id == message_id)
        )
        msg = result.scalar_one_or_none()
        if msg is None:
            logger.debug("Ack for unknown message %s, ignoring", message_id)
            return

        already_acked = msg.delivery_status == DeliveryStatus.ACKNOWLEDGED.value
        if already_acked:
            logger.debug("Message %s already acked, processing duplicate ack", message_id)

        # Capture task_id before clearing fields for Redis cleanup
        task_id = msg.task_id

        if not already_acked:
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

        # Clean up Redis pending queue for this agent. Runs on every ack
        # (including duplicates): a redelivered copy that landed after the
        # first ack must not linger in the queue forever.
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


RETRY_CLAIM_WINDOW_S = 30
"""How long a retry claim hides a row from other instances of this worker.

Must comfortably exceed a send round-trip, so two concurrent instances of
retry_unacked_messages never re-send the same message.
"""

_RETRY_CLAIM_SELECT_SQL = text(
    """
    SELECT id FROM messages
    WHERE delivery_status = :delivered_status
      AND next_retry_at <= :now
      AND retry_count < max_retries
    ORDER BY next_retry_at
    FOR UPDATE SKIP LOCKED
    """
)

_RETRY_CLAIM_UPDATE_SQL = text(
    """
    UPDATE messages
    SET delivery_status = :delivering_status,
        next_retry_at = :claim_until
    WHERE id = :row_id
    """
)


async def retry_unacked_messages() -> int:
    """Retry worker: find delivered-but-unacked messages past their retry window,
    re-deliver them, and apply backoff.

    M3 claim protocol (claim first, send after, never hold row locks across
    the send round-trip):

        claim:  SELECT ... FOR UPDATE SKIP LOCKED  (single statement)
                UPDATE delivery_status = 'delivering', next_retry_at = now + window
        COMMIT  <- row locks released here
        send:   transport round-trip
        finish: final status in a separate transaction

    SKIP LOCKED only matters for concurrent instances of this SAME statement
    (two event-loop instances / replicas). The offline delivery worker scans
    a strictly disjoint row set ('queued'/'delivering'), so by construction
    the two workers can never claim the same row; there is no cross-worker
    concurrency to guard here.

    The claim intentionally has NO LIMIT: a bounded batch ordered by
    next_retry_at (most overdue first) lets an accumulated backlog of
    overdue rows crowd a freshly-armed message out of the batch, so a
    message whose retry window just opened would wait an arbitrary number
    of cycles before being claimed — its retry bookkeeping (retry_count,
    backoff) would depend on how much unrelated backlog exists. Claiming
    the full due set every cycle guarantees forward progress for every
    due message; SKIP LOCKED still splits the set across concurrent
    instances/replicas.

    Returns number of messages retried.
    """
    from app.models.message_delivery_event import MessageDeliveryEvent
    from app.transports import select_transport

    now = datetime.now(UTC)
    claim_until = now + timedelta(seconds=RETRY_CLAIM_WINDOW_S)

    async with SessionLocal() as session:
        claim_result = await session.execute(
            _RETRY_CLAIM_SELECT_SQL,
            {
                "delivered_status": DeliveryStatus.DELIVERED.value,
                "now": now,
            },
        )
        claimed_ids = [uuid.UUID(str(row.id)) for row in claim_result]

        for row_id in claimed_ids:
            await session.execute(
                _RETRY_CLAIM_UPDATE_SQL,
                {
                    "delivering_status": DeliveryStatus.DELIVERING.value,
                    "claim_until": claim_until,
                    "row_id": row_id,
                },
            )
        await session.commit()
        # Row locks released: the send round-trip below holds none.

    if not claimed_ids:
        return 0

    transport = select_transport(None)
    retried = 0

    for mid in claimed_ids:
        async with SessionLocal() as session:
            msg = await session.get(Message, mid)
            if msg is None:
                continue

            # Get the task to find assigned_to
            task_result = await session.execute(
                select(Task).where(Task.id == msg.task_id)
            )
            task = task_result.scalar_one_or_none()
            if task is None or task.assigned_to is None:
                msg.delivery_status = DeliveryStatus.DELIVERY_FAILED.value
                msg.next_retry_at = None
                # Record delivery_failed event
                event = MessageDeliveryEvent(
                    message_id=msg.message_id,
                    task_id=msg.task_id,
                    event_type="delivery_failed",
                    error_code="TASK_OR_AGENT_NOT_FOUND",
                    error_message="Task or assigned agent not found during retry",
                )
                session.add(event)
                await session.commit()
                continue

            agent_id = task.assigned_to
            ws_payload = {
                "type": msg.type,
                "message_id": msg.message_id,
                "task_id": str(task.id),
                "payload": msg.content,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            # M2: same copy-only marker semantics as the first delivery.
            _copy_security_marker(ws_payload, msg.content)

            send_result = await transport.deliver(
                agent_id=agent_id,
                message=json.dumps(ws_payload),
                message_id=msg.message_id,
                task_id=task.id,
                source_agent_id=task.created_by,
                track_pending=True,
            )

            if send_result.is_sent:
                msg.retry_count += 1
                backoff = RETRY_BACKOFF_BASE_S * (2 ** msg.retry_count)
                msg.next_retry_at = datetime.now(UTC) + timedelta(seconds=backoff)
                msg.delivery_status = DeliveryStatus.DELIVERED.value
                metrics.MESSAGES_RETRIED_TOTAL.inc()
                retried += 1
                # Record delivered event for retry
                event = MessageDeliveryEvent(
                    message_id=msg.message_id,
                    task_id=msg.task_id,
                    event_type="delivered",
                    extra_metadata={
                        "retry_count": msg.retry_count,
                        "outcome": send_result.outcome,
                        "node_id": send_result.node_id,
                    },
                )
                session.add(event)
            elif send_result.is_queued:
                # Agent unreachable (or pub/sub degraded): re-arm the retry
                # window WITHOUT consuming an attempt — the transport never
                # failed, the agent is simply not there right now.
                msg.delivery_status = DeliveryStatus.DELIVERED.value
                backoff = RETRY_BACKOFF_BASE_S * (2 ** msg.retry_count)
                msg.next_retry_at = datetime.now(UTC) + timedelta(seconds=backoff)
            else:
                # Delivery genuinely failed: count this attempt so a
                # permanently unreachable agent eventually exhausts
                # max_retries instead of being retried forever.
                msg.delivery_status = DeliveryStatus.DELIVERED.value
                msg.retry_count += 1
                if msg.retry_count >= msg.max_retries:
                    msg.delivery_status = DeliveryStatus.DELIVERY_FAILED.value
                    msg.next_retry_at = None
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
                else:
                    backoff = RETRY_BACKOFF_BASE_S * (2 ** msg.retry_count)
                    msg.next_retry_at = datetime.now(UTC) + timedelta(seconds=backoff)

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
