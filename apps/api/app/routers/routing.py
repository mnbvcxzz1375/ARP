"""Routing runtime REST API endpoints."""

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.exceptions import DomainException
from app.models.message_delivery_event import MessageDeliveryEvent
from app.models.user import User
from app.models.relay_node import RelayNode
from app.models.route_decision import RouteDecision
from app.models.task import Task
from app.protocol.constants import ErrorCode
from app.services.auth import authenticate
from app.schemas.routing import (
    MessageDeliveryEventListResponse,
    MessageDeliveryEventResponse,
    RegisterRelayNodeRequest,
    RelayNodeHeartbeatRequest,
    RelayNodeListResponse,
    RelayNodeResponse,
    RouteDecisionListResponse,
    RouteDecisionResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1", tags=["routing"])


@router.get("/routes/decisions", response_model=RouteDecisionListResponse)
async def list_route_decisions(
    task_id: str | None = Query(None, description="Filter by task ID"),
    offset: int = Query(0, ge=0, description="Result offset"),
    limit: int = Query(20, ge=1, le=100, description="Page size"),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(authenticate),
) -> RouteDecisionListResponse:
    """List route decisions with optional task filter.

    Only returns decisions for tasks where the user owns either the sender or receiver agent.
    """
    from app.models.agent import Agent

    # Build query with ownership filter
    stmt = (
        select(RouteDecision)
        .join(Task, RouteDecision.task_id == Task.id)
        .join(Agent, (Task.created_by == Agent.id) | (Task.assigned_to == Agent.id))
        .where(Agent.owner_id == user.id)
    )

    if task_id:
        try:
            task_uuid = uuid.UUID(task_id)
            stmt = stmt.where(RouteDecision.task_id == task_uuid)
        except ValueError:
            raise DomainException(
                ErrorCode.INVALID_REQUEST,
                "Invalid task_id format",
                status_code=400,
            )

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    # Get page
    stmt = stmt.order_by(RouteDecision.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    decisions = result.scalars().all()

    return RouteDecisionListResponse(
        decisions=[
            RouteDecisionResponse(
                id=str(d.id),
                task_id=str(d.task_id),
                message_id=d.message_id,
                trace_id=d.trace_id,
                selected_route_type=d.selected_route_type,
                selected_relay_node_id=str(d.selected_relay_node_id) if d.selected_relay_node_id else None,
                candidate_routes=d.candidate_routes,
                rejection_reasons=d.rejection_reasons,
                fallback_from_route=d.fallback_from_route,
                fallback_reason=d.fallback_reason,
                timeliness_mode=d.timeliness_mode,
                risk_level=d.risk_level,
                final_score=d.final_score,
                decision_time_ms=d.decision_time_ms,
                shadow_mode=d.shadow_mode,
                created_at=d.created_at,
            )
            for d in decisions
        ],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/routes/decisions/{route_decision_id}", response_model=RouteDecisionResponse)
async def get_route_decision(
    route_decision_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(authenticate),
) -> RouteDecisionResponse:
    """Get a specific route decision by ID.

    Only returns the decision if the user owns either the sender or receiver agent.
    """
    from app.models.agent import Agent

    try:
        decision_uuid = uuid.UUID(route_decision_id)
    except ValueError:
        raise DomainException(
            ErrorCode.INVALID_REQUEST,
            "Invalid route_decision_id format",
            status_code=400,
        )

    # Query with ownership filter
    result = await session.execute(
        select(RouteDecision)
        .join(Task, RouteDecision.task_id == Task.id)
        .join(Agent, or_(Task.created_by == Agent.id, Task.assigned_to == Agent.id))
        .where(RouteDecision.id == decision_uuid)
        .where(Agent.owner_id == user.id)
        .distinct()
    )
    decision = result.scalar_one_or_none()

    if decision is None:
        raise DomainException(
            ErrorCode.INVALID_REQUEST,
            f"Route decision {route_decision_id} not found",
            status_code=404,
        )

    return RouteDecisionResponse(
        id=str(decision.id),
        task_id=str(decision.task_id),
        message_id=decision.message_id,
        trace_id=decision.trace_id,
        selected_route_type=decision.selected_route_type,
        selected_relay_node_id=str(decision.selected_relay_node_id) if decision.selected_relay_node_id else None,
        candidate_routes=decision.candidate_routes,
        rejection_reasons=decision.rejection_reasons,
        fallback_from_route=decision.fallback_from_route,
        fallback_reason=decision.fallback_reason,
        timeliness_mode=decision.timeliness_mode,
        risk_level=decision.risk_level,
        final_score=decision.final_score,
        decision_time_ms=decision.decision_time_ms,
        shadow_mode=decision.shadow_mode,
        created_at=decision.created_at,
    )


@router.get("/relay-nodes", response_model=RelayNodeListResponse)
async def list_relay_nodes(
    node_type: str | None = Query(None, description="Filter by node type"),
    status: str | None = Query(None, description="Filter by status"),
    offset: int = Query(0, ge=0, description="Result offset"),
    limit: int = Query(20, ge=1, le=100, description="Page size"),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(authenticate),
) -> RelayNodeListResponse:
    """List relay nodes with optional filters."""
    stmt = select(RelayNode)

    if node_type:
        stmt = stmt.where(RelayNode.node_type == node_type)
    if status:
        stmt = stmt.where(RelayNode.status == status)

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    # Get page
    stmt = stmt.order_by(RelayNode.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    nodes = result.scalars().all()

    return RelayNodeListResponse(
        nodes=[
            RelayNodeResponse(
                id=str(n.id),
                node_name=n.node_name,
                node_type=n.node_type,
                status=n.status,
                current_load=n.current_load,
                queue_depth=n.queue_depth,
                avg_latency_ms=n.avg_latency_ms,
                success_rate=n.success_rate,
                capabilities=n.capabilities,
                max_capacity=n.max_capacity,
                region=n.region,
                zone=n.zone,
                last_heartbeat_at=n.last_heartbeat_at,
                extra_metadata=n.extra_metadata,
                enabled=n.enabled,
                created_at=n.created_at,
                updated_at=n.updated_at,
            )
            for n in nodes
        ],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.post("/relay-nodes/register", response_model=RelayNodeResponse, status_code=201)
async def register_relay_node(
    req: RegisterRelayNodeRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(authenticate),
) -> RelayNodeResponse:
    """Register a new relay node.

    Regular users can only register personal_edge nodes.
    Admin users can register any node type.
    """
    # Permission check: only admin can register non-personal_edge nodes
    restricted_node_types = {"central", "regional", "egress", "dedicated"}
    if req.node_type in restricted_node_types and user.role not in {"admin", "super_admin"}:
        raise DomainException(
            ErrorCode.INVALID_REQUEST,
            f"Only admin users can register {req.node_type} relay nodes. Regular users can only register personal_edge nodes.",
            status_code=403,
        )

    # Check if node_name already exists
    result = await session.execute(
        select(RelayNode).where(RelayNode.node_name == req.node_name)
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise DomainException(
            ErrorCode.INVALID_REQUEST,
            f"Relay node with name '{req.node_name}' already exists",
            status_code=409,
        )

    node = RelayNode(
        node_name=req.node_name,
        node_type=req.node_type,
        status="unknown",
        current_load=0.0,
        queue_depth=0,
        capabilities=req.capabilities,
        max_capacity=req.max_capacity,
        region=req.region,
        zone=req.zone,
        metadata=req.metadata,
        enabled=True,
    )
    session.add(node)
    await session.commit()
    await session.refresh(node)

    logger.info("Registered relay node: %s (type=%s)", node.node_name, node.node_type)

    return RelayNodeResponse(
        id=str(node.id),
        node_name=node.node_name,
        node_type=node.node_type,
        status=node.status,
        current_load=node.current_load,
        queue_depth=node.queue_depth,
        avg_latency_ms=node.avg_latency_ms,
        success_rate=node.success_rate,
        capabilities=node.capabilities,
        max_capacity=node.max_capacity,
        region=node.region,
        zone=node.zone,
        last_heartbeat_at=node.last_heartbeat_at,
        extra_metadata=node.extra_metadata,
        enabled=node.enabled,
        created_at=node.created_at,
        updated_at=node.updated_at,
    )


@router.post("/relay-nodes/{relay_node_id}/heartbeat", response_model=RelayNodeResponse)
async def relay_node_heartbeat(
    relay_node_id: str,
    req: RelayNodeHeartbeatRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(authenticate),
) -> RelayNodeResponse:
    """Update relay node health metrics via heartbeat."""
    try:
        node_uuid = uuid.UUID(relay_node_id)
    except ValueError:
        raise DomainException(
            ErrorCode.INVALID_REQUEST,
            "Invalid relay_node_id format",
            status_code=400,
        )

    result = await session.execute(
        select(RelayNode).where(RelayNode.id == node_uuid)
    )
    node = result.scalar_one_or_none()

    if node is None:
        raise DomainException(
            ErrorCode.INVALID_REQUEST,
            f"Relay node {relay_node_id} not found",
            status_code=404,
        )

    # Update metrics
    node.current_load = req.current_load
    node.queue_depth = req.queue_depth
    node.avg_latency_ms = req.avg_latency_ms
    node.success_rate = req.success_rate
    node.last_heartbeat_at = datetime.now(UTC)

    # Update status based on metrics
    if req.current_load < 0.7 and req.queue_depth < 100 and (req.success_rate or 1.0) > 0.9:
        node.status = "healthy"
    elif req.current_load < 0.9 and req.queue_depth < 500 and (req.success_rate or 1.0) > 0.7:
        node.status = "degraded"
    else:
        node.status = "down"

    await session.commit()
    await session.refresh(node)

    logger.debug(
        "Relay node heartbeat: %s status=%s load=%.2f queue=%d",
        node.node_name,
        node.status,
        node.current_load,
        node.queue_depth,
    )

    return RelayNodeResponse(
        id=str(node.id),
        node_name=node.node_name,
        node_type=node.node_type,
        status=node.status,
        current_load=node.current_load,
        queue_depth=node.queue_depth,
        avg_latency_ms=node.avg_latency_ms,
        success_rate=node.success_rate,
        capabilities=node.capabilities,
        max_capacity=node.max_capacity,
        region=node.region,
        zone=node.zone,
        last_heartbeat_at=node.last_heartbeat_at,
        extra_metadata=node.extra_metadata,
        enabled=node.enabled,
        created_at=node.created_at,
        updated_at=node.updated_at,
    )


@router.get("/tasks/{task_id}/delivery-events", response_model=MessageDeliveryEventListResponse)
async def list_task_delivery_events(
    task_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(authenticate),
) -> MessageDeliveryEventListResponse:
    """List delivery events for a specific task (delivery timeline).

    Only returns events if the user owns either the sender or receiver agent.
    """
    from app.models.agent import Agent

    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError:
        raise DomainException(
            ErrorCode.INVALID_REQUEST,
            "Invalid task_id format",
            status_code=400,
        )

    # Verify task exists and user has ownership
    # Check if user owns either the sender or receiver agent
    task_result = await session.execute(
        select(Task).where(Task.id == task_uuid)
    )
    task = task_result.scalar_one_or_none()
    if task is None:
        raise DomainException(
            ErrorCode.TASK_NOT_FOUND,
            f"Task {task_id} not found",
            status_code=404,
        )

    # Verify ownership through agents
    agent_result = await session.execute(
        select(Agent)
        .where(or_(Agent.id == task.created_by, Agent.id == task.assigned_to))
        .where(Agent.owner_id == user.id)
    )
    if agent_result.first() is None:
        raise DomainException(
            ErrorCode.TASK_NOT_FOUND,
            f"Task {task_id} not found",
            status_code=404,
        )

    # Get delivery events
    result = await session.execute(
        select(MessageDeliveryEvent)
        .where(MessageDeliveryEvent.task_id == task_uuid)
        .order_by(MessageDeliveryEvent.created_at.asc())
    )
    events = result.scalars().all()

    # Count total
    total = len(events)

    return MessageDeliveryEventListResponse(
        events=[
            MessageDeliveryEventResponse(
                id=str(e.id),
                message_id=e.message_id,
                task_id=str(e.task_id),
                event_type=e.event_type,
                route_type=e.route_type,
                relay_node_id=str(e.relay_node_id) if e.relay_node_id else None,
                latency_ms=e.latency_ms,
                queue_wait_ms=e.queue_wait_ms,
                error_code=e.error_code,
                error_message=e.error_message,
                extra_metadata=e.extra_metadata,
                created_at=e.created_at,
            )
            for e in events
        ],
        total=total,
    )


@router.get("/tasks/{task_id}/route-decisions", response_model=RouteDecisionListResponse)
async def list_task_route_decisions(
    task_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(authenticate),
) -> RouteDecisionListResponse:
    """List route decisions for a specific task.

    Only returns decisions if the user owns either the sender or receiver agent.
    """
    from app.models.agent import Agent

    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError:
        raise DomainException(
            ErrorCode.INVALID_REQUEST,
            "Invalid task_id format",
            status_code=400,
        )

    # Verify task exists and user has ownership
    # Check if user owns either the sender or receiver agent
    task_result = await session.execute(
        select(Task).where(Task.id == task_uuid)
    )
    task = task_result.scalar_one_or_none()
    if task is None:
        raise DomainException(
            ErrorCode.TASK_NOT_FOUND,
            f"Task {task_id} not found",
            status_code=404,
        )

    # Verify ownership through agents
    agent_result = await session.execute(
        select(Agent)
        .where(or_(Agent.id == task.created_by, Agent.id == task.assigned_to))
        .where(Agent.owner_id == user.id)
    )
    if agent_result.first() is None:
        raise DomainException(
            ErrorCode.TASK_NOT_FOUND,
            f"Task {task_id} not found",
            status_code=404,
        )

    # Get route decisions
    result = await session.execute(
        select(RouteDecision)
        .where(RouteDecision.task_id == task_uuid)
        .order_by(RouteDecision.created_at.desc())
    )
    decisions = result.scalars().all()

    total = len(decisions)

    return RouteDecisionListResponse(
        decisions=[
            RouteDecisionResponse(
                id=str(d.id),
                task_id=str(d.task_id),
                message_id=d.message_id,
                trace_id=d.trace_id,
                selected_route_type=d.selected_route_type,
                selected_relay_node_id=str(d.selected_relay_node_id) if d.selected_relay_node_id else None,
                candidate_routes=d.candidate_routes,
                rejection_reasons=d.rejection_reasons,
                fallback_from_route=d.fallback_from_route,
                fallback_reason=d.fallback_reason,
                timeliness_mode=d.timeliness_mode,
                risk_level=d.risk_level,
                final_score=d.final_score,
                decision_time_ms=d.decision_time_ms,
                shadow_mode=d.shadow_mode,
                created_at=d.created_at,
            )
            for d in decisions
        ],
        total=total,
        offset=0,
        limit=total,
    )
