import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CreateTaskRequest(BaseModel):
    assigned_to: str = Field(..., description="Agent number of the target agent")
    from_agent_number: str | None = Field(
        default=None,
        description="Agent number of the sending agent. If omitted, uses the user's first agent.",
    )
    idempotency_key: str | None = Field(default=None, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)


class TaskResponse(BaseModel):
    task_id: str
    idempotency_key: str | None
    created_by: str | None
    assigned_to: str | None
    status: str
    message_id: str | None
    lease_agent_id: str | None
    lease_expires_at: datetime | None
    last_progress_at: datetime | None
    last_heartbeat_at: datetime | None
    result: dict | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = dict(from_attributes=True)


class TaskListResponse(BaseModel):
    tasks: list[TaskResponse]
    total: int
    offset: int
    limit: int


class TaskProgressResponse(BaseModel):
    id: str
    task_id: str
    seq: int
    status: str
    progress_pct: int | None
    message: str | None
    data: dict | None
    created_at: datetime

    model_config = dict(from_attributes=True)


class TaskProgressListResponse(BaseModel):
    entries: list[TaskProgressResponse]
    total: int
