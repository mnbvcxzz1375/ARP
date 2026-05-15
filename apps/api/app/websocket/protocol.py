"""WebSocket protocol helpers for message parsing and validation."""

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.config import get_settings
from app.exceptions import DomainException
from app.protocol.constants import ErrorCode, MessageType


class WSMessage(BaseModel):
    """Standard WebSocket message envelope."""

    type: str
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    payload: dict[str, Any] = Field(default_factory=dict)


class HeartbeatPayload(BaseModel):
    session_id: str | None = None


class SessionResumePayload(BaseModel):
    session_id: str
    last_message_id: str | None = None


def parse_ws_message(data: str | bytes) -> WSMessage:
    if isinstance(data, bytes):
        try:
            data = data.decode("utf-8")
        except UnicodeDecodeError:
            raise DomainException(
                ErrorCode.INVALID_REQUEST,
                "WebSocket message must be valid UTF-8 text.",
                status_code=400,
            )
    try:
        raw = json.loads(data)
    except json.JSONDecodeError as exc:
        raise DomainException(
            ErrorCode.INVALID_REQUEST,
            f"Invalid JSON in WebSocket message: {exc}",
            status_code=400,
        )
    try:
        return WSMessage(**raw)
    except ValidationError as exc:
        raise DomainException(
            ErrorCode.INVALID_REQUEST,
            f"WebSocket message validation failed: {exc}",
            status_code=422,
            details={"errors": exc.errors()},
        )


def validate_event_type(msg: WSMessage, *allowed: MessageType) -> None:
    if msg.type not in {t.value for t in allowed}:
        raise DomainException(
            ErrorCode.UNSUPPORTED_MESSAGE_TYPE,
            f"Unexpected message type: {msg.type}",
            status_code=400,
        )


def check_payload_size(data: str) -> None:
    settings = get_settings()
    if len(data.encode("utf-8")) > settings.max_payload_bytes:
        raise DomainException(
            ErrorCode.MESSAGE_TOO_LARGE,
            f"Message exceeds max payload size ({settings.max_payload_bytes} bytes).",
            status_code=413,
        )


def build_ws_message(
    msg_type: str, payload: dict[str, Any] | None = None
) -> str:
    msg = WSMessage(type=msg_type, payload=payload or {})
    return msg.model_dump_json()


def build_ack(message_id: str) -> str:
    return build_ws_message(MessageType.ACK.value, {"message_id": message_id})


def build_error(code: str, message: str, message_id: str | None = None) -> str:
    payload: dict[str, Any] = {"code": code, "message": message}
    if message_id:
        payload["message_id"] = message_id
    return build_ws_message(MessageType.ERROR.value, payload)