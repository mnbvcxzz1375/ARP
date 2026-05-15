"""Connection API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ConnectionRequestRequest(BaseModel):
    to_agent_number: str = Field(..., description="Agent number of the target agent")
    reason: str | None = Field(None, max_length=1024, description="Reason for requesting the connection")
    requested_capabilities: list[str] = Field(default_factory=list, max_length=20)
    requested_security_modes: list[str] = Field(default_factory=list, max_length=5)


class ConnectionAcceptRequest(BaseModel):
    allowed_capabilities: list[str] | None = Field(default_factory=list, max_length=20)
    preferred_security_mode: str | None = Field(None, max_length=32)
    expires_at: datetime | None = Field(None, description="When this connection grant expires")


class ConnectionRejectRequest(BaseModel):
    reason: str | None = Field(None, max_length=256)


class ConnectionResponse(BaseModel):
    id: UUID
    from_agent_id: UUID
    to_agent_id: UUID
    status: str
    allowed_capabilities: list[str] | None
    preferred_security_mode: str | None
    expires_at: datetime | None
    reason: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConnectionListResponse(BaseModel):
    connections: list[ConnectionResponse]
    total: int