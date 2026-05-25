import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import NetworkScope, NetworkZone, User
from app.exceptions import DomainException
from app.protocol.constants import ErrorCode
from app.dependencies.auth import CurrentSession
from app.dependencies.rbac import require_permission, require_high_risk
from app.services.rbac_service import PERM_ADMIN_READ, PERM_SUPER_ADMIN_WRITE
from app.services import network_topology_service
from app.services.audit_service import write_audit
from app.schemas.network_topology import (
    NetworkScopeCreateRequest,
    NetworkScopeUpdateRequest,
    NetworkScopeListItem,
    NetworkScopeListResponse,
    NetworkScopeDetailResponse,
    NetworkZoneCreateRequest,
    NetworkZoneUpdateRequest,
    NetworkZoneListItem,
    NetworkZoneListResponse,
    NetworkZoneDetailResponse,
)

router = APIRouter(prefix="/v1/dashboard/admin/network", tags=["dashboard-admin"])


VALID_SCOPE_TYPES = {"personal", "enterprise"}
VALID_ZONE_TYPES = {"local", "regional", "global", "local_edge", "central", "cloud", "egress"}


def _parse_uuid(value: str, field_name: str = "ID") -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise DomainException(ErrorCode.INVALID_REQUEST, f"Invalid {field_name} format", status_code=422)


def _scope_detail(scope: NetworkScope) -> NetworkScopeDetailResponse:
    username = scope.user.username if scope.user else None
    return NetworkScopeDetailResponse(
        scope_id=str(scope.id),
        scope_name=scope.scope_name,
        scope_type=scope.scope_type,
        user_id=str(scope.user_id),
        username=username,
        network_cidr=scope.network_cidr,
        agent_ids=[str(aid) for aid in (scope.agent_ids or [])],
        zone_ids=[str(zid) for zid in (scope.zone_ids or [])],
        created_at=scope.created_at,
        updated_at=scope.updated_at,
    )


def _zone_detail(zone: NetworkZone) -> NetworkZoneDetailResponse:
    scope_name = zone.scope.scope_name if zone.scope else None
    return NetworkZoneDetailResponse(
        zone_id=str(zone.id),
        zone_name=zone.zone_name,
        zone_type=zone.zone_type,
        scope_id=str(zone.scope_id),
        scope_name=scope_name,
        parent_zone_id=str(zone.parent_zone_id) if zone.parent_zone_id else None,
        relay_node_ids=[str(rid) for rid in (zone.relay_node_ids or [])],
        zone_metadata=zone.zone_metadata or {},
        created_at=zone.created_at,
        updated_at=zone.updated_at,
    )


# ── Scope read ───────────────────────────────────────────────────


@router.get("/scopes", response_model=NetworkScopeListResponse)
async def list_network_scopes(
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    scope_type: str | None = None,
    _: None = Depends(require_permission(PERM_ADMIN_READ)),
):
    """List all network scopes."""
    stmt = select(NetworkScope)
    if scope_type:
        stmt = stmt.where(NetworkScope.scope_type == scope_type)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(NetworkScope.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    scopes = list(result.scalars().all())

    items = []
    for s in scopes:
        username = s.user.username if s.user else None
        items.append(NetworkScopeListItem(
            scope_id=str(s.id),
            scope_name=s.scope_name,
            scope_type=s.scope_type,
            user_id=str(s.user_id),
            username=username,
            network_cidr=s.network_cidr,
            agent_count=len(s.agent_ids) if s.agent_ids else 0,
            zone_count=len(s.zone_ids) if s.zone_ids else 0,
            created_at=s.created_at,
            updated_at=s.updated_at,
        ))

    return NetworkScopeListResponse(scopes=items, total=total, offset=offset, limit=limit)


@router.get("/scopes/{scope_id}", response_model=NetworkScopeDetailResponse)
async def get_network_scope(
    scope_id: str,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_permission(PERM_ADMIN_READ)),
):
    """Get a single network scope."""
    scope = await network_topology_service.get_network_scope(
        session, scope_id=_parse_uuid(scope_id, "scope ID")
    )
    return _scope_detail(scope)


# ── Scope CRUD ───────────────────────────────────────────────────


