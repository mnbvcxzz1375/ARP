"""Route Policy router: manage routing policies for enterprise topology."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies.auth import CurrentSession
from app.dependencies.rbac import require_permission
from app.exceptions import DomainException
from app.models.route_policy import RoutePolicy
from app.protocol.constants import ErrorCode
from app.schemas.route_policy import (
    RoutePolicyCreate,
    RoutePolicyListResponse,
    RoutePolicyResponse,
    RoutePolicyUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/routes/policies", tags=["routing"])


@router.get("", response_model=RoutePolicyListResponse)
async def list_policies(
    current_session: CurrentSession,
    session: AsyncSession = Depends(get_session),
    scope_id: UUID | None = Query(None, description="Filter by scope ID"),
    enabled: bool | None = Query(None, description="Filter by enabled status"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    _rbac: None = Depends(require_permission("policy:read")),
):
    """List route policies with optional filtering.

    Requires: policy:read permission
    """
    query = select(RoutePolicy)

    # Filter by scope if provided
    if scope_id is not None:
        query = query.where(RoutePolicy.scope_id == scope_id)

    # Filter by enabled status if provided
    if enabled is not None:
        query = query.where(RoutePolicy.enabled == enabled)

    # Order by priority (lower number = higher priority)
    query = query.order_by(RoutePolicy.priority.asc(), RoutePolicy.created_at.desc())

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar_one()

    # Apply pagination
    query = query.limit(limit).offset(offset)

    result = await session.execute(query)
    policies = list(result.scalars().all())

    logger.info(
        "User %s listed %d route policies (total=%d, scope_id=%s, enabled=%s)",
        current_session.user_id if current_session else "unknown",
        len(policies),
        total,
        scope_id,
        enabled,
    )

    return RoutePolicyListResponse(
        policies=[RoutePolicyResponse.model_validate(p) for p in policies],
        total=total,
    )


@router.post("", response_model=RoutePolicyResponse, status_code=201)
async def create_policy(
    policy_data: RoutePolicyCreate,
    current_session: CurrentSession = None,
    _rbac: None = Depends(require_permission("policy:manage")),
    session: AsyncSession = Depends(get_session),
):
    """Create a new route policy.

    Requires: policy:manage permission
    """
    # Validate risk level if provided
    if policy_data.risk_level and policy_data.risk_level not in ("low", "medium", "high", "critical"):
        raise DomainException(
            error_code=ErrorCode.INVALID_INPUT,
            message="Invalid risk_level. Must be one of: low, medium, high, critical",
            status_code=400,
        )

    # Create policy
    policy = RoutePolicy(
        policy_name=policy_data.policy_name,
        description=policy_data.description,
        priority=policy_data.priority,
        scope_id=policy_data.scope_id,
        source_zone_id=policy_data.source_zone_id,
        target_zone_id=policy_data.target_zone_id,
        allowed_route_types=policy_data.allowed_route_types,
        denied_route_types=policy_data.denied_route_types,
        require_approval=policy_data.require_approval,
        risk_level=policy_data.risk_level,
        data_boundary_rules=policy_data.data_boundary_rules,
        enabled=policy_data.enabled,
    )

    session.add(policy)
    await session.commit()
    await session.refresh(policy)

    logger.info(
        "User %s created route policy %s (name=%s, priority=%d)",
        current_session.user_id if current_session else "unknown",
        policy.id,
        policy.policy_name,
        policy.priority,
    )

    return RoutePolicyResponse.model_validate(policy)


@router.patch("/{policy_id}", response_model=RoutePolicyResponse)
async def update_policy(
    policy_id: UUID,
    policy_data: RoutePolicyUpdate,
    current_session: CurrentSession = None,
    _rbac: None = Depends(require_permission("policy:manage")),
    session: AsyncSession = Depends(get_session),
):
    """Update an existing route policy.

    Requires: policy:manage permission
    """
    # Get policy
    result = await session.execute(select(RoutePolicy).where(RoutePolicy.id == policy_id))
    policy = result.scalar_one_or_none()

    if not policy:
        raise DomainException(
            error_code=ErrorCode.RESOURCE_NOT_FOUND,
            message=f"Route policy {policy_id} not found",
            status_code=404,
        )

    # Validate risk level if provided
    if policy_data.risk_level and policy_data.risk_level not in ("low", "medium", "high", "critical"):
        raise DomainException(
            error_code=ErrorCode.INVALID_INPUT,
            message="Invalid risk_level. Must be one of: low, medium, high, critical",
            status_code=400,
        )

    # Update fields
    update_data = policy_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(policy, field, value)

    await session.commit()
    await session.refresh(policy)

    logger.info(
        "User %s updated route policy %s (name=%s)",
        current_session.user_id if current_session else "unknown",
        policy.id,
        policy.policy_name,
    )

    return RoutePolicyResponse.model_validate(policy)
