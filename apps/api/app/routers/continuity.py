"""Continuity router: business continuity and failover management API."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies.rbac import require_permission
from app.exceptions import DomainException
from app.models.circuit_breaker import CircuitBreaker
from app.models.failover_config import FailoverConfig
from app.models.failover_event import FailoverEvent
from app.protocol.constants import ErrorCode
from app.services.continuity_service import (
    check_relay_health,
    execute_failover,
    rollback_failover,
    trigger_failover,
)

router = APIRouter(prefix="/v1/continuity", tags=["continuity"])

# Permission constants
PERM_READ_CONTINUITY = "continuity:read"
PERM_MANAGE_CONTINUITY = "continuity:manage"


@router.get("/failover-configs")
async def list_failover_configs(
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_permission(PERM_READ_CONTINUITY)),
) -> dict[str, Any]:
    """List all failover configurations."""
    result = await session.execute(select(FailoverConfig))
    configs = result.scalars().all()

    return {
        "configs": [
            {
                "id": str(c.id),
                "scope_id": str(c.scope_id),
                "primary_relay_id": str(c.primary_relay_id),
                "backup_relay_ids": c.backup_relay_ids,
                "failover_threshold_seconds": c.failover_threshold_seconds,
                "auto_failover_enabled": c.auto_failover_enabled,
                "manual_approval_required": c.manual_approval_required,
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat(),
            }
            for c in configs
        ]
    }


@router.post("/failover-configs")
async def create_failover_config(
    scope_id: str,
    primary_relay_id: str,
    backup_relay_ids: list[str],
    failover_threshold_seconds: int = 60,
    auto_failover_enabled: bool = True,
    manual_approval_required: bool = False,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_permission(PERM_MANAGE_CONTINUITY)),
) -> dict[str, Any]:
    """Create a new failover configuration."""
    try:
        scope_uuid = uuid.UUID(scope_id)
        primary_uuid = uuid.UUID(primary_relay_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid UUID: {e}")

    # Validate backup relay IDs
    for backup_id in backup_relay_ids:
        try:
            uuid.UUID(backup_id)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid backup relay ID: {backup_id}")

    config = FailoverConfig(
        scope_id=scope_uuid,
        primary_relay_id=primary_uuid,
        backup_relay_ids=backup_relay_ids,
        failover_threshold_seconds=failover_threshold_seconds,
        auto_failover_enabled=auto_failover_enabled,
        manual_approval_required=manual_approval_required,
    )
    session.add(config)
    await session.commit()
    await session.refresh(config)

    return {
        "id": str(config.id),
        "scope_id": str(config.scope_id),
        "primary_relay_id": str(config.primary_relay_id),
        "backup_relay_ids": config.backup_relay_ids,
        "failover_threshold_seconds": config.failover_threshold_seconds,
        "auto_failover_enabled": config.auto_failover_enabled,
        "manual_approval_required": config.manual_approval_required,
        "created_at": config.created_at.isoformat(),
    }


@router.post("/failover/{config_id}/trigger")
async def trigger_manual_failover(
    config_id: str,
    trigger_reason: str,
    approval_id: str | None = None,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_permission(PERM_MANAGE_CONTINUITY)),
) -> dict[str, Any]:
    """Manually trigger a failover."""
    try:
        config_uuid = uuid.UUID(config_id)
        approval_uuid = uuid.UUID(approval_id) if approval_id else None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid UUID: {e}")

    try:
        event = await trigger_failover(
            session,
            config_id=config_uuid,
            trigger_reason=trigger_reason,
            auto_triggered=False,
            approval_id=approval_uuid,
        )
        await session.commit()

        # Execute immediately if no approval required
        result = await session.execute(
            select(FailoverConfig).where(FailoverConfig.id == config_uuid)
        )
        config = result.scalar_one_or_none()

        if config and not config.manual_approval_required:
            event = await execute_failover(session, event.id)
            await session.commit()

        return {
            "id": str(event.id),
            "config_id": str(event.config_id),
            "event_time": event.event_time.isoformat(),
            "trigger_reason": event.trigger_reason,
            "from_relay_id": str(event.from_relay_id),
            "to_relay_id": str(event.to_relay_id),
            "status": event.status,
            "auto_triggered": event.auto_triggered,
        }
    except DomainException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/failover/{event_id}/execute")
async def execute_manual_failover(
    event_id: str,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_permission(PERM_MANAGE_CONTINUITY)),
) -> dict[str, Any]:
    """Execute a pending failover event."""
    try:
        event_uuid = uuid.UUID(event_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid UUID: {e}")

    try:
        event = await execute_failover(session, event_uuid)
        await session.commit()

        return {
            "id": str(event.id),
            "status": event.status,
            "affected_task_count": event.affected_task_count,
            "completed_at": event.completed_at.isoformat() if event.completed_at else None,
        }
    except DomainException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/failover/{event_id}/rollback")
async def rollback_manual_failover(
    event_id: str,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_permission(PERM_MANAGE_CONTINUITY)),
) -> dict[str, Any]:
    """Rollback a completed failover event."""
    try:
        event_uuid = uuid.UUID(event_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid UUID: {e}")

    try:
        event = await rollback_failover(session, event_uuid)
        await session.commit()

        return {
            "id": str(event.id),
            "status": event.status,
            "rollback_at": event.rollback_at.isoformat() if event.rollback_at else None,
        }
    except DomainException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/failover-events")
async def list_failover_events(
    config_id: str | None = None,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_permission(PERM_MANAGE_CONTINUITY)),
) -> dict[str, Any]:
    """List failover events."""
    stmt = select(FailoverEvent).order_by(FailoverEvent.event_time.desc()).limit(limit)

    if config_id:
        try:
            config_uuid = uuid.UUID(config_id)
            stmt = stmt.where(FailoverEvent.config_id == config_uuid)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid config_id UUID")

    result = await session.execute(stmt)
    events = result.scalars().all()

    return {
        "events": [
            {
                "id": str(e.id),
                "config_id": str(e.config_id),
                "event_time": e.event_time.isoformat(),
                "trigger_reason": e.trigger_reason,
                "from_relay_id": str(e.from_relay_id),
                "to_relay_id": str(e.to_relay_id),
                "affected_task_count": e.affected_task_count,
                "auto_triggered": e.auto_triggered,
                "status": e.status,
                "completed_at": e.completed_at.isoformat() if e.completed_at else None,
                "rollback_at": e.rollback_at.isoformat() if e.rollback_at else None,
                "error_message": e.error_message,
            }
            for e in events
        ]
    }


@router.get("/circuit-breakers")
async def list_circuit_breakers(
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_permission(PERM_MANAGE_CONTINUITY)),
) -> dict[str, Any]:
    """List all circuit breakers."""
    result = await session.execute(select(CircuitBreaker))
    breakers = result.scalars().all()

    return {
        "circuit_breakers": [
            {
                "id": str(b.id),
                "relay_node_id": str(b.relay_node_id),
                "state": b.state,
                "failure_count": b.failure_count,
                "success_count": b.success_count,
                "last_failure_time": b.last_failure_time.isoformat() if b.last_failure_time else None,
                "open_until": b.open_until.isoformat() if b.open_until else None,
                "success_threshold": b.success_threshold,
                "failure_threshold": b.failure_threshold,
                "is_open": b.is_open,
                "should_allow_request": b.should_allow_request,
            }
            for b in breakers
        ]
    }


@router.post("/circuit-breakers/{breaker_id}/reset")
async def reset_circuit_breaker(
    breaker_id: str,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_permission(PERM_MANAGE_CONTINUITY)),
) -> dict[str, Any]:
    """Manually reset a circuit breaker to closed state."""
    try:
        breaker_uuid = uuid.UUID(breaker_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid UUID: {e}")

    result = await session.execute(
        select(CircuitBreaker).where(CircuitBreaker.id == breaker_uuid)
    )
    breaker = result.scalar_one_or_none()

    if not breaker:
        raise HTTPException(status_code=404, detail="Circuit breaker not found")

    breaker.state = "closed"
    breaker.failure_count = 0
    breaker.success_count = 0
    breaker.open_until = None

    await session.commit()

    return {
        "id": str(breaker.id),
        "relay_node_id": str(breaker.relay_node_id),
        "state": breaker.state,
        "message": "Circuit breaker reset to closed state",
    }


@router.get("/relay-health/{relay_id}")
async def get_relay_health(
    relay_id: str,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_permission(PERM_MANAGE_CONTINUITY)),
) -> dict[str, Any]:
    """Check relay node health status."""
    try:
        relay_uuid = uuid.UUID(relay_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid UUID: {e}")

    health = await check_relay_health(session, relay_uuid)

    return health