@router.post("/scopes", response_model=NetworkScopeDetailResponse, status_code=201)
async def create_network_scope(
    body: NetworkScopeCreateRequest,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_high_risk(PERM_SUPER_ADMIN_WRITE)),
):
    """Create a new network scope."""
    if body.scope_type not in VALID_SCOPE_TYPES:
        raise DomainException(
            ErrorCode.INVALID_REQUEST,
            f"Invalid scope_type '{body.scope_type}'. Must be one of: {', '.join(sorted(VALID_SCOPE_TYPES))}",
            status_code=400,
        )

    scope = await network_topology_service.create_network_scope(
        session,
        user_id=_parse_uuid(body.user_id, "user ID"),
        scope_name=body.scope_name,
        scope_type=body.scope_type,
        network_cidr=body.network_cidr,
        agent_ids=[_parse_uuid(a, "agent ID") for a in (body.agent_ids or [])] if body.agent_ids else None,
        zone_ids=[_parse_uuid(z, "zone ID") for z in (body.zone_ids or [])] if body.zone_ids else None,
    )
    await write_audit(
        session,
        actor_type="admin",
        actor_id=str(ds.user_id),
        action="network_scope.create",
        resource_type="network_scope",
        resource_id=str(scope.id),
        details={"scope_name": body.scope_name, "scope_type": body.scope_type},
    )
    await session.commit()
    await session.refresh(scope)
    return _scope_detail(scope)


@router.put("/scopes/{scope_id}", response_model=NetworkScopeDetailResponse)
async def update_network_scope(
    scope_id: str,
    body: NetworkScopeUpdateRequest,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_high_risk(PERM_SUPER_ADMIN_WRITE)),
):
    """Update a network scope."""
    scope = await network_topology_service.update_network_scope(
        session,
        scope_id=_parse_uuid(scope_id, "scope ID"),
        scope_name=body.scope_name,
        network_cidr=body.network_cidr,
        agent_ids=[_parse_uuid(a, "agent ID") for a in body.agent_ids] if body.agent_ids is not None else None,
        zone_ids=[_parse_uuid(z, "zone ID") for z in body.zone_ids] if body.zone_ids is not None else None,
    )
    await write_audit(
        session,
        actor_type="admin",
        actor_id=str(ds.user_id),
        action="network_scope.update",
        resource_type="network_scope",
        resource_id=str(scope.id),
        details={"updated_fields": [k for k, v in body.model_dump().items() if v is not None]},
    )
    await session.commit()
    await session.refresh(scope)
    return _scope_detail(scope)


@router.delete("/scopes/{scope_id}", status_code=204)
async def delete_network_scope(
    scope_id: str,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_high_risk(PERM_SUPER_ADMIN_WRITE)),
):
    """Delete a network scope. Child zones cascade per model definition (delete-orphan)."""
    scope_uuid = _parse_uuid(scope_id, "scope ID")
    scope = await network_topology_service.get_network_scope(session, scope_id=scope_uuid)
    await write_audit(
        session,
        actor_type="admin",
        actor_id=str(ds.user_id),
        action="network_scope.delete",
        resource_type="network_scope",
        resource_id=scope_id,
        details={"scope_name": scope.scope_name},
    )
    await network_topology_service.delete_network_scope(session, scope_id=scope_uuid)
    await session.commit()


# ── Zone read ────────────────────────────────────────────────────


@router.get("/zones", response_model=NetworkZoneListResponse)
async def list_network_zones(
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    zone_type: str | None = None,
    scope_id_filter: str | None = None,
    _: None = Depends(require_permission(PERM_ADMIN_READ)),
):
    """List all network zones."""
    stmt = select(NetworkZone)
    if zone_type:
        stmt = stmt.where(NetworkZone.zone_type == zone_type)
    if scope_id_filter:
        stmt = stmt.where(NetworkZone.scope_id == _parse_uuid(scope_id_filter, "scope_id_filter"))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(NetworkZone.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    zones = list(result.scalars().all())

    items = []
    for z in zones:
        scope_name = z.scope.scope_name if z.scope else None
        items.append(NetworkZoneListItem(
            zone_id=str(z.id),
            zone_name=z.zone_name,
            zone_type=z.zone_type,
            scope_id=str(z.scope_id),
            scope_name=scope_name,
            parent_zone_id=str(z.parent_zone_id) if z.parent_zone_id else None,
            relay_node_count=len(z.relay_node_ids) if z.relay_node_ids else 0,
            created_at=z.created_at,
            updated_at=z.updated_at,
        ))

    return NetworkZoneListResponse(zones=items, total=total, offset=offset, limit=limit)


@router.get("/zones/{zone_id}", response_model=NetworkZoneDetailResponse)
async def get_network_zone(
    zone_id: str,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_permission(PERM_ADMIN_READ)),
):
    """Get a single network zone."""
    zone = await network_topology_service.get_network_zone(
        session, zone_id=_parse_uuid(zone_id, "zone ID")
    )
    return _zone_detail(zone)


