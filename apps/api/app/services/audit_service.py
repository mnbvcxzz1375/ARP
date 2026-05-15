"""Audit service: writes audit log entries. Never logs secrets."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


async def write_audit(
    session: AsyncSession,
    *,
    actor_type: str,
    actor_id: str,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    trace_id: str | None = None,
    task_id: str | None = None,
    message_id: str | None = None,
    delivery_status: str | None = None,
    error_code: str | None = None,
    details: dict[str, Any] | None = None,
    request_ip: str | None = None,
) -> None:
    """Write an audit log entry.

    **Security**: never pass secrets, tokens, API keys, or passwords in
    *details* or any field. This data is stored in plaintext in the DB.
    """
    entry = AuditLog(
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        trace_id=trace_id,
        task_id=task_id,
        message_id=message_id,
        delivery_status=delivery_status,
        error_code=error_code,
        details=details,
        request_ip=request_ip,
    )
    session.add(entry)
    logger.debug(
        "Audit: %s %s %s/%s",
        actor_type, action, resource_type, resource_id,
    )


async def list_audit_logs(
    session: AsyncSession,
    *,
    actor_type: str | None = None,
    actor_id: str | None = None,
    action: str | None = None,
    task_id: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[AuditLog], int]:
    """Query audit logs with optional filters."""
    stmt = select(AuditLog)
    count_stmt = select(func.count(AuditLog.id))

    if actor_type:
        stmt = stmt.where(AuditLog.actor_type == actor_type)
        count_stmt = count_stmt.where(AuditLog.actor_type == actor_type)
    if actor_id:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
        count_stmt = count_stmt.where(AuditLog.actor_id == actor_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
        count_stmt = count_stmt.where(AuditLog.action == action)
    if task_id:
        stmt = stmt.where(AuditLog.task_id == task_id)
        count_stmt = count_stmt.where(AuditLog.task_id == task_id)

    total = (await session.execute(count_stmt)).scalar() or 0
    result = await session.execute(
        stmt.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    )
    return list(result.scalars().all()), total
