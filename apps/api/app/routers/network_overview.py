"""Network Overview router: network topology statistics for dashboard."""

import logging
from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies.auth import CurrentSession
from app.dependencies.rbac import require_permission
from app.models.network_scope import NetworkScope
from app.models.network_zone import NetworkZone
from app.models.route_policy import RoutePolicy
from app.schemas.network_overview import NetworkOverviewResponse, NetworkOverviewStats

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/dashboard", tags=["dashboard"])


@router.get("/network/overview", response_model=NetworkOverviewResponse)
async def get_user_network_overview(
    current_session: CurrentSession = None,
    session: AsyncSession = Depends(get_session),
):
    """Get network overview statistics for the current user.

    Returns statistics for scopes, zones, and policies owned by the user.
    """
    # Count user's scopes
    scope_count_result = await session.execute(
        select(func.count()).select_from(NetworkScope).where(NetworkScope.user_id == current_session.user_id)
    )
    total_scopes = scope_count_result.scalar_one()

    # Count user's zones (via scopes)
    zone_count_result = await session.execute(
        select(func.count())
        .select_from(NetworkZone)
        .join(NetworkScope, NetworkZone.scope_id == NetworkScope.id)
        .where(NetworkScope.user_id == current_session.user_id)
    )
    total_zones = zone_count_result.scalar_one()

    # Count user's policies (via scopes)
    policy_count_result = await session.execute(
        select(func.count())
        .select_from(RoutePolicy)
        .join(NetworkScope, RoutePolicy.scope_id == NetworkScope.id)
        .where(NetworkScope.user_id == current_session.user_id)
    )
    total_policies = policy_count_result.scalar_one()

    # Count active policies
    active_policy_count_result = await session.execute(
        select(func.count())
        .select_from(RoutePolicy)
        .join(NetworkScope, RoutePolicy.scope_id == NetworkScope.id)
        .where(NetworkScope.user_id == current_session.user_id)
        .where(RoutePolicy.enabled == True)  # noqa: E712
    )
    active_policies = active_policy_count_result.scalar_one()

    # Get scopes by type
    scopes_result = await session.execute(
        select(NetworkScope.scope_type, func.count())
        .where(NetworkScope.user_id == current_session.user_id)
        .group_by(NetworkScope.scope_type)
    )
    scopes_by_type = {row[0]: row[1] for row in scopes_result.all()}

    # Get zones by type
    zones_result = await session.execute(
        select(NetworkZone.zone_type, func.count())
        .join(NetworkScope, NetworkZone.scope_id == NetworkScope.id)
        .where(NetworkScope.user_id == current_session.user_id)
        .group_by(NetworkZone.zone_type)
    )
    zones_by_type = {row[0]: row[1] for row in zones_result.all()}

    # Get policies by risk level
    policies_result = await session.execute(
        select(RoutePolicy.risk_level, func.count())
        .join(NetworkScope, RoutePolicy.scope_id == NetworkScope.id)
        .where(NetworkScope.user_id == current_session.user_id)
        .where(RoutePolicy.risk_level.isnot(None))
        .group_by(RoutePolicy.risk_level)
    )
    policies_by_risk_level = {row[0]: row[1] for row in policies_result.all()}

    logger.info(
        "User %s retrieved network overview (scopes=%d, zones=%d, policies=%d)",
        current_session.user_id,
        total_scopes,
        total_zones,
        total_policies,
    )

    return NetworkOverviewResponse(
        stats=NetworkOverviewStats(
            total_scopes=total_scopes,
            total_zones=total_zones,
            total_policies=total_policies,
            active_policies=active_policies,
            scopes_by_type=scopes_by_type,
            zones_by_type=zones_by_type,
            policies_by_risk_level=policies_by_risk_level,
        )
    )


@router.get("/admin/network/overview", response_model=NetworkOverviewResponse)
async def get_admin_network_overview(
    current_session: CurrentSession = None,
    _rbac: None = Depends(require_permission("admin:read")),
    session: AsyncSession = Depends(get_session),
):
    """Get network overview statistics for all users (admin only).

    Returns statistics for all scopes, zones, and policies in the system.

    Requires: admin:read permission
    """
    # Count all scopes
    scope_count_result = await session.execute(select(func.count()).select_from(NetworkScope))
    total_scopes = scope_count_result.scalar_one()

    # Count all zones
    zone_count_result = await session.execute(select(func.count()).select_from(NetworkZone))
    total_zones = zone_count_result.scalar_one()

    # Count all policies
    policy_count_result = await session.execute(select(func.count()).select_from(RoutePolicy))
    total_policies = policy_count_result.scalar_one()

    # Count active policies
    active_policy_count_result = await session.execute(
        select(func.count()).select_from(RoutePolicy).where(RoutePolicy.enabled == True)  # noqa: E712
    )
    active_policies = active_policy_count_result.scalar_one()

    # Get scopes by type
    scopes_result = await session.execute(
        select(NetworkScope.scope_type, func.count()).group_by(NetworkScope.scope_type)
    )
    scopes_by_type = {row[0]: row[1] for row in scopes_result.all()}

    # Get zones by type
    zones_result = await session.execute(
        select(NetworkZone.zone_type, func.count()).group_by(NetworkZone.zone_type)
    )
    zones_by_type = {row[0]: row[1] for row in zones_result.all()}

    # Get policies by risk level
    policies_result = await session.execute(
        select(RoutePolicy.risk_level, func.count())
        .where(RoutePolicy.risk_level.isnot(None))
        .group_by(RoutePolicy.risk_level)
    )
    policies_by_risk_level = {row[0]: row[1] for row in policies_result.all()}

    logger.info(
        "Admin %s retrieved network overview (scopes=%d, zones=%d, policies=%d)",
        current_session.user_id,
        total_scopes,
        total_zones,
        total_policies,
    )

    return NetworkOverviewResponse(
        stats=NetworkOverviewStats(
            total_scopes=total_scopes,
            total_zones=total_zones,
            total_policies=total_policies,
            active_policies=active_policies,
            scopes_by_type=scopes_by_type,
            zones_by_type=zones_by_type,
            policies_by_risk_level=policies_by_risk_level,
        )
    )
