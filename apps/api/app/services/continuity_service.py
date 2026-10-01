"""Continuity service: business continuity and failover management."""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DomainException
from app.metrics import CIRCUIT_BREAKER_STATE, FAILOVER_EVENTS_TOTAL
from app.models.circuit_breaker import CircuitBreaker
from app.models.failover_config import FailoverConfig
from app.models.failover_event import FailoverEvent
from app.models.relay_node import RelayNode
from app.models.task import Task
from app.protocol.constants import ErrorCode, TaskStatus
from app.services.audit_service import write_audit

logger = logging.getLogger(__name__)

CIRCUIT_BREAKER_OPEN_DURATION_SECONDS = 60
CIRCUIT_BREAKER_HALF_OPEN_TEST_WINDOW = 30


async def check_relay_health(session: AsyncSession, relay_node_id: uuid.UUID) -> dict:
    """Check relay node health status.

    Returns:
        dict with keys: is_healthy, status, last_heartbeat_age_seconds, reason
    """
    result = await session.execute(
        select(RelayNode).where(RelayNode.id == relay_node_id)
    )
    relay = result.scalar_one_or_none()

    if not relay:
        return {
            "is_healthy": False,
            "status": "not_found",
            "last_heartbeat_age_seconds": None,
            "reason": "Relay node not found",
        }

    if not relay.enabled:
        return {
            "is_healthy": False,
            "status": "disabled",
            "last_heartbeat_age_seconds": None,
            "reason": "Relay node is disabled",
        }

    if relay.status not in ["healthy", "degraded"]:
        return {
            "is_healthy": False,
            "status": relay.status,
            "last_heartbeat_age_seconds": None,
            "reason": f"Relay status is {relay.status}",
        }

    if not relay.last_heartbeat_at:
        return {
            "is_healthy": False,
            "status": "no_heartbeat",
            "last_heartbeat_age_seconds": None,
            "reason": "No heartbeat received",
        }

    now = datetime.now(UTC)
    age_seconds = (now - relay.last_heartbeat_at).total_seconds()

    if age_seconds > 60:
        return {
            "is_healthy": False,
            "status": "heartbeat_timeout",
            "last_heartbeat_age_seconds": age_seconds,
            "reason": f"Heartbeat timeout ({age_seconds:.0f}s since last heartbeat)",
        }

    return {
        "is_healthy": True,
        "status": relay.status,
        "last_heartbeat_age_seconds": age_seconds,
        "reason": "Relay is healthy",
    }


async def get_or_create_circuit_breaker(
    session: AsyncSession,
    relay_node_id: uuid.UUID,
) -> CircuitBreaker:
    """Get or create circuit breaker for a relay node."""
    result = await session.execute(
        select(CircuitBreaker).where(CircuitBreaker.relay_node_id == relay_node_id)
    )
    breaker = result.scalar_one_or_none()

    if not breaker:
        breaker = CircuitBreaker(relay_node_id=relay_node_id)
        session.add(breaker)
        await session.flush()
        logger.info("Created circuit breaker for relay %s", relay_node_id)

    return breaker


