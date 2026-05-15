"""Approval API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ApprovalResponse(BaseModel):
    id: UUID
    task_id: UUID
    agent_id: UUID | None
    status: str
    risk_level: str
    action_kind: str
    action_preview: str | None
    reason: str | None
    expires_at: datetime | None
    decided_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApprovalListResponse(BaseModel):
    approvals: list[ApprovalResponse]
    total: int