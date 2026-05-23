"""Egress Log schemas for API requests and responses."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class EgressLogResponse(BaseModel):
    """Schema for egress log response."""

    id: UUID
    gateway_id: UUID
    task_id: UUID | None
    agent_id: UUID | None
    request_type: str
    target_domain: str
    request_size_bytes: int
    response_size_bytes: int
    status_code: int | None
    latency_ms: int | None
    cost_estimate: float | None
    approval_id: UUID | None
    created_at: datetime

    class Config:
        from_attributes = True


class EgressLogListResponse(BaseModel):
    """Schema for egress log list response."""

    logs: list[EgressLogResponse]
    total: int