async def update_circuit_breaker(
    session: AsyncSession,
    relay_node_id: uuid.UUID,
    success: bool,
    error_code: str | None = None,
) -> CircuitBreaker:
    """Update circuit breaker state based on delivery result.

    Args:
        relay_node_id: The relay node ID
        success: Whether the delivery succeeded
        error_code: Optional error code if failed

    Returns:
        Updated CircuitBreaker instance
    """
    breaker = await get_or_create_circuit_breaker(session, relay_node_id)
    now = datetime.now(UTC)

    # Check if circuit should transition from open to half_open
    if breaker.state == "open" and breaker.open_until and now >= breaker.open_until:
        breaker.state = "half_open"
        breaker.success_count = 0
        breaker.failure_count = 0
        logger.info("Circuit breaker %s transitioned to half_open", relay_node_id)
        await write_audit(
                    session,
                    actor_type="system",
                    actor_id="system",
            action="circuit_breaker_half_open",
            resource_type="circuit_breaker",
            resource_id=str(breaker.id),
            details={
                "relay_node_id": str(relay_node_id),
                "previous_state": "open",
            },
        )

    if success:
        if breaker.state == "closed":
            # Reset failure count on success in closed state
            breaker.failure_count = 0
        elif breaker.state == "half_open":
            # Count successes in half_open state
            breaker.success_count += 1
            if breaker.success_count >= breaker.success_threshold:
                # Transition to closed; capture the success count BEFORE the
                # reset below so the audit reflects what triggered recovery.
                recovered_success_count = breaker.success_count
                breaker.state = "closed"
                breaker.failure_count = 0
                breaker.success_count = 0
                breaker.open_until = None
                logger.info("Circuit breaker %s closed after recovery", relay_node_id)
                await write_audit(
                    session,
                    actor_type="system",
                    actor_id="system",
                    action="circuit_breaker_closed",
                    resource_type="circuit_breaker",
                    resource_id=str(breaker.id),
                    details={
                        "relay_node_id": str(relay_node_id),
                        "success_count": recovered_success_count,
                    },
                )
    else:
        # Failure
        breaker.last_failure_time = now

        if breaker.state == "closed":
            breaker.failure_count += 1
            if breaker.failure_count >= breaker.failure_threshold:
                # Trip circuit
                breaker.state = "open"
                breaker.open_until = now + timedelta(seconds=CIRCUIT_BREAKER_OPEN_DURATION_SECONDS)
                logger.warning(
                    "Circuit breaker %s opened after %d failures",
                    relay_node_id,
                    breaker.failure_count,
                )
                await write_audit(
                    session,
                    actor_type="system",
                    actor_id="system",
                    action="circuit_breaker_opened",
                    resource_type="circuit_breaker",
                    resource_id=str(breaker.id),
                    details={
                        "relay_node_id": str(relay_node_id),
                        "failure_count": breaker.failure_count,
                        "error_code": error_code,
                        "open_until": breaker.open_until.isoformat(),
                    },
                )
        elif breaker.state == "half_open":
            # Failure in half_open means back to open
            breaker.state = "open"
            breaker.open_until = now + timedelta(seconds=CIRCUIT_BREAKER_OPEN_DURATION_SECONDS)
            breaker.success_count = 0
            breaker.failure_count = 1
            logger.warning("Circuit breaker %s reopened after failure in half_open", relay_node_id)
            await write_audit(
                    session,
                    actor_type="system",
                    actor_id="system",
                action="circuit_breaker_reopened",
                resource_type="circuit_breaker",
                resource_id=str(breaker.id),
                details={
                    "relay_node_id": str(relay_node_id),
                    "error_code": error_code,
                },
            )

    breaker.updated_at = now

    # Prometheus: update circuit breaker state gauge
    state_value = {"closed": 0, "half_open": 1, "open": 2}.get(breaker.state, 0)
    CIRCUIT_BREAKER_STATE.labels(relay_id=str(relay_node_id)).set(state_value)

    return breaker


async def get_backup_relay(
    session: AsyncSession,
    config: FailoverConfig,
    exclude_relay_ids: list[uuid.UUID] | None = None,
) -> RelayNode | None:
    """Get the next available backup relay from config.

    Args:
        config: Failover configuration
        exclude_relay_ids: List of relay IDs to exclude (already failed)

    Returns:
        Next healthy backup relay or None
    """
    exclude_relay_ids = exclude_relay_ids or []

    for backup_id_str in config.backup_relay_ids:
        try:
            backup_id = uuid.UUID(backup_id_str)
        except ValueError:
            logger.warning("Invalid backup relay ID in config: %s", backup_id_str)
            continue

        if backup_id in exclude_relay_ids:
            continue

        # Check health
        health = await check_relay_health(session, backup_id)
        if not health["is_healthy"]:
            logger.debug(
                "Backup relay %s not healthy: %s",
                backup_id,
                health["reason"],
            )
            continue

        # Check circuit breaker
        breaker_result = await session.execute(
            select(CircuitBreaker).where(CircuitBreaker.relay_node_id == backup_id)
        )
        breaker = breaker_result.scalar_one_or_none()

        if breaker and breaker.state == "open":
            logger.debug("Backup relay %s circuit breaker is open", backup_id)
            continue

        # Get relay node
        result = await session.execute(
            select(RelayNode).where(RelayNode.id == backup_id)
        )
        relay = result.scalar_one_or_none()

        if relay:
            logger.info("Selected backup relay %s for failover", backup_id)
            return relay

    return None


