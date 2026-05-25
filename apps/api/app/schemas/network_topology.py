from pydantic import BaseModel, Field
from datetime import datetime


# ── Create / Update request schemas ──────────────────────────────


class NetworkScopeCreateRequest(BaseModel):
    user_id: str = Field(..., description="Owner user ID")
    scope_name: str = Field(..., min_length=1, max_length=128)
    scope_type: str = Field(..., description="Must be 'personal' or 'enterprise'")
    network_cidr: str | None = None
    agent_ids: list[str] | None = None
    zone_ids: list[str] | None = None


class NetworkScopeUpdateRequest(BaseModel):
    scope_name: str | None = Field(None, min_length=1, max_length=128)
    network_cidr: str | None = None
    agent_ids: list[str] | None = None
    zone_ids: list[str] | None = None


class NetworkZoneCreateRequest(BaseModel):
    scope_id: str = Field(..., description="Parent scope ID")
    zone_name: str = Field(..., min_length=1, max_length=128)
    zone_type: str = Field(
        ...,
        description="Must be one of: local, regional, global, local_edge, central, cloud, egress",
    )
    parent_zone_id: str | None = None
    relay_node_ids: list[str] | None = None
    zone_metadata: dict | None = None


class NetworkZoneUpdateRequest(BaseModel):
    zone_name: str | None = Field(None, min_length=1, max_length=128)
    parent_zone_id: str | None = None
    relay_node_ids: list[str] | None = None
    zone_metadata: dict | None = None


# ── Response schemas (existing, preserved) ───────────────────────


class NetworkScopeListItem(BaseModel):
    scope_id: str
    scope_name: str
    scope_type: str
    user_id: str
    username: str | None
    network_cidr: str | None
    agent_count: int
    zone_count: int
    created_at: datetime
    updated_at: datetime


class NetworkScopeListResponse(BaseModel):
    scopes: list[NetworkScopeListItem]
    total: int
    offset: int
    limit: int


class NetworkScopeDetailResponse(BaseModel):
    scope_id: str
    scope_name: str
    scope_type: str
    user_id: str
    username: str | None
    network_cidr: str | None
    agent_ids: list[str]
    zone_ids: list[str]
    created_at: datetime
    updated_at: datetime


class NetworkZoneListItem(BaseModel):
    zone_id: str
    zone_name: str
    zone_type: str
    scope_id: str
    scope_name: str | None
    parent_zone_id: str | None
    relay_node_count: int
    created_at: datetime
    updated_at: datetime


class NetworkZoneListResponse(BaseModel):
    zones: list[NetworkZoneListItem]
    total: int
    offset: int
    limit: int


class NetworkZoneDetailResponse(BaseModel):
    zone_id: str
    zone_name: str
    zone_type: str
    scope_id: str
    scope_name: str | None
    parent_zone_id: str | None
    relay_node_ids: list[str]
    zone_metadata: dict
    created_at: datetime
    updated_at: datetime
