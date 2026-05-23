"""SLA monitoring API endpoints."""

import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies.auth import CurrentSession
from app.dependencies.rbac import require_permission
from app.models.sla_target import SLATarget
from app.models.sla_violation import SLAViolation
from app.services import sla_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/sla", tags=["sla"])

# Permission constants
PERM_READ_SLA = "sla:read"
PERM_MANAGE_SLA = "sla:manage"


@router.get("/targets")
async def list_sla_targets(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_session: CurrentSession,
    _perm: Annotated[None, Depends(require_permission(PERM_READ_SLA))],
    scope_id: str | None = Query(None, description="Filter by scope_id"),
    enabled: bool | None = Query(None, description="Filter by enabled status"),
):
    """List all SLA targets."""
    query = select(SLATarget)
    if scope_id:
        query = query.where(SLATarget.scope_id == scope_id)
    if enabled is not None:
        query = query.where(SLATarget.enabled == enabled)

    result = await session.execute(query)
    targets = result.scalars().all()

    return {
        "targets": [
            {
                "id": str(t.id),
                "scope_id": t.scope_id,
                "target_name": t.target_name,
                "metric_type": t.metric_type,
                "target_value": t.target_value,
                "warning_threshold": t.warning_threshold,
                "critical_threshold": t.critical_threshold,
                "measurement_window_seconds": t.measurement_window_seconds,
                "enabled": t.enabled,
                "created_at": t.created_at.isoformat(),
                "updated_at": t.updated_at.isoformat(),
            }
            for t in targets
        ]
    }


@router.post("/targets")
async def create_sla_target(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_session: CurrentSession,
    _perm: Annotated[None, Depends(require_permission(PERM_MANAGE_SLA))],
    scope_id: str,
    target_name: str,
    metric_type: str,
    target_value: float,
    warning_threshold: float = 0.9,
    critical_threshold: float = 0.8,
    measurement_window_seconds: int = 300,
    enabled: bool = True,
):
    """Create a new SLA target."""
    target = await sla_service.create_sla_target(
        session,
        scope_id=scope_id,
        target_name=target_name,
        metric_type=metric_type,
        target_value=target_value,
        warning_threshold=warning_threshold,
        critical_threshold=critical_threshold,
        measurement_window_seconds=measurement_window_seconds,
        enabled=enabled,
    )
    await session.commit()

    return {
        "id": str(target.id),
        "scope_id": target.scope_id,
        "target_name": target.target_name,
        "metric_type": target.metric_type,
        "target_value": target.target_value,
        "warning_threshold": target.warning_threshold,
        "critical_threshold": target.critical_threshold,
        "measurement_window_seconds": target.measurement_window_seconds,
        "enabled": target.enabled,
        "created_at": target.created_at.isoformat(),
    }


@router.get("/violations")
async def list_sla_violations(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_session: CurrentSession,
    _perm: Annotated[None, Depends(require_permission(PERM_READ_SLA))],
    target_id: str | None = Query(None, description="Filter by target_id"),
    severity: str | None = Query(None, description="Filter by severity (warning/critical)"),
    resolved: bool | None = Query(None, description="Filter by resolution status"),
    limit: int = Query(100, ge=1, le=1000),
):
    """List SLA violations."""
    query = select(SLAViolation).order_by(SLAViolation.violation_time.desc())

    if target_id:
        query = query.where(SLAViolation.target_id == target_id)
    if severity:
        query = query.where(SLAViolation.severity == severity)
    if resolved is not None:
        if resolved:
            query = query.where(SLAViolation.resolved_at.isnot(None))
        else:
            query = query.where(SLAViolation.resolved_at.is_(None))

    query = query.limit(limit)
    result = await session.execute(query)
    violations = result.scalars().all()

    return {
        "violations": [
            {
                "id": str(v.id),
                "target_id": str(v.target_id),
                "violation_time": v.violation_time.isoformat(),
                "metric_value": v.metric_value,
                "severity": v.severity,
                "duration_seconds": v.duration_seconds,
                "resolved": v.resolved_at is not None,
                "resolved_at": v.resolved_at.isoformat() if v.resolved_at else None,
                "resolution_note": v.resolution_note,
            }
            for v in violations
        ]
    }


@router.get("/metrics")
async def query_sla_metrics(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_session: CurrentSession,
    _perm: Annotated[None, Depends(require_permission(PERM_READ_SLA))],
    scope_id: str,
    metric_type: str,
    window_seconds: int = Query(300, ge=60, le=86400),
):
    """Query current metric value for a scope."""
    metric_value = await sla_service.calculate_metrics(
        session,
        scope_id=scope_id,
        metric_type=metric_type,
        window_seconds=window_seconds,
    )

    return {
        "scope_id": scope_id,
        "metric_type": metric_type,
        "window_seconds": window_seconds,
        "metric_value": metric_value,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/report")
async def generate_sla_report(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_session: CurrentSession,
    _perm: Annotated[None, Depends(require_permission(PERM_READ_SLA))],
    scope_id: str | None = Query(None, description="Filter by scope_id"),
    hours: int = Query(24, ge=1, le=168, description="Report time window in hours"),
):
    """Generate SLA compliance report."""
    from datetime import timedelta, timezone

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=hours)

    report = await sla_service.generate_sla_report(
        session,
        scope_id=scope_id,
        start_time=start_time,
        end_time=end_time,
    )

    return report