async def trigger_failover(
    session: AsyncSession,
    config_id: uuid.UUID,
    trigger_reason: str,
    auto_triggered: bool = True,
    approval_id: uuid.UUID | None = None,
) -> FailoverEvent:
    """Trigger a failover event.

    Args:
        config_id: Failover configuration ID
        trigger_reason: Reason for triggering failover
        auto_triggered: Whether this was automatically triggered
        approval_id: Optional approval ID if manual approval was required

    Returns:
        Created FailoverEvent
    """
    result = await session.execute(
        select(FailoverConfig).where(FailoverConfig.id == config_id)
    )
    config = result.scalar_one_or_none()

    if not config:
        raise DomainException(
            ErrorCode.RESOURCE_NOT_FOUND,
            f"Failover config {config_id} not found",
            status_code=404,
        )

    # Check if manual approval is required but not provided
    if config.manual_approval_required and not approval_id:
        raise DomainException(
            ErrorCode.APPROVAL_REQUIRED,
            "Manual approval required for this failover",
            status_code=403,
        )

    # Get backup relay
    backup_relay = await get_backup_relay(session, config)

    if not backup_relay:
        raise DomainException(
            ErrorCode.NO_AVAILABLE_RELAY,
            "No healthy backup relay available",
            status_code=503,
        )

    # Create failover event
    event = FailoverEvent(
        config_id=config_id,
        event_time=datetime.now(UTC),
        trigger_reason=trigger_reason,
        from_relay_id=config.primary_relay_id,
        to_relay_id=backup_relay.id,
        auto_triggered=auto_triggered,
        approval_id=approval_id,
        status="pending",
    )
    session.add(event)
    await session.flush()

    logger.info(
        "Triggered failover %s: %s -> %s (reason: %s)",
        event.id,
        config.primary_relay_id,
        backup_relay.id,
        trigger_reason,
    )

    await write_audit(
                    session,
                    actor_type="system",
                    actor_id="system",
        action="failover_triggered",
        resource_type="failover_event",
        resource_id=str(event.id),
        details={
            "config_id": str(config_id),
            "from_relay_id": str(config.primary_relay_id),
            "to_relay_id": str(backup_relay.id),
            "trigger_reason": trigger_reason,
            "auto_triggered": auto_triggered,
        },
    )

    # Prometheus: record failover event
    FAILOVER_EVENTS_TOTAL.labels(
        config_id=str(config_id), trigger=trigger_reason
    ).inc()

    return event


async def execute_failover(
    session: AsyncSession,
    event_id: uuid.UUID,
) -> FailoverEvent:
    """Execute a failover by migrating tasks from primary to backup relay.

    Args:
        event_id: Failover event ID

    Returns:
        Updated FailoverEvent
    """
    result = await session.execute(
        select(FailoverEvent).where(FailoverEvent.id == event_id)
    )
    event = result.scalar_one_or_none()

    if not event:
        raise DomainException(
            ErrorCode.RESOURCE_NOT_FOUND,
            f"Failover event {event_id} not found",
            status_code=404,
        )

    if event.status != "pending":
        raise DomainException(
            ErrorCode.INVALID_STATE,
            f"Failover event is in {event.status} state, cannot execute",
            status_code=400,
        )

    event.status = "in_progress"
    await session.flush()

    try:
        from app.models.route_decision import RouteDecision

        # Query all active tasks assigned to the failing relay
        # Active statuses: DELIVERED, ACCEPTED, RUNNING
        result = await session.execute(
            select(Task, RouteDecision)
            .join(RouteDecision, Task.id == RouteDecision.task_id)
            .where(
                RouteDecision.selected_relay_node_id == event.from_relay_id,
                Task.status.in_([
                    TaskStatus.DELIVERED.value,
                    TaskStatus.ACCEPTED.value,
                    TaskStatus.RUNNING.value,
                ]),
            )
        )
        task_route_pairs = result.all()

        migrated_count = 0
        tasks_needing_notification = []

        # Migrate each task by updating its route decision
        for task, route_decision in task_route_pairs:
            # Update the route decision to point to the backup relay
            route_decision.selected_relay_node_id = event.to_relay_id

            # Track tasks that are actively running and may need notification
            if task.status == TaskStatus.RUNNING.value:
                tasks_needing_notification.append({
                    "task_id": str(task.id),
                    "status": task.status,
                    "assigned_to": str(task.assigned_to) if task.assigned_to else None,
                })

            migrated_count += 1

        event.affected_task_count = migrated_count

        # Log the failover execution with details
        logger.info(
            "Executing failover %s: migrated %d tasks from %s to %s (%d running tasks may need notification)",
            event.id,
            migrated_count,
            event.from_relay_id,
            event.to_relay_id,
            len(tasks_needing_notification),
        )

        # Mark failover as completed
        event.status = "completed"
        event.completed_at = datetime.now(UTC)

        await write_audit(
            session,
            actor_type="system",
            actor_id="system",
            action="failover_completed",
            resource_type="failover_event",
            resource_id=str(event.id),
            details={
                "from_relay_id": str(event.from_relay_id),
                "to_relay_id": str(event.to_relay_id),
                "affected_task_count": event.affected_task_count,
                "migrated_count": migrated_count,
                "tasks_needing_notification": tasks_needing_notification,
            },
        )

        return event

    except Exception as e:
        # Roll back the partial migration. The failure bookkeeping below
        # must run in a FRESH transaction: after rollback() the event row
        # in this session is expired, and since this exception propagates
        # to the caller, anything written to `session` here would never be
        # committed — leaving the event stuck in "pending" forever.
        await session.rollback()
        logger.error("Failover %s failed: %s", event.id, e, exc_info=True)

        from app.database import SessionLocal

        async with SessionLocal() as cleanup_session:
            result = await cleanup_session.execute(
                select(FailoverEvent).where(FailoverEvent.id == event.id)
            )
            failed_event = result.scalar_one_or_none()
            if failed_event is not None:
                failed_event.status = "failed"
                failed_event.error_message = str(e)[:2000]
                await write_audit(
                    cleanup_session,
                    actor_type="system",
                    actor_id="system",
                    action="failover_failed",
                    resource_type="failover_event",
                    resource_id=str(failed_event.id),
                    details={
                        "error": str(e)[:2000],
                        "from_relay_id": str(failed_event.from_relay_id),
                        "to_relay_id": str(failed_event.to_relay_id),
                    },
                )
                await cleanup_session.commit()

        raise


async def rollback_failover(
    session: AsyncSession,
    event_id: uuid.UUID,
) -> FailoverEvent:
    """Rollback a completed failover.

    Args:
        event_id: Failover event ID

    Returns:
        Updated FailoverEvent
    """
    result = await session.execute(
        select(FailoverEvent).where(FailoverEvent.id == event_id)
    )
    event = result.scalar_one_or_none()

    if not event:
        raise DomainException(
            ErrorCode.RESOURCE_NOT_FOUND,
            f"Failover event {event_id} not found",
            status_code=404,
        )

    if event.status != "completed":
        raise DomainException(
            ErrorCode.INVALID_STATE,
            f"Can only rollback completed failovers, current state: {event.status}",
            status_code=400,
        )

    # Mark as rolled back
    event.status = "rolled_back"
    event.rollback_at = datetime.now(UTC)

    logger.info("Rolled back failover %s", event.id)

    await write_audit(
                    session,
                    actor_type="system",
                    actor_id="system",
        action="failover_rolled_back",
        resource_type="failover_event",
        resource_id=str(event.id),
        details={
            "from_relay_id": str(event.from_relay_id),
            "to_relay_id": str(event.to_relay_id),
        },
    )

    return event


async def check_and_trigger_auto_failover(session: AsyncSession) -> list[FailoverEvent]:
    """Check all failover configs and trigger auto-failover if needed.

    This should be called periodically by a background worker.

    Returns:
        List of triggered failover events
    """
    result = await session.execute(
        select(FailoverConfig).where(FailoverConfig.auto_failover_enabled == True)
    )
    configs = result.scalars().all()

    triggered_events = []

    for config in configs:
        # Check primary relay health
        health = await check_relay_health(session, config.primary_relay_id)

        if health["is_healthy"]:
            continue

        # Check if unhealthy for threshold duration
        if health["last_heartbeat_age_seconds"] is not None:
            if health["last_heartbeat_age_seconds"] < config.failover_threshold_seconds:
                continue

        # Check if there's already a pending/in_progress failover for this config
        existing_result = await session.execute(
            select(FailoverEvent)
            .where(
                FailoverEvent.config_id == config.id,
                FailoverEvent.status.in_(["pending", "in_progress"]),
            )
            .order_by(FailoverEvent.event_time.desc())
            .limit(1)
        )
        existing_event = existing_result.scalar_one_or_none()

        if existing_event:
            logger.debug(
                "Failover already in progress for config %s, skipping",
                config.id,
            )
            continue

        # Trigger failover
        try:
            event = await trigger_failover(
                session,
                config_id=config.id,
                trigger_reason=f"Auto-failover: {health['reason']}",
                auto_triggered=True,
            )
            triggered_events.append(event)

            # If manual approval not required, execute immediately
            if not config.manual_approval_required:
                await execute_failover(session, event.id)

        except DomainException as e:
            logger.warning(
                "Failed to trigger auto-failover for config %s: %s",
                config.id,
                e.message,
            )
        except Exception as e:
            # Non-domain errors (e.g. DB failures) must not escape the loop:
            # they would skip the commit below and silently drop every
            # FailoverEvent already triggered in this batch. execute_failover
            # already persisted its own failure state in a fresh session.
            logger.error(
                "Auto-failover execution error for config %s: %s",
                config.id,
                e,
                exc_info=True,
            )

    if triggered_events:
        await session.commit()
        logger.info("Triggered %d auto-failovers", len(triggered_events))

    return triggered_events