# ── Zone CRUD ────────────────────────────────────────────────────


@router.post("/zones", response_model=NetworkZoneDetailResponse, status_code=201)
async def create_network_zone(
    body: NetworkZoneCreateRequest,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_high_risk(PERM_SUPER_ADMIN_WRITE)),
):
    """Create a new network zone."""
    if body.zone_type not in VALID_ZONE_TYPES:
        raise DomainException(
            ErrorCode.INVALID_REQUEST,
            f"Invalid zone_type '{body.zone_type}'. Must be one of: {', '.join(sorted(VALID_ZONE_TYPES))}",
            status_code=400,
        )

    zone = await network_topology_service.create_network_zone(
        session,
        scope_id=_parse_uuid(body.scope_id, "scope ID"),
        zone_name=body.zone_name,
        zone_type=body.zone_type,
        parent_zone_id=_parse_uuid(body.parent_zone_id, "parent zone ID") if body.parent_zone_id else None,
        relay_node_ids=[_parse_uuid(r, "relay node ID") for r in (body.relay_node_ids or [])] if body.relay_node_ids else None,
        zone_metadata=body.zone_metadata,
    )
    await write_audit(
        session,
        actor_type="admin",
        actor_id=str(ds.user_id),
        action="network_zone.create",
        resource_type="network_zone",
        resource_id=str(zone.id),
        details={"zone_name": body.zone_name, "zone_type": body.zone_type, "scope_id": body.scope_id},
    )
    await session.commit()
    await session.refresh(zone)
    return _zone_detail(zone)


@router.put("/zones/{zone_id}", response_model=NetworkZoneDetailResponse)
async def update_network_zone(
    zone_id: str,
    body: NetworkZoneUpdateRequest,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_high_risk(PERM_SUPER_ADMIN_WRITE)),
):
    """Update a network zone."""
    zone_uuid = _parse_uuid(zone_id, "zone ID")
    zone = await network_topology_service.get_network_zone(session, zone_id=zone_uuid)

    if body.zone_name is not None:
        zone.zone_name = body.zone_name
    if body.parent_zone_id is not None:
        zone.parent_zone_id = _parse_uuid(body.parent_zone_id, "parent zone ID")
    if body.relay_node_ids is not None:
        zone.relay_node_ids = [_parse_uuid(r, "relay node ID") for r in body.relay_node_ids]
    if body.zone_metadata is not None:
        zone.zone_metadata = body.zone_metadata

    await write_audit(
        session,
        actor_type="admin",
        actor_id=str(ds.user_id),
        action="network_zone.update",
        resource_type="network_zone",
        resource_id=str(zone.id),
        details={"updated_fields": [k for k, v in body.model_dump().items() if v is not None]},
    )
    await session.commit()
    await session.refresh(zone)
    return _zone_detail(zone)


@router.delete("/zones/{zone_id}", status_code=204)
async def delete_network_zone(
    zone_id: str,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_high_risk(PERM_SUPER_ADMIN_WRITE)),
):
    """Delete a network zone."""
    zone_uuid = _parse_uuid(zone_id, "zone ID")
    zone = await network_topology_service.get_network_zone(session, zone_id=zone_uuid)
    await write_audit(
        session,
        actor_type="admin",
        actor_id=str(ds.user_id),
        action="network_zone.delete",
        resource_type="network_zone",
        resource_id=zone_id,
        details={"zone_name": zone.zone_name, "scope_id": str(zone.scope_id)},
    )
    await network_topology_service.delete_network_zone(session, zone_id=zone_uuid)
    await session.commit()