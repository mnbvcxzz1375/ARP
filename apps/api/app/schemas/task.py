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

    # E2EE (M2): the sender's envelope marker fields. When present they are
    # merged into Message.content verbatim — the sender's envelope is the
    # single source of truth for the marker block; the platform never
    # constructs, rewrites, or infers them.
    security: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Envelope security marker block {mode, encryption, key_id, nonce}. "
            "Copied verbatim into the task message content and into the delivered "
            "WS payload; the platform never constructs or rewrites it."
        ),
    )
    encrypted_payload: str | None = Field(
        default=None,
        description="Base64 ciphertext. Stored verbatim in Message.content when security is present.",
    )
    aad: dict[str, Any] | None = Field(
        default=None,
        description="Additional authenticated data object, stored verbatim with the ciphertext.",
    )

    # Timeliness and routing hints (Phase 14)
    timeliness_mode: str | None = Field(
        default="normal",
        description="Timeliness mode: realtime, interactive, normal, batch, or durable. Affects routing decisions.",
    )
    ttl_seconds: int | None = Field(
        default=None,
        description="Time-to-live in seconds. Task expires if not delivered within this time.",
    )
    deadline_at: datetime | None = Field(
        default=None,
        description="Absolute deadline timestamp. Task expires if not completed by this time.",
    )
    priority: int | None = Field(
        default=None,
        ge=0,
        le=10,
        description="Task priority (1=highest, 10=lowest). Default is 0 (normal).",
    )
    max_retry_count: int | None = Field(
        default=None,
        ge=0,
        description="Maximum number of delivery retries. If omitted, uses system default.",
    )
    retry_policy: dict[str, Any] | None = Field(
        default=None,
        description="Custom retry policy (backoff strategy, retry intervals, etc.).",
    )
    route_policy_hint: str | None = Field(
        default=None,
        max_length=64,
        description="Routing policy hint (e.g., 'prefer_local', 'require_secure', 'cost_optimized').",
    )


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
