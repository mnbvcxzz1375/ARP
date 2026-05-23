"""Personal mode schemas: simplified UI for individual users."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PersonalScopeResponse(BaseModel):
    """Personal scope configuration response."""

    user_id: str
    scope_name: str
    default_relay_type: str
    enable_edge_relay: bool
    enable_secure_channel: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PersonalScopeUpdate(BaseModel):
    """Update personal scope configuration."""

    enable_edge_relay: bool | None = None
    enable_secure_channel: bool | None = None


class PersonalEdgeRelayRegister(BaseModel):
    """Register a personal edge relay."""

    node_name: str = Field(..., min_length=1, max_length=128)
    local_ip: str | None = None
    subnet: str | None = None
    gateway: str | None = None
    capabilities: list[str] = Field(default_factory=lambda: ["websocket", "task_delivery"])
    max_capacity: int | None = Field(default=100, ge=1)


class PersonalEdgeRelayHeartbeat(BaseModel):
    """Heartbeat from personal edge relay."""

    node_name: str
    current_load: float = Field(default=0.0, ge=0.0, le=1.0)
    queue_depth: int = Field(default=0, ge=0)
    avg_latency_ms: float | None = Field(default=None, ge=0)
    success_rate: float | None = Field(default=None, ge=0.0, le=1.0)


class PersonalEdgeRelayResponse(BaseModel):
    """Personal edge relay information."""

    id: str
    node_name: str
    status: str
    current_load: float
    queue_depth: int
    avg_latency_ms: float | None
    success_rate: float | None
    is_healthy: bool
    network_info: dict
    last_heartbeat_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class PersonalTaskCreate(BaseModel):
    """Create task with personal mode simplified options."""

    assigned_to: int  # Agent number
    task_type: str
    parameters: dict = Field(default_factory=dict)
    idempotency_key: str | None = None

    # Simplified timeliness options
    speed: Literal["fast", "normal", "reliable"] = "normal"
    # fast -> interactive, normal -> normal, reliable -> durable

    # Optional advanced fields
    ttl_seconds: int | None = None
    priority: int = Field(default=5, ge=1, le=10)


# Mapping from personal UI to internal timeliness mode
SPEED_TO_TIMELINESS: dict[str, str] = {
    "fast": "interactive",
    "normal": "normal",
    "reliable": "durable",
}

# Default TTL by speed
SPEED_DEFAULT_TTL: dict[str, int | None] = {
    "fast": 30,  # 30 seconds for fast tasks
    "normal": None,  # No TTL for normal
    "reliable": None,  # No TTL for reliable (will retry)
}

# Default retry count by speed
SPEED_DEFAULT_RETRY: dict[str, int | None] = {
    "fast": 1,  # Fail fast
    "normal": 3,  # Standard retry
    "reliable": 5,  # More retries
}
