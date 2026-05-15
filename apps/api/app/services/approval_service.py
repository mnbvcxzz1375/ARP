"""Approval service: create, accept, reject, expire for human-in-the-loop."""

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DomainException
from app.models.approval import Approval
from app.models.task import Task
from app.protocol.constants import ErrorCode, TaskStatus
from app.services.audit_service import write_audit

logger = logging.getLogger(__name__)

APPROVAL_DEFAULT_TIMEOUT_S = 120


async def create_approval(
    session: AsyncSession,
    *,
    task_id: UUID,
    agent_id: UUID,
    risk_level: str,
    action_kind: str,
    action_preview: str | None = None,
    reason: str | None = None,
    expires_in_seconds: int = APPROVAL_DEFAULT_TIMEOUT_S,
) -> Approval:
    """Create an approval request for a high-risk action."""
    approval = Approval(
        task_id=task_id,
        agent_id=agent_id,
        status="pending",
        risk_level=risk_level,
        action_kind=action_kind,
        action_preview=action_preview,
        reason=reason,
        expires_at=datetime.now(UTC) + timedelta(seconds=expires_in_seconds),
    )
    session.add(approval)
    await session.commit()
    await session.refresh(approval)

    # Audit: approval created
    await write_audit(
        session,
        actor_type="agent",
        actor_id=str(agent_id),
        action="approval.created",
        resource_type="approval",
        resource_id=str(approval.id),
        task_id=str(task_id),
        details={"risk_level": risk_level, "action_kind": action_kind},
    )

    logger.info(
        "Approval created: %s task=%s risk=%s action=%s",
        approval.id, task_id, risk_level, action_kind,
    )
    return approval


async def accept_approval(session: AsyncSession, approval_id: UUID) -> Approval:
    """Accept a pending approval."""
    approval = await _get_approval(session, approval_id)
    if approval.status != "pending":
        raise DomainException(
            ErrorCode.APPROVAL_REJECTED,
            f"Approval {approval_id} is not pending (current: {approval.status})",
            status_code=409,
        )

    approval.status = "accepted"
    approval.decided_at = datetime.now(UTC)

    # Transition task back to running
    task = await session.get(Task, approval.task_id)
    if task and task.status == TaskStatus.AWAITING_APPROVAL.value:
        task.status = TaskStatus.RUNNING.value
        from datetime import timedelta
        from app.config import get_settings
        ttl = get_settings().task_lease_duration_s
        task.lease_expires_at = datetime.now(UTC) + timedelta(seconds=ttl)

    await session.commit()
    await session.refresh(approval)

    # Audit: approval accepted
    await write_audit(
        session,
        actor_type="system",
        actor_id="relay",
        action="approval.accepted",
        resource_type="approval",
        resource_id=str(approval.id),
        task_id=str(approval.task_id),
    )

    logger.info("Approval %s accepted, task %s back to running", approval_id, approval.task_id)
    return approval


async def reject_approval(session: AsyncSession, approval_id: UUID) -> Approval:
    """Reject a pending approval."""
    approval = await _get_approval(session, approval_id)
    if approval.status != "pending":
        raise DomainException(
            ErrorCode.APPROVAL_REJECTED,
            f"Approval {approval_id} is not pending (current: {approval.status})",
            status_code=409,
        )

    approval.status = "rejected"
    approval.decided_at = datetime.now(UTC)

    # Mark task as rejected/failed
    task = await session.get(Task, approval.task_id)
    if task and task.status == TaskStatus.AWAITING_APPROVAL.value:
        task.status = TaskStatus.REJECTED.value

    await session.commit()
    await session.refresh(approval)

    # Audit: approval rejected
    await write_audit(
        session,
        actor_type="system",
        actor_id="relay",
        action="approval.rejected",
        resource_type="approval",
        resource_id=str(approval.id),
        task_id=str(approval.task_id),
        error_code=ErrorCode.APPROVAL_REJECTED.value,
    )

    logger.info("Approval %s rejected, task %s set to rejected", approval_id, approval.task_id)
    return approval


async def expire_stale_approvals() -> int:
    """Expire approvals past their expires_at. Returns count expired."""
    now = datetime.now(UTC)
    from app.database import SessionLocal

    async with SessionLocal() as session:
        result = await session.execute(
            select(Approval).where(
                Approval.status == "pending",
                Approval.expires_at.isnot(None),
                Approval.expires_at <= now,
            ).limit(100)
        )
        approvals = result.scalars().all()

        for approval in approvals:
            approval.status = "expired"
            approval.decided_at = now

            task = await session.get(Task, approval.task_id)
            if task and task.status == TaskStatus.AWAITING_APPROVAL.value:
                task.status = TaskStatus.FAILED.value
                task.error_message = "Approval request expired"

            # Audit: approval expired
            await write_audit(
                session,
                actor_type="system",
                actor_id="relay",
                action="approval.expired",
                resource_type="approval",
                resource_id=str(approval.id),
                task_id=str(approval.task_id),
            )

        await session.commit()

        if approvals:
            logger.info("Expired %d stale approvals", len(approvals))
        return len(approvals)


async def list_approvals(
    session: AsyncSession,
    task_id: UUID | None = None,
    status: str | None = None,
    owner_id: UUID | None = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[Approval], int]:
    from sqlalchemy import func
    from app.models.agent import Agent

    stmt = select(Approval)
    if owner_id is not None:
        stmt = stmt.join(Agent, Agent.id == Approval.agent_id).where(Agent.owner_id == owner_id)
    if task_id:
        stmt = stmt.where(Approval.task_id == task_id)
    if status:
        stmt = stmt.where(Approval.status == status)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(Approval.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def _get_approval(session: AsyncSession, approval_id: UUID) -> Approval:
    result = await session.execute(
        select(Approval).where(Approval.id == approval_id)
    )
    approval = result.scalar_one_or_none()
    if approval is None:
        raise DomainException(
            ErrorCode.APPROVAL_REQUIRED,
            f"Approval {approval_id} not found",
            status_code=404,
        )
    return approval
