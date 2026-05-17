"""Task service: creation, idempotency, state machine, lease management."""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.exceptions import DomainException
from app.models.task import Task, VALID_TRANSITIONS
from app.models.message import Message
from app.models.agent import Agent
from app.services.routing_service import deliver_task_request, resolve_agent
from app.protocol.constants import ErrorCode, TaskStatus, MessageType, DeliveryStatus
from app import metrics

logger = logging.getLogger(__name__)


def _lease_duration() -> int:
    return get_settings().task_lease_duration_s


async def create_task(
    session: AsyncSession,
    *,
    from_agent: Agent,
    to_agent_number: str,
    idempotency_key: str | None,
    payload: dict,
) -> Task:
    to_agent = await resolve_agent(session, to_agent_number)

    if idempotency_key:
        existing = await _find_by_idempotency_key(
            session, idempotency_key,
            from_agent_id=from_agent.id, to_agent_id=to_agent.id,
        )
        if existing:
            logger.info("Idempotent task found: %s -> %s", idempotency_key, existing.id)
            return existing

    # Phase 5: Enforce connection policy
    from app.services.connection_service import enforce_policy
    requested_modes = payload.get("requested_security_modes", [])
    await enforce_policy(session, from_agent, to_agent, requested_security_modes=requested_modes if requested_modes else None)

    # Save IDs before flush — ORM objects expire after rollback
    from_agent_id = from_agent.id
    to_agent_id = to_agent.id

    task = Task(
        idempotency_key=idempotency_key,
        created_by=from_agent_id,
        assigned_to=to_agent_id,
        status=TaskStatus.CREATED.value,
        message_id=str(uuid.uuid4()),
    )
    session.add(task)

    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        existing = await _find_by_idempotency_key(
            session, idempotency_key,
            from_agent_id=from_agent_id, to_agent_id=to_agent_id,
        )
        if existing:
            return existing
        raise

    msg = Message(
        task_id=task.id,
        message_id=task.message_id,
        type=MessageType.TASK_REQUEST.value,
        delivery_status=DeliveryStatus.PENDING.value,
        content=payload,
    )
    session.add(msg)

    await session.commit()
    await session.refresh(task)
    await session.refresh(msg)

    # Audit: task created
    from app.services.audit_service import write_audit
    await write_audit(
        session,
        actor_type="agent",
        actor_id=str(from_agent.id),
        action="task.created",
        resource_type="task",
        resource_id=str(task.id),
        task_id=str(task.id),
        message_id=task.message_id,
        details={"to_agent": to_agent_number},
    )

    logger.info("Task created: id=%s from=%s to=%s", task.id, from_agent.agent_number, to_agent_number)
    metrics.TASKS_CREATED_TOTAL.inc()

    # Route: deliver online or queue offline
    delivery_status = await deliver_task_request(task, msg, to_agent)
    msg.delivery_status = delivery_status
    # Update task status to reflect delivery state
    if delivery_status == DeliveryStatus.DELIVERED.value:
        task.status = TaskStatus.DELIVERED.value
    await session.commit()
    logger.info("Task %s delivery status: %s", task.id, delivery_status)

    # Audit: delivery
    await write_audit(
        session,
        actor_type="system",
        actor_id="relay",
        action="task.delivered",
        resource_type="task",
        resource_id=str(task.id),
        task_id=str(task.id),
        message_id=task.message_id,
        delivery_status=delivery_status,
    )

    return task


async def get_task(
    session: AsyncSession,
    task_id: uuid.UUID,
    *,
    owner_id: uuid.UUID | None = None,
) -> Task:
    stmt = select(Task).where(Task.id == task_id)
    if owner_id is not None:
        # Only return the task if the requesting user owns one of the involved agents
        owned_agent_ids = select(Agent.id).where(Agent.owner_id == owner_id)
        stmt = stmt.where(
            Task.created_by.in_(owned_agent_ids) | Task.assigned_to.in_(owned_agent_ids)
        )
    result = await session.execute(stmt)
    task = result.scalar_one_or_none()
    if task is None:
        raise DomainException(
            ErrorCode.TASK_NOT_FOUND,
            f"Task {task_id} not found",
            status_code=404,
        )
    return task


