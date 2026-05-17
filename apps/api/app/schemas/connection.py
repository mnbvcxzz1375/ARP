"""Connection API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ConnectionRequestRequest(BaseModel):
    to_agent_number: str = Field(..., description="Agent number of the target agent")
    reason: str | None = Field(None, max_length=1024, description="Reason for requesting the connection")
    requested_capabilities: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Capabilities requested from the target agent.",
    )
    requested_security_modes: list[str] = Field(
        default_factory=list,
        max_length=5,
        description="Security modes acceptable to the requesting agent.",
    )


class ConnectionAcceptRequest(BaseModel):
    allowed_capabilities: list[str] | None = Field(
        default_factory=list,
        max_length=20,
        description="Capabilities granted to the requester.",
    )
    preferred_security_mode: str | None = Field(
        None,
        max_length=32,
        description="Negotiated security mode for this connection.",
    )
    expires_at: datetime | None = Field(None, description="When this connection grant expires")


class ConnectionRejectRequest(BaseModel):
    reason: str | None = Field(None, max_length=256, description="Optional rejection reason.")


class ConnectionResponse(BaseModel):
    id: UUID = Field(description="Connection UUID.")
    from_agent_id: UUID = Field(description="Requester agent UUID.")
    to_agent_id: UUID = Field(description="Target agent UUID.")
    status: str = Field(description="Connection lifecycle status.")
    allowed_capabilities: list[str] | None = Field(description="Capabilities granted by the target agent.")
    preferred_security_mode: str | None = Field(description="Negotiated or preferred security mode.")
    expires_at: datetime | None = Field(description="Optional connection expiry time.")
    reason: str | None = Field(description="Request or rejection reason.")
    created_at: datetime = Field(description="Connection creation time.")
    updated_at: datetime = Field(description="Last connection update time.")

    model_config = {"from_attributes": True}


class ConnectionListResponse(BaseModel):
    connections: list[ConnectionResponse] = Field(description="Connections in this page.")
    total: int = Field(description="Total matching connections.")
