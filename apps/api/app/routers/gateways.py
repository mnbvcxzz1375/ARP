"""Egress gateway CRUD router: the /v1/egress/gateways contract.

A gateway is a policy entity (domains it may reach, secret-store
reference, rate/cache/cost config) that agents are pointed at via
agents.egress_gateway_id. Reads require admin:read; mutations require
the super_admin:write permission plus step-up auth and CSRF, matching
the dedicated-channel endpoints.

List semantics: the catalog is an admin-curated policy set expected in
the low dozens, so the list ships all rows (newest first) and the
console narrows by scope/type client-side.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies.auth import CurrentSession
from app.dependencies.csrf import require_csrf
from app.dependencies.rbac import require_high_risk, require_permission
from app.exceptions import DomainException
from app.models.egress_gateway import EgressGateway
from app.protocol.constants import ErrorCode
from app.schemas.egress_gateway import (
    EgressGatewayCreate,
    EgressGatewayListResponse,
    EgressGatewayResponse,
    EgressGatewayUpdate,
)
from app.services.audit_service import write_audit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/egress/gateways", tags=["egress-gateways"])


def _not_found() -> DomainException:
    return DomainException(
        ErrorCode.INVALID_REQUEST,
        "Egress gateway not found",
        status_code=404,
    )


async def _load_gateway(session: AsyncSession, gateway_id: UUID) -> EgressGateway:
    gateway = await session.get(EgressGateway, gateway_id)
    if gateway is None:
        raise _not_found()
    return gateway


def _to_response(gateway: EgressGateway) -> EgressGatewayResponse:
    return EgressGatewayResponse(
        id=gateway.id,
        scope_id=gateway.scope_id,
        gateway_name=gateway.gateway_name,
        gateway_type=gateway.gateway_type,
        domain_allowlist=gateway.domain_allowlist or [],
        secret_store_ref=gateway.secret_store_ref,
        rate_limit_config=gateway.rate_limit_config,
        cache_config=gateway.cache_config,
        cost_tracking=gateway.cost_tracking,
        enabled=gateway.enabled,
        created_at=gateway.created_at,
        updated_at=gateway.updated_at,
    )


@router.get("", response_model=EgressGatewayListResponse)
async def list_egress_gateways(
    current_session: CurrentSession,
    _rbac: None = Depends(require_permission("admin:read")),
    session: AsyncSession = Depends(get_session),
):
    """List every egress gateway (admin read).

    Returns all rows newest-first; the console filters client-side.
    Audit: records reads of gateway configuration metadata.
    """
    result = await session.execute(
        select(EgressGateway).order_by(EgressGateway.created_at.desc())
    )
    gateways = list(result.scalars().all())
    await write_audit(
        session,
        actor_type="admin",
        actor_id=str(current_session.user_id),
        action="egress_gateway.list",
        resource_type="egress_gateway",
        details={"count": len(gateways)},
    )
    await session.commit()
    return EgressGatewayListResponse(
        gateways=[_to_response(g) for g in gateways],
        total=len(gateways),
    )


@router.get("/{gateway_id}", response_model=EgressGatewayResponse)
async def get_egress_gateway(
    gateway_id: UUID,
    current_session: CurrentSession,
    _rbac: None = Depends(require_permission("admin:read")),
    session: AsyncSession = Depends(get_session),
):
    """Fetch one egress gateway by ID (admin read)."""
    gateway = await _load_gateway(session, gateway_id)
    await session.commit()
    return _to_response(gateway)


@router.post("", response_model=EgressGatewayResponse, status_code=201)
async def create_egress_gateway(
    body: EgressGatewayCreate,
    current_session: CurrentSession,
    response: Response,
    _rbac: None = Depends(require_high_risk("super_admin:write")),
    _csrf: None = Depends(require_csrf),
    session: AsyncSession = Depends(get_session),
):
    """Create an egress gateway (super admin, step-up + CSRF).

    The secret_store_ref is a reference (env:VAR_NAME), never a secret
    value; the runtime resolves it server-side at request time.
    """
    gateway = EgressGateway(
        scope_id=body.scope_id,
        gateway_name=body.gateway_name,
        gateway_type=body.gateway_type,
        domain_allowlist=body.domain_allowlist or [],
        secret_store_ref=body.secret_store_ref,
        rate_limit_config=body.rate_limit_config,
        cache_config=body.cache_config,
        cost_tracking=body.cost_tracking,
        enabled=True,
    )
    session.add(gateway)
    await session.flush()
    await write_audit(
        session,
        actor_type="admin",
        actor_id=str(current_session.user_id),
        action="egress_gateway.create",
        resource_type="egress_gateway",
        resource_id=str(gateway.id),
        details={"gateway_name": gateway.gateway_name, "gateway_type": gateway.gateway_type},
    )
    await session.commit()
    await session.refresh(gateway)
    logger.info(
        "Egress gateway created: %s (%s)",
        gateway.gateway_name,
        gateway.gateway_type,
    )
    response.status_code = 201
    return _to_response(gateway)


@router.patch("/{gateway_id}", response_model=EgressGatewayResponse)
async def update_egress_gateway(
    gateway_id: UUID,
    body: EgressGatewayUpdate,
    current_session: CurrentSession,
    _rbac: None = Depends(require_high_risk("super_admin:write")),
    _csrf: None = Depends(require_csrf),
    session: AsyncSession = Depends(get_session),
):
    """Partially update an egress gateway (super admin, step-up + CSRF)."""
    gateway = await _load_gateway(session, gateway_id)
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(gateway, field, value)
    await session.flush()
    await write_audit(
        session,
        actor_type="admin",
        actor_id=str(current_session.user_id),
        action="egress_gateway.update",
        resource_type="egress_gateway",
        resource_id=str(gateway.id),
        details={"changed_fields": sorted(updates)},
    )
    await session.commit()
    # onupdate columns are expired post-flush; refresh before mapping so
    # _to_response never triggers a lazy load.
    await session.refresh(gateway)
    return _to_response(gateway)


@router.delete("/{gateway_id}", status_code=204)
async def delete_egress_gateway(
    gateway_id: UUID,
    current_session: CurrentSession,
    _rbac: None = Depends(require_high_risk("super_admin:write")),
    _csrf: None = Depends(require_csrf),
    session: AsyncSession = Depends(get_session),
):
    """Delete an egress gateway (super admin, step-up + CSRF).

    Agents referencing the gateway keep working: agents.egress_gateway_id
    is ON DELETE SET NULL, so their egress falls back to direct routing.
    """
    gateway = await _load_gateway(session, gateway_id)
    await session.delete(gateway)
    await write_audit(
        session,
        actor_type="admin",
        actor_id=str(current_session.user_id),
        action="egress_gateway.delete",
        resource_type="egress_gateway",
        resource_id=str(gateway.id),
        details={"gateway_name": gateway.gateway_name},
    )
    await session.commit()
    return Response(status_code=204)
