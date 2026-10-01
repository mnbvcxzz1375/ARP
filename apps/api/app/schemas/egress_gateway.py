"""Egress gateway request/response schemas.

Contract for /v1/egress/gateways (enterprise console CRUD). The row
model is app/models/egress_gateway.py: a gateway is a policy entity
(domains it may reach, secret-store reference, rate/cache/cost config)
that agents are pointed at via agents.egress_gateway_id.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

GATEWAY_TYPES = ("api", "model", "github", "deployment", "mcp")


class EgressGatewayCreate(BaseModel):
    """Request body for creating an egress gateway."""

    scope_id: UUID = Field(..., description="Network scope the gateway belongs to")
    gateway_name: str = Field(..., min_length=1, max_length=128)
    gateway_type: str = Field(
        ..., min_length=1, max_length=32, description=f"One of: {', '.join(GATEWAY_TYPES)}"
    )
    domain_allowlist: list[str] = Field(
        default_factory=list,
        description="Domains this gateway may reach. Empty = no restriction "
        "beyond the gateway's own policy.",
    )
    secret_store_ref: str | None = Field(
        None, max_length=256,
        description="Reference to a secret (env:VAR_NAME). NEVER the secret itself.",
    )
    rate_limit_config: dict[str, Any] | None = Field(None, description="Rate limit rules")
    cache_config: dict[str, Any] | None = Field(None, description="Cache TTL and rules")
    cost_tracking: bool = Field(True, description="Track per-gateway cost")


class EgressGatewayUpdate(BaseModel):
    """Request body for partially updating an egress gateway."""

    gateway_name: str | None = Field(None, min_length=1, max_length=128)
    gateway_type: str | None = Field(None, min_length=1, max_length=32)
    domain_allowlist: list[str] | None = None
    secret_store_ref: str | None = Field(None, max_length=256)
    rate_limit_config: dict[str, Any] | None = None
    cache_config: dict[str, Any] | None = None
    cost_tracking: bool | None = None
    enabled: bool | None = None


class EgressGatewayResponse(BaseModel):
    """Single egress gateway response."""

    id: UUID
    scope_id: UUID
    gateway_name: str
    gateway_type: str
    domain_allowlist: list[str]
    secret_store_ref: str | None
    rate_limit_config: dict[str, Any] | None
    cache_config: dict[str, Any] | None
    cost_tracking: bool
    enabled: bool
    created_at: datetime
    updated_at: datetime


class EgressGatewayListResponse(BaseModel):
    """Paginated egress gateway list response."""

    gateways: list[EgressGatewayResponse]
    total: int
