from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.protocol.constants import MessageType, SecurityMode


class DeliveryOptions(BaseModel):
    requires_ack: bool = True
    idempotency_key: str | None = None
    retry_count: int = Field(default=0, ge=0)

    model_config = ConfigDict(extra="forbid")


class SecurityOptions(BaseModel):
    mode: SecurityMode = SecurityMode.RELAY_VISIBLE
    encryption: str = "none"
    key_id: str | None = None
    nonce: str | None = None

    model_config = ConfigDict(extra="forbid")


class Limits(BaseModel):
    max_duration_seconds: int = Field(default=600, gt=0)
    max_steps: int = Field(default=20, gt=0)
    max_output_bytes: int = Field(default=1_048_576, gt=0)

    model_config = ConfigDict(extra="forbid")


class ContentPart(BaseModel):
    mime: str = "text/plain"
    text: str | None = None
    data: dict[str, Any] | None = None

    model_config = ConfigDict(extra="forbid")


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class ErrorResponse(BaseModel):
    type: Literal["error"] = "error"
    error: ErrorBody

    model_config = ConfigDict(extra="forbid")


class Envelope(BaseModel):
    version: Literal["arp-0.1"] = "arp-0.1"
    message_id: str
    request_id: str | None = None
    session_id: str | None = None
    type: MessageType
    from_agent: str | None = Field(default=None, alias="from")
    to_agent: str | None = Field(default=None, alias="to")
    task_id: str | None = None
    conversation_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    ttl_seconds: int = Field(default=600, gt=0)
    delivery: DeliveryOptions = Field(default_factory=DeliveryOptions)
    security: SecurityOptions = Field(default_factory=SecurityOptions)
    limits: Limits = Field(default_factory=Limits)
    content: list[ContentPart] = Field(default_factory=list)
    encrypted_payload: str | None = None
    aad: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True, extra="forbid", use_enum_values=True)


class TaskMessage(Envelope):
    type: Literal[
        MessageType.TASK_REQUEST,
        MessageType.TASK_ACCEPTED,
        MessageType.TASK_REJECTED,
        MessageType.TASK_PROGRESS,
        MessageType.TASK_HEARTBEAT,
        MessageType.TASK_RESULT,
        MessageType.TASK_FAILED,
        MessageType.TASK_CANCELLED,
    ]


class ConnectionRequest(BaseModel):
    type: Literal[MessageType.CONNECTION_REQUEST] = MessageType.CONNECTION_REQUEST
    from_agent: str = Field(alias="from")
    to_agent: str = Field(alias="to")
    reason: str | None = None
    requested_capabilities: list[str] = Field(default_factory=list)
    requested_security_modes: list[SecurityMode] = Field(default_factory=lambda: [SecurityMode.RELAY_VISIBLE])

    model_config = ConfigDict(populate_by_name=True, extra="forbid", use_enum_values=True)


class ConnectionAccepted(BaseModel):
    type: Literal[MessageType.CONNECTION_ACCEPTED] = MessageType.CONNECTION_ACCEPTED
    from_agent: str = Field(alias="from")
    to_agent: str = Field(alias="to")
    allowed_capabilities: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None
    preferred_security_mode: SecurityMode = SecurityMode.RELAY_VISIBLE

    model_config = ConfigDict(populate_by_name=True, extra="forbid", use_enum_values=True)


class ConnectionRejected(BaseModel):
    type: Literal[MessageType.CONNECTION_REJECTED] = MessageType.CONNECTION_REJECTED
    from_agent: str = Field(alias="from")
    to_agent: str = Field(alias="to")
    reason: str = "not_allowed"

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class ApprovalAction(BaseModel):
    kind: str
    preview: str

    model_config = ConfigDict(extra="forbid")


class ApprovalRequest(BaseModel):
    type: Literal[MessageType.APPROVAL_REQUEST] = MessageType.APPROVAL_REQUEST
    task_id: str
    risk_level: str
    action: ApprovalAction
    reason: str | None = None
    expires_in_seconds: int = Field(default=120, gt=0)

    model_config = ConfigDict(extra="forbid")


class ApprovalAccepted(BaseModel):
    type: Literal[MessageType.APPROVAL_ACCEPTED] = MessageType.APPROVAL_ACCEPTED
    task_id: str

    model_config = ConfigDict(extra="forbid")


class ApprovalRejected(BaseModel):
    type: Literal[MessageType.APPROVAL_REJECTED] = MessageType.APPROVAL_REJECTED
    task_id: str
    reason: str = "user_rejected"

    model_config = ConfigDict(extra="forbid")

