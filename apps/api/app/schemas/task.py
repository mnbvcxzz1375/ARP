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
    idempotency_key: str | None = Field(
        default=None,
        max_length=128,
        description="Optional sender-provided idempotency key for safe retries.",
    )
    payload: dict[str, Any] = Field(default_factory=dict, description="Task payload delivered to the target agent.")


class TaskResponse(BaseModel):
    task_id: str = Field(description="Task UUID.")
    idempotency_key: str | None = Field(description="Sender-provided idempotency key, if any.")
    created_by: str | None = Field(description="Sender agent UUID.")
    assigned_to: str | None = Field(description="Target agent UUID.")
    status: str = Field(description="Task lifecycle status.")
    message_id: str | None = Field(description="Initial task request message id.")
    lease_agent_id: str | None = Field(description="Agent UUID currently holding the task lease.")
    lease_expires_at: datetime | None = Field(description="Current lease expiry time.")
    last_progress_at: datetime | None = Field(description="Last progress update time.")
    last_heartbeat_at: datetime | None = Field(description="Last lease heartbeat time.")
    result: dict | None = Field(description="Task result payload when completed.")
    error_message: str | None = Field(description="Failure or expiry reason.")
    created_at: datetime = Field(description="Task creation time.")
    updated_at: datetime = Field(description="Last task update time.")

    model_config = dict(from_attributes=True)


class TaskListResponse(BaseModel):
    tasks: list[TaskResponse] = Field(description="Tasks in this page.")
    total: int = Field(description="Total matching tasks.")
    offset: int = Field(description="Zero-based result offset.")
    limit: int = Field(description="Requested page size.")


class TaskProgressResponse(BaseModel):
    id: str = Field(description="Progress entry UUID.")
    task_id: str = Field(description="Task UUID.")
    seq: int = Field(description="Monotonic progress sequence number.")
    status: str = Field(description="Progress status label.")
    progress_pct: int | None = Field(description="Optional progress percentage.")
    message: str | None = Field(description="Optional human-readable progress message.")
    data: dict | None = Field(description="Optional machine-readable progress data.")
    created_at: datetime = Field(description="Progress entry creation time.")

    model_config = dict(from_attributes=True)


class TaskProgressListResponse(BaseModel):
    entries: list[TaskProgressResponse] = Field(description="Progress entries in this page.")
    total: int = Field(description="Total matching progress entries.")
