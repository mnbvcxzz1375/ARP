"""Approval API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ApprovalResponse(BaseModel):
    id: UUID = Field(description="Approval UUID.")
    task_id: UUID = Field(description="Task UUID requiring approval.")
    agent_id: UUID | None = Field(description="Agent UUID that owns the approval.")
    status: str = Field(description="Approval status.")
    risk_level: str = Field(description="Risk level assigned to the action.")
    action_kind: str = Field(description="Kind of action requiring approval.")
    action_preview: str | None = Field(description="Human-readable action preview.")
    reason: str | None = Field(description="Decision or rejection reason.")
    expires_at: datetime | None = Field(description="Approval expiry time.")
    decided_at: datetime | None = Field(description="Decision time, if decided.")
    created_at: datetime = Field(description="Approval creation time.")
    updated_at: datetime = Field(description="Last approval update time.")

    model_config = {"from_attributes": True}


class ApprovalListResponse(BaseModel):
    approvals: list[ApprovalResponse] = Field(description="Approvals in this page.")
    total: int = Field(description="Total matching approvals.")
