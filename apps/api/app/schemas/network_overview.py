"""Network Overview schemas for dashboard API."""

from pydantic import BaseModel


class NetworkOverviewStats(BaseModel):
    """Network overview statistics."""

    total_scopes: int
    total_zones: int
    total_policies: int
    active_policies: int
    scopes_by_type: dict[str, int]
    zones_by_type: dict[str, int]
    policies_by_risk_level: dict[str, int]


class NetworkOverviewResponse(BaseModel):
    """Network overview response."""

    stats: NetworkOverviewStats
