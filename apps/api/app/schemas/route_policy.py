"""Route Policy schemas for API requests and responses."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RoutePolicyBase(BaseModel):
    """Base schema for route policy."""

    policy_name: str = Field(..., max_length=128)
    description: str | None = None
    priority: int = Field(default=100, ge=0)
    scope_id: UUID | None = None
    source_zone_id: UUID | None = None
    target_zone_id: UUID | None = None
    allowed_route_types: list[str] | None = None
    denied_route_types: list[str] | None = None
    require_approval: bool = False
    risk_level: str | None = Field(None, pattern="^(low|medium|high|critical)$")
    data_boundary_rules: dict | None = None
    enabled: bool = True


class RoutePolicyCreate(RoutePolicyBase):
    """Schema for creating a route policy."""

    pass


class RoutePolicyUpdate(BaseModel):
    """Schema for updating a route policy."""

    policy_name: str | None = Field(None, max_length=128)
    description: str | None = None
    priority: int | None = Field(None, ge=0)
    scope_id: UUID | None = None
    source_zone_id: UUID | None = None
    target_zone_id: UUID | None = None
    allowed_route_types: list[str] | None = None
    denied_route_types: list[str] | None = None
    require_approval: bool | None = None
    risk_level: str | None = Field(None, pattern="^(low|medium|high|critical)$")
    data_boundary_rules: dict | None = None
    enabled: bool | None = None


class RoutePolicyResponse(RoutePolicyBase):
    """Schema for route policy response."""

    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RoutePolicyListResponse(BaseModel):
    """Schema for route policy list response."""

    policies: list[RoutePolicyResponse]
    total: int
