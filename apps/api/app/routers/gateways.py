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
import re
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies.auth import CurrentSession
from app.dependencies.csrf import require_csrf
from app.dependencies.rbac import require_high_risk, require_permission
from app.exceptions import DomainException
from app.models.agent import Agent
from app.models.egress_gateway import EgressGateway
from app.models.network_scope import NetworkScope
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

# Hostname pattern for allowlist entries: optional leading "*." label,
# then dot-separated labels of 1-63 alphanumeric/hyphen characters (no
# leading/trailing hyphens). "*" alone is also allowed. Entries with a
# scheme, port, path or userinfo are rejected at registration time.
_DOMAIN_LABEL = r"(?!-)[a-zA-Z0-9-]{1,63}(?<!-)"
_DOMAIN_ENTRY_RE = re.compile(rf"^(\*\.)?{_DOMAIN_LABEL}(\.{_DOMAIN_LABEL})*$|^\*$")


def _not_found() -> DomainException:
    return DomainException(
        ErrorCode.INVALID_REQUEST,
        "Egress gateway not found",
        status_code=404,
    )


def _bad_request(message: str) -> DomainException:
    return DomainException(
        ErrorCode.INVALID_REQUEST,
        message,
        status_code=400,
    )


async def _validate_scope_exists(session: AsyncSession, scope_id: UUID) -> None:
    """Registration-time check: a gateway's scope_id must resolve to an
    existing network scope (the policy scope whose network_cidr the
    egress policy decision point filters against)."""
    result = await session.execute(
        select(NetworkScope.id).where(NetworkScope.id == scope_id)
    )
    if result.first() is None:
        raise _bad_request(f"Network scope {scope_id} does not exist")


def _validate_domain_allowlist(entries: list[str]) -> None:
    """Registration-time check: every allowlist entry must be a hostname
    pattern (optionally wildcard-prefixed) or "*". Rejects URLs, ports,
    paths and empty entries so the pattern cannot be smuggled past the
    matching logic."""
    for entry in entries or []:
        if entry is None or entry == "" or _DOMAIN_ENTRY_RE.match(entry) is None:
            raise _bad_request(
                f"Invalid domain_allowlist entry {entry!r}: expected a hostname "
                "pattern like 'api.example.com', '*.example.com' or '*'"
            )


def _validate_secret_store_ref(secret_store_ref: str | None) -> None:
    """Registration-time check: secrets are only ever read from
    environment variables. A ref must be None or 'env:VAR_NAME' with a
    non-empty variable name; anything else (including a literal secret
    value or a vault:// URL) is rejected at registration time."""
    if secret_store_ref is None:
        return
    if not secret_store_ref.startswith("env:"):
        raise _bad_request(
            f"Invalid secret_store_ref {secret_store_ref!r}: only 'env:VAR_NAME' "
            "references are supported (never the secret value itself)"
        )
    var_name = secret_store_ref[len("env:"):].strip()
    if not var_name or any(c.isspace() for c in var_name):
        raise _bad_request(
            f"Invalid secret_store_ref {secret_store_ref!r}: env variable name "
            "must be non-empty and contain no whitespace"
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
        allow_internal_egress=gateway.allow_internal_egress,
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
    Registration-time validation: scope_id must reference an existing
    network scope, domain_allowlist entries must be hostname patterns,
    and secret_store_ref must be env:-prefixed.
    """
    await _validate_scope_exists(session, body.scope_id)
    _validate_domain_allowlist(body.domain_allowlist)
    _validate_secret_store_ref(body.secret_store_ref)

    gateway = EgressGateway(
        scope_id=body.scope_id,
        gateway_name=body.gateway_name,
        gateway_type=body.gateway_type,
        domain_allowlist=body.domain_allowlist or [],
        secret_store_ref=body.secret_store_ref,
        rate_limit_config=body.rate_limit_config,
        cache_config=body.cache_config,
        cost_tracking=body.cost_tracking,
        allow_internal_egress=body.allow_internal_egress,
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
    """Partially update an egress gateway (super admin, step-up + CSRF).

    Mutable policy fields re-run the registration-time validation
    (domain format, secret ref shape) so a later config change cannot
    smuggle an invalid entry past the policy point.
    """
    gateway = await _load_gateway(session, gateway_id)
    updates = body.model_dump(exclude_unset=True)
    if "domain_allowlist" in updates:
        _validate_domain_allowlist(updates["domain_allowlist"])
    if "secret_store_ref" in updates:
        _validate_secret_store_ref(updates["secret_store_ref"])
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

    Deleting a gateway that agents are still bound to would silently
    degrade their egress to no-gateway fail-closed — a hidden policy
    change. Such a delete is rejected with 409; unbind the agents first
    (PATCH /v1/agents/{id}).
    """
    gateway = await _load_gateway(session, gateway_id)

    referenced = await session.execute(
        select(Agent.id).where(Agent.egress_gateway_id == gateway_id).limit(1)
    )
    if referenced.first() is not None:
        raise DomainException(
            ErrorCode.INVALID_STATE,
            f"Egress gateway {gateway_id} is still bound to agents "
            "(agents.egress_gateway_id); unbind them before deleting",
            status_code=409,
        )

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
