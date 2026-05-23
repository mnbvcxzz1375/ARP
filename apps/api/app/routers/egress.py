"""Egress router: egress gateway logs and monitoring."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies.auth import CurrentSession
from app.dependencies.rbac import require_permission
from app.models.egress_log import EgressLog
from app.schemas.egress_log import EgressLogListResponse, EgressLogResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/dashboard/admin", tags=["dashboard"])


@router.get("/egress-logs", response_model=EgressLogListResponse)
async def list_egress_logs(
    current_session: CurrentSession,
    gateway_id: UUID | None = Query(None, description="Filter by gateway ID"),
    task_id: UUID | None = Query(None, description="Filter by task ID"),
    agent_id: UUID | None = Query(None, description="Filter by agent ID"),
    target_domain: str | None = Query(None, description="Filter by target domain"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    _rbac: None = Depends(require_permission("admin:read")),
    session: AsyncSession = Depends(get_session),
):
    """List egress logs with optional filtering (admin only).

    Returns egress gateway request logs with filtering and pagination.

    Requires: admin:read permission
    """
    query = select(EgressLog)

    # Apply filters
    if gateway_id is not None:
        query = query.where(EgressLog.gateway_id == gateway_id)

    if task_id is not None:
        query = query.where(EgressLog.task_id == task_id)

    if agent_id is not None:
        query = query.where(EgressLog.agent_id == agent_id)

    if target_domain is not None:
        query = query.where(EgressLog.target_domain.ilike(f"%{target_domain}%"))

    # Order by created_at descending (most recent first)
    query = query.order_by(EgressLog.created_at.desc())

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar_one()

    # Apply pagination
    query = query.limit(limit).offset(offset)

    result = await session.execute(query)
    logs = list(result.scalars().all())

    logger.info(
        "Admin %s listed %d egress logs (total=%d, gateway_id=%s, task_id=%s, agent_id=%s, domain=%s)",
        current_session.user_id if current_session else "unknown",
        len(logs),
        total,
        gateway_id,
        task_id,
        agent_id,
        target_domain,
    )

    return EgressLogListResponse(
        logs=[EgressLogResponse.model_validate(log) for log in logs],
        total=total,
    )
