"""Personal mode REST API endpoints."""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.exceptions import DomainException
from app.services.auth import authenticate
from app.models.agent import Agent
from app.models.personal_scope import PersonalScope
from app.models.relay_node import RelayNode
from app.models.user import User
from app.protocol.constants import ErrorCode
from app.schemas.personal import (
    PersonalEdgeRelayHeartbeat,
    PersonalEdgeRelayRegister,
    PersonalEdgeRelayResponse,
    PersonalScopeResponse,
    PersonalScopeUpdate,
)
from app.services.edge_discovery import (
    get_personal_edge_relays,
    process_edge_heartbeat,
    register_personal_edge_relay,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/personal", tags=["personal"])


@router.get("/scope", response_model=PersonalScopeResponse)
async def get_personal_scope(
    current_user: Annotated[User, Depends(authenticate)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """Get personal scope configuration for current user.

    Auto-creates if not exists.
    """
    result = await session.execute(
        select(PersonalScope).where(PersonalScope.user_id == current_user.id)
    )
    scope = result.scalar_one_or_none()

    if not scope:
        # Auto-create personal scope
        scope = PersonalScope(
            user_id=current_user.id,
            scope_name="personal",
            default_relay_type="central_relay",
            enable_edge_relay=False,
            enable_secure_channel=False,
        )
        session.add(scope)
        await session.commit()
        await session.refresh(scope)
        logger.info("Auto-created personal scope for user: %s", current_user.id)

    return PersonalScopeResponse(
        user_id=str(scope.user_id),
        scope_name=scope.scope_name,
        default_relay_type=scope.default_relay_type,
        enable_edge_relay=scope.enable_edge_relay,
        enable_secure_channel=scope.enable_secure_channel,
        created_at=scope.created_at,
        updated_at=scope.updated_at,
    )


@router.patch("/scope", response_model=PersonalScopeResponse)
async def update_personal_scope(
    update: PersonalScopeUpdate,
    current_user: Annotated[User, Depends(authenticate)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """Update personal scope configuration."""
    result = await session.execute(
        select(PersonalScope).where(PersonalScope.user_id == current_user.id)
    )
    scope = result.scalar_one_or_none()

    if not scope:
        # Auto-create if not exists
        scope = PersonalScope(
            user_id=current_user.id,
            scope_name="personal",
            default_relay_type="central_relay",
            enable_edge_relay=False,
            enable_secure_channel=False,
        )
        session.add(scope)

    # Update fields
    if update.enable_edge_relay is not None:
        scope.enable_edge_relay = update.enable_edge_relay
    if update.enable_secure_channel is not None:
        scope.enable_secure_channel = update.enable_secure_channel

    await session.commit()
    await session.refresh(scope)

    logger.info(
        "Updated personal scope: user=%s edge=%s secure=%s",
        current_user.id,
        scope.enable_edge_relay,
        scope.enable_secure_channel,
    )

    return PersonalScopeResponse(
        user_id=str(scope.user_id),
        scope_name=scope.scope_name,
        default_relay_type=scope.default_relay_type,
        enable_edge_relay=scope.enable_edge_relay,
        enable_secure_channel=scope.enable_secure_channel,
        created_at=scope.created_at,
        updated_at=scope.updated_at,
    )


@router.post("/edge-relay/register", response_model=PersonalEdgeRelayResponse, status_code=status.HTTP_201_CREATED)
async def register_edge_relay(
    register_req: PersonalEdgeRelayRegister,
    current_user: Annotated[User, Depends(authenticate)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """Register a personal edge relay."""
    try:
        relay = await register_personal_edge_relay(
            session,
            user_id=current_user.id,
            node_name=register_req.node_name,
            local_ip=register_req.local_ip,
            subnet=register_req.subnet,
            gateway=register_req.gateway,
            capabilities=register_req.capabilities,
            max_capacity=register_req.max_capacity,
        )
        await session.commit()
        await session.refresh(relay)

        return PersonalEdgeRelayResponse(
            id=str(relay.id),
            node_name=relay.node_name,
            status=relay.status,
            current_load=relay.current_load,
            queue_depth=relay.queue_depth,
            avg_latency_ms=relay.avg_latency_ms,
            success_rate=relay.success_rate,
            is_healthy=relay.is_healthy,
            network_info=relay.network_info,
            last_heartbeat_at=relay.last_heartbeat_at,
            created_at=relay.created_at,
        )
    except DomainException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/edge-relay/heartbeat", response_model=PersonalEdgeRelayResponse)
async def edge_relay_heartbeat(
    heartbeat: PersonalEdgeRelayHeartbeat,
    current_user: Annotated[User, Depends(authenticate)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """Process heartbeat from personal edge relay."""
    try:
        relay = await process_edge_heartbeat(
            session,
            user_id=current_user.id,
            node_name=heartbeat.node_name,
            current_load=heartbeat.current_load,
            queue_depth=heartbeat.queue_depth,
            avg_latency_ms=heartbeat.avg_latency_ms,
            success_rate=heartbeat.success_rate,
        )
        await session.commit()
        await session.refresh(relay)

        return PersonalEdgeRelayResponse(
            id=str(relay.id),
            node_name=relay.node_name,
            status=relay.status,
            current_load=relay.current_load,
            queue_depth=relay.queue_depth,
            avg_latency_ms=relay.avg_latency_ms,
            success_rate=relay.success_rate,
            is_healthy=relay.is_healthy,
            network_info=relay.network_info,
            last_heartbeat_at=relay.last_heartbeat_at,
            created_at=relay.created_at,
        )
    except DomainException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/edge-relays", response_model=list[PersonalEdgeRelayResponse])
async def list_edge_relays(
    current_user: Annotated[User, Depends(authenticate)],
    session: Annotated[AsyncSession, Depends(get_session)],
    only_healthy: bool = False,
):
    """List all personal edge relays for current user."""
    relays = await get_personal_edge_relays(
        session,
        user_id=current_user.id,
        only_healthy=only_healthy,
    )

    return [
        PersonalEdgeRelayResponse(
            id=str(relay.id),
            node_name=relay.node_name,
            status=relay.status,
            current_load=relay.current_load,
            queue_depth=relay.queue_depth,
            avg_latency_ms=relay.avg_latency_ms,
            success_rate=relay.success_rate,
            is_healthy=relay.is_healthy,
            network_info=relay.network_info,
            last_heartbeat_at=relay.last_heartbeat_at,
            created_at=relay.created_at,
        )
        for relay in relays
    ]