async def list_tasks(
    session: AsyncSession,
    agent_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    status: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[Task], int]:
    stmt = select(Task)
    if user_id is not None:
        # Show tasks for ALL agents owned by this user
        owned_agent_ids = select(Agent.id).where(Agent.owner_id == user_id)
        stmt = stmt.where(
            Task.created_by.in_(owned_agent_ids) | Task.assigned_to.in_(owned_agent_ids)
        )
    elif agent_id:
        stmt = stmt.where(
            (Task.created_by == agent_id) | (Task.assigned_to == agent_id)
        )
    if status:
        stmt = stmt.where(Task.status == status)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(Task.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def transition_state(
    session: AsyncSession,
    task: Task,
    new_status: str,
    *,
    lease_agent_id: uuid.UUID | None = None,
) -> Task:
    valid = VALID_TRANSITIONS.get(task.status, set())
    if new_status not in valid:
        raise DomainException(
            ErrorCode.INVALID_TASK_STATE_TRANSITION,
            f"Cannot transition from {task.status} to {new_status}",
            status_code=409,
            details={"current": task.status, "requested": new_status, "allowed": sorted(valid)},
        )

    old_status = task.status
    task.status = new_status

    if new_status == TaskStatus.RUNNING.value:
        task.lease_agent_id = lease_agent_id
        task.lease_expires_at = datetime.now(UTC) + timedelta(seconds=_lease_duration())

    if new_status in (TaskStatus.COMPLETED.value, TaskStatus.FAILED.value, TaskStatus.CANCELLED.value,
                      TaskStatus.EXPIRED.value, TaskStatus.REJECTED.value):
        task.lease_expires_at = None
        task.lease_agent_id = None

    await session.commit()
    await session.refresh(task)

    # Audit: state transition
    from app.services.audit_service import write_audit
    await write_audit(
        session,
        actor_type="agent",
        actor_id=str(lease_agent_id) if lease_agent_id else "system",
        action=f"task.{new_status}",
        resource_type="task",
        resource_id=str(task.id),
        task_id=str(task.id),
        details={"old_status": old_status, "new_status": new_status},
    )

    logger.info("Task state transition: %s -> %s (task=%s)", old_status, new_status, task.id)
    return task


async def accept_task(session: AsyncSession, task: Task, *, agent_id: uuid.UUID | None = None) -> Task:
    """Accept a delivered task, transitioning it to accepted."""
    if task.status not in (TaskStatus.DELIVERED.value,):
        raise DomainException(
            ErrorCode.INVALID_TASK_STATE_TRANSITION,
            f"Cannot accept task in {task.status} state",
            status_code=409,
        )
    task.status = TaskStatus.ACCEPTED.value
    await session.commit()
    await session.refresh(task)

    from app.services.audit_service import write_audit
    await write_audit(
        session,
        actor_type="agent",
        actor_id=str(agent_id) if agent_id else (str(task.assigned_to) if task.assigned_to else 'unknown'),
        action="task.accepted",
        resource_type="task",
        resource_id=str(task.id),
        task_id=str(task.id),
    )

    logger.info("Task %s accepted by agent %s", task.id, agent_id)
    return task


async def start_task(session: AsyncSession, task: Task, *, agent_id: uuid.UUID | None = None) -> Task:
    """Start an accepted task, transitioning it to running with a lease."""
    if task.status != TaskStatus.ACCEPTED.value:
        raise DomainException(
            ErrorCode.INVALID_TASK_STATE_TRANSITION,
            f"Cannot start task in {task.status} state",
            status_code=409,
        )
    task.status = TaskStatus.RUNNING.value
    task.lease_expires_at = datetime.now(UTC) + timedelta(seconds=_lease_duration())
    task.lease_agent_id = agent_id
    await session.commit()
    await session.refresh(task)

    from app.services.audit_service import write_audit
    await write_audit(
        session,
        actor_type="agent",
        actor_id=str(agent_id) if agent_id else (str(task.assigned_to) if task.assigned_to else 'unknown'),
        action="task.running",
        resource_type="task",
        resource_id=str(task.id),
        task_id=str(task.id),
    )

    logger.info("Task %s started (running)", task.id)
    return task


async def record_progress(
    session: AsyncSession,
    task: Task,
    *,
    progress_pct: int | None = None,
    message: str | None = None,
    data: dict | None = None,
) -> Task:
    """Record a progress update. Refreshes lease and creates progress entry."""
    if task.status != TaskStatus.RUNNING.value:
        raise DomainException(
            ErrorCode.INVALID_TASK_STATE_TRANSITION,
            f"Cannot record progress on task in {task.status} state",
            status_code=409,
        )

    # Refresh lease
    task.last_progress_at = datetime.now(UTC)
    task.lease_expires_at = datetime.now(UTC) + timedelta(seconds=_lease_duration())

    # Create progress entry
    from app.models.task_progress import TaskProgress

    # Get next seq
    max_seq = await session.execute(
        select(func.coalesce(func.max(TaskProgress.seq), 0)).where(TaskProgress.task_id == task.id)
    )
    next_seq = max_seq.scalar_one() + 1

    entry = TaskProgress(
        task_id=task.id,
        seq=next_seq,
        status=task.status,
        progress_pct=progress_pct,
        message=message,
        data=data,
    )
    session.add(entry)
    await session.commit()
    await session.refresh(task)

    logger.info("Task %s progress: seq=%d pct=%s", task.id, next_seq, progress_pct)
    return task


async def complete_task(
    session: AsyncSession,
    task: Task,
    *,
    result: dict | None = None,
) -> Task:
    """Mark a task as completed with result."""
    if task.status not in (TaskStatus.RUNNING.value, TaskStatus.ACCEPTED.value, TaskStatus.DELIVERED.value):
        raise DomainException(
            ErrorCode.INVALID_TASK_STATE_TRANSITION,
            f"Cannot complete task in {task.status} state",
            status_code=409,
        )

    lease_agent = task.lease_agent_id
    assigned_agent = task.assigned_to
    task.status = TaskStatus.COMPLETED.value
    task.result = result
    task.lease_expires_at = None
    task.lease_agent_id = None

    await session.commit()
    await session.refresh(task)

    # Audit: task completed
    from app.services.audit_service import write_audit
    audit_agent_id = str(lease_agent) if lease_agent else str(assigned_agent) if assigned_agent else "unknown"
    await write_audit(
        session,
        actor_type="agent",
        actor_id=audit_agent_id,
        action="task.completed",
        resource_type="task",
        resource_id=str(task.id),
        task_id=str(task.id),
    )

    logger.info("Task %s completed", task.id)
    metrics.TASKS_COMPLETED_TOTAL.inc()
    return task


async def fail_task(
    session: AsyncSession,
    task: Task,
    *,
    error_message: str | None = None,
) -> Task:
    """Mark a task as failed with error message."""
    if task.status not in (TaskStatus.RUNNING.value, TaskStatus.ACCEPTED.value, TaskStatus.DELIVERED.value):
        raise DomainException(
            ErrorCode.INVALID_TASK_STATE_TRANSITION,
            f"Cannot fail task in {task.status} state",
            status_code=409,
        )

    lease_agent_fail = task.lease_agent_id
    assigned_agent_fail = task.assigned_to

    # Sanitize agent-supplied error_message: truncate + strip newlines
    if error_message and len(error_message) > 1024:
        error_message = error_message[:1024]
    if error_message:
        error_message = " ".join(error_message.split())

    task.status = TaskStatus.FAILED.value
    task.error_message = error_message
    task.lease_expires_at = None
    task.lease_agent_id = None

    await session.commit()
    await session.refresh(task)

    # Audit: task failed
    from app.services.audit_service import write_audit
    audit_agent_id_fail = str(lease_agent_fail) if lease_agent_fail else str(assigned_agent_fail) if assigned_agent_fail else "unknown"
    await write_audit(
        session,
        actor_type="agent",
        actor_id=audit_agent_id_fail,
        action="task.failed",
        resource_type="task",
        resource_id=str(task.id),
        task_id=str(task.id),
        error_code=ErrorCode.TASK_EXPIRED.value if error_message and "expired" in error_message.lower() else None,
        details={"error": error_message} if error_message else None,
    )

    logger.info("Task %s failed: %s", task.id, error_message)
    metrics.TASKS_FAILED_TOTAL.inc()
    return task


async def request_approval(
    session: AsyncSession,
    task: Task,
    *,
    risk_level: str,
    action_kind: str,
    action_preview: str | None = None,
    reason: str | None = None,
) -> Task:
    """Transition task to awaiting_approval and create an approval request."""
    if task.status != TaskStatus.RUNNING.value:
        raise DomainException(
            ErrorCode.INVALID_TASK_STATE_TRANSITION,
            f"Cannot request approval on task in {task.status} state",
            status_code=409,
        )

    task.status = TaskStatus.AWAITING_APPROVAL.value
    await session.flush()

    from app.services.approval_service import create_approval
    await create_approval(
        session,
        task_id=task.id,
        agent_id=task.assigned_to,
        risk_level=risk_level,
        action_kind=action_kind,
        action_preview=action_preview,
        reason=reason,
    )

    await session.commit()
    await session.refresh(task)

    # Audit: approval requested
    from app.services.audit_service import write_audit
    await write_audit(
        session,
        actor_type="agent",
        actor_id=str(task.assigned_to) if task.assigned_to else "unknown",
        action="task.awaiting_approval",
        resource_type="task",
        resource_id=str(task.id),
        task_id=str(task.id),
        details={"risk_level": risk_level, "action_kind": action_kind},
    )

    logger.info("Task %s awaiting approval: risk=%s action=%s", task.id, risk_level, action_kind)
    return task


async def list_task_progress(
    session: AsyncSession,
    task_id,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list, int]:
    """List progress entries for a task."""
    from app.models.task_progress import TaskProgress as TP

    stmt = select(TP).where(TP.task_id == task_id)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(TP.seq.asc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all()), total



async def heartbeat_task(
    session: AsyncSession,
    task: Task,
    agent_id: uuid.UUID,
) -> Task:
    """Refresh the task lease - extends lease_expires_at and updates heartbeat timestamp."""
    if task.status != TaskStatus.RUNNING.value:
        raise DomainException(
            ErrorCode.INVALID_TASK_STATE_TRANSITION,
            f"Cannot heartbeat task in {task.status} state",
            status_code=409,
        )

    now = datetime.now(UTC)
    task.last_heartbeat_at = now
    task.last_progress_at = now
    task.lease_expires_at = now + timedelta(seconds=_lease_duration())

    await session.commit()
    await session.refresh(task)

    logger.info("Task %s heartbeat received, lease extended", task.id)
    return task

async def _find_by_idempotency_key(
    session: AsyncSession,
    key: str,
    *,
    from_agent_id: uuid.UUID | None = None,
    to_agent_id: uuid.UUID | None = None,
) -> Task | None:
    stmt = select(Task).where(Task.idempotency_key == key)
    if from_agent_id is not None:
        stmt = stmt.where(Task.created_by == from_agent_id)
    if to_agent_id is not None:
        stmt = stmt.where(Task.assigned_to == to_agent_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()









