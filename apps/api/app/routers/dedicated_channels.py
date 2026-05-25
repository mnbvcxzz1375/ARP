"""Dedicated channel router: CRUD, health check, and admin controls."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies.auth import CurrentSession
from app.dependencies.rbac import require_high_risk, require_permission
from app.exceptions import DomainException
from app.models.channel_health_check import ChannelHealthCheck
from app.models.dedicated_channel import DedicatedChannel
from app.protocol.constants import ErrorCode
from app.schemas.dedicated_channel import (
    ChannelHealthCheckResponse,
    DedicatedChannelCreate,
    DedicatedChannelListResponse,
    DedicatedChannelResponse,
    DedicatedChannelUpdate,
)
from app.services import dedicated_channel_service
from app.services.audit_service import write_audit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/dashboard/admin", tags=["dashboard"])


@router.get("/dedicated-channels", response_model=DedicatedChannelListResponse)
async def list_dedicated_channels(
    current_session: CurrentSession,
    channel_type: str | None = Query(None, description="Filter by channel type"),
    source_agent_id: UUID | None = Query(None, description="Filter by source agent"),
    target_agent_id: UUID | None = Query(None, description="Filter by target agent"),
    enabled: bool | None = Query(None, description="Filter by enabled status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _rbac: None = Depends(require_permission("admin:read")),
    session: AsyncSession = Depends(get_session),
):
    """List dedicated channels with optional filtering (admin read).

    Requires: admin:read
    Secrets in connection_config and encryption_config are masked.
    Audit: records every read of sensitive channel configuration metadata.
    """
    query = select(DedicatedChannel)

    if channel_type is not None:
        query = query.where(DedicatedChannel.channel_type == channel_type)
    if source_agent_id is not None:
        query = query.where(DedicatedChannel.source_agent_id == source_agent_id)
    if target_agent_id is not None:
        query = query.where(DedicatedChannel.target_agent_id == target_agent_id)
    if enabled is not None:
        query = query.where(DedicatedChannel.enabled == enabled)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_query)).scalar_one()

    query = query.order_by(DedicatedChannel.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(query)
    channels = list(result.scalars().all())

    await write_audit(
        session,
        actor_type="admin",
        actor_id=str(current_session.user_id),
        action="dedicated_channel.list",
        resource_type="dedicated_channel",
        resource_id="*",
        details={"total": total, "limit": limit, "offset": offset, "filters": {
            k: str(v) for k, v in [
                ("channel_type", channel_type), ("source_agent_id", source_agent_id),
                ("target_agent_id", target_agent_id), ("enabled", enabled),
            ] if v is not None
        }},
    )
    await session.commit()

    return DedicatedChannelListResponse(
        channels=[DedicatedChannelResponse.from_channel(ch) for ch in channels],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/dedicated-channels/{channel_id}", response_model=DedicatedChannelResponse)
async def get_dedicated_channel(
    channel_id: UUID,
    current_session: CurrentSession,
    _rbac: None = Depends(require_permission("admin:read")),
    session: AsyncSession = Depends(get_session),
):
    """Get a single dedicated channel by ID (admin read).

    Requires: admin:read
    """
    channel = await session.get(DedicatedChannel, channel_id)
    if not channel:
        raise DomainException(ErrorCode.RESOURCE_NOT_FOUND, f"Channel {channel_id} not found", status_code=404)

    await write_audit(
        session,
        actor_type="admin",
        actor_id=str(current_session.user_id),
        action="dedicated_channel.read",
        resource_type="dedicated_channel",
        resource_id=str(channel_id),
        details={"channel_name": channel.channel_name, "channel_type": channel.channel_type},
    )
    await session.commit()

    return DedicatedChannelResponse.from_channel(channel)


@router.post("/dedicated-channels", response_model=DedicatedChannelResponse, status_code=201)
async def create_dedicated_channel(
    body: DedicatedChannelCreate,
    current_session: CurrentSession,
    _rbac: None = Depends(require_high_risk("super_admin:write")),
    session: AsyncSession = Depends(get_session),
):
    """Create a new dedicated channel (super_admin + step-up required).

    Requires: super_admin:write + step-up
    """
    channel = await dedicated_channel_service.create_dedicated_channel(
        session,
        scope_id=body.scope_id,
        channel_name=body.channel_name,
        channel_type=body.channel_type,
        source_agent_id=body.source_agent_id,
        target_agent_id=body.target_agent_id,
        connection_config=body.connection_config,
        encryption_config=body.encryption_config,
        bandwidth_mbps=body.bandwidth_mbps,
        latency_target_ms=body.latency_target_ms,
    )

    await write_audit(
        session,
        actor_type="admin",
        actor_id=str(current_session.user_id),
        action="dedicated_channel.create",
        resource_type="dedicated_channel",
        resource_id=str(channel.id),
        details={"channel_name": body.channel_name, "channel_type": body.channel_type},
    )
    await session.commit()

    return DedicatedChannelResponse.from_channel(channel)


@router.patch("/dedicated-channels/{channel_id}", response_model=DedicatedChannelResponse)
async def update_dedicated_channel(
    channel_id: UUID,
    body: DedicatedChannelUpdate,
    current_session: CurrentSession,
    _rbac: None = Depends(require_high_risk("super_admin:write")),
    session: AsyncSession = Depends(get_session),
):
    """Update a dedicated channel (super_admin + step-up required).

    Requires: super_admin:write + step-up
    """
    channel = await session.get(DedicatedChannel, channel_id)
    if not channel:
        raise DomainException(ErrorCode.RESOURCE_NOT_FOUND, f"Channel {channel_id} not found", status_code=404)

    if body.channel_name is not None:
        channel.channel_name = body.channel_name
    if body.connection_config is not None:
        channel.connection_config = body.connection_config
    if body.encryption_config is not None:
        channel.encryption_config = body.encryption_config
    if body.bandwidth_mbps is not None:
        channel.bandwidth_mbps = body.bandwidth_mbps
    if body.latency_target_ms is not None:
        channel.latency_target_ms = body.latency_target_ms

    await write_audit(
        session,
        actor_type="admin",
        actor_id=str(current_session.user_id),
        action="dedicated_channel.update",
        resource_type="dedicated_channel",
        resource_id=str(channel_id),
        details={"updated_fields": list(body.model_fields_set)},
    )
    await session.commit()

    return DedicatedChannelResponse.from_channel(channel)


@router.post("/dedicated-channels/{channel_id}/enable", response_model=DedicatedChannelResponse)
async def enable_dedicated_channel(
    channel_id: UUID,
    current_session: CurrentSession,
    _rbac: None = Depends(require_high_risk("super_admin:write")),
    session: AsyncSession = Depends(get_session),
):
    """Enable a dedicated channel (super_admin + step-up required).

    Requires: super_admin:write + step-up
    """
    channel = await session.get(DedicatedChannel, channel_id)
    if not channel:
        raise DomainException(ErrorCode.RESOURCE_NOT_FOUND, f"Channel {channel_id} not found", status_code=404)

    channel.enabled = True

    await write_audit(
        session,
        actor_type="admin",
        actor_id=str(current_session.user_id),
        action="dedicated_channel.enable",
        resource_type="dedicated_channel",
        resource_id=str(channel_id),
    )
    await session.commit()

    return DedicatedChannelResponse.from_channel(channel)


@router.post("/dedicated-channels/{channel_id}/disable", response_model=DedicatedChannelResponse)
async def disable_dedicated_channel(
    channel_id: UUID,
    current_session: CurrentSession,
    _rbac: None = Depends(require_high_risk("super_admin:write")),
    session: AsyncSession = Depends(get_session),
):
    """Disable a dedicated channel (super_admin + step-up required).

    Requires: super_admin:write + step-up
    """
    channel = await session.get(DedicatedChannel, channel_id)
    if not channel:
        raise DomainException(ErrorCode.RESOURCE_NOT_FOUND, f"Channel {channel_id} not found", status_code=404)

    channel.enabled = False

    await write_audit(
        session,
        actor_type="admin",
        actor_id=str(current_session.user_id),
        action="dedicated_channel.disable",
        resource_type="dedicated_channel",
        resource_id=str(channel_id),
    )
    await session.commit()

    return DedicatedChannelResponse.from_channel(channel)


@router.post(
    "/dedicated-channels/{channel_id}/health-check",
    response_model=ChannelHealthCheckResponse,
)
async def trigger_health_check(
    channel_id: UUID,
    current_session: CurrentSession,
    _rbac: None = Depends(require_high_risk("super_admin:write")),
    session: AsyncSession = Depends(get_session),
):
    """Trigger a health check on a dedicated channel (super_admin + step-up required).

    Requires: super_admin:write + step-up
    Health-check is a write action (creates ChannelHealthCheck record), not a read.
    Audit: records health check invocation and result.
    """
    health_check = await dedicated_channel_service.verify_channel_health(session, channel_id)

    await write_audit(
        session,
        actor_type="admin",
        actor_id=str(current_session.user_id),
        action="dedicated_channel.health_check",
        resource_type="dedicated_channel",
        resource_id=str(channel_id),
        details={"status": health_check.status, "latency_ms": health_check.latency_ms},
    )
    await session.commit()

    return ChannelHealthCheckResponse.model_validate(health_check)


@router.get(
    "/dedicated-channels/{channel_id}/health-checks",
    response_model=list[ChannelHealthCheckResponse],
)
async def list_health_checks(
    channel_id: UUID,
    current_session: CurrentSession,
    limit: int = Query(20, ge=1, le=100),
    _rbac: None = Depends(require_permission("admin:read")),
    session: AsyncSession = Depends(get_session),
):
    """List recent health checks for a dedicated channel (admin read).

    Requires: admin:read
    Audit: records read of health check history.
    """
    result = await session.execute(
        select(ChannelHealthCheck)
        .where(ChannelHealthCheck.channel_id == channel_id)
        .order_by(ChannelHealthCheck.check_time.desc())
        .limit(limit)
    )
    checks = list(result.scalars().all())

    await write_audit(
        session,
        actor_type="admin",
        actor_id=str(current_session.user_id),
        action="dedicated_channel.list_health_checks",
        resource_type="dedicated_channel",
        resource_id=str(channel_id),
        details={"count": len(checks), "limit": limit},
    )
    await session.commit()

    return [ChannelHealthCheckResponse.model_validate(c) for c in checks]


@router.delete("/dedicated-channels/{channel_id}", status_code=204)
async def delete_dedicated_channel(
    channel_id: UUID,
    current_session: CurrentSession,
    _rbac: None = Depends(require_high_risk("super_admin:write")),
    session: AsyncSession = Depends(get_session),
):
    """Delete (revoke) a dedicated channel (super_admin + step-up required).

    Requires: super_admin:write + step-up
    """
    channel = await session.get(DedicatedChannel, channel_id)
    if not channel:
        raise DomainException(ErrorCode.RESOURCE_NOT_FOUND, f"Channel {channel_id} not found", status_code=404)

    await write_audit(
        session,
        actor_type="admin",
        actor_id=str(current_session.user_id),
        action="dedicated_channel.delete",
        resource_type="dedicated_channel",
        resource_id=str(channel_id),
        details={"channel_name": channel.channel_name, "channel_type": channel.channel_type},
    )
    await session.delete(channel)
    await session.commit()