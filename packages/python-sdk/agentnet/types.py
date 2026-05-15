from __future__ import annotations

from enum import StrEnum


class MessageType(StrEnum):
    PRESENCE_HEARTBEAT = "presence.heartbeat"
    CONNECTION_REQUEST = "connection.request"
    CONNECTION_ACCEPTED = "connection.accepted"
    CONNECTION_REJECTED = "connection.rejected"
    SESSION_RESUME = "session.resume"
    SESSION_RESUME_RESULT = "session.resume_result"
    TASK_REQUEST = "task.request"
    TASK_ACCEPTED = "task.accepted"
    TASK_REJECTED = "task.rejected"
    TASK_PROGRESS = "task.progress"
    TASK_HEARTBEAT = "task.heartbeat"
    TASK_RESULT = "task.result"
    TASK_FAILED = "task.failed"
    TASK_CANCELLED = "task.cancelled"
    APPROVAL_REQUEST = "approval.request"
    APPROVAL_ACCEPTED = "approval.accepted"
    APPROVAL_REJECTED = "approval.rejected"
    APPROVAL_EXPIRED = "approval.expired"
    ACK = "ack"
    ERROR = "error"


class TaskStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    DELIVERED = "delivered"
    ACCEPTED = "accepted"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REJECTED = "rejected"


class DeliveryStatus(StrEnum):
    PENDING = "pending"
    DELIVERED = "delivered"
    ACKED = "acked"
    FAILED = "failed"
    EXPIRED = "expired"


class ErrorCode(StrEnum):
    AGENT_NOT_FOUND = "AGENT_NOT_FOUND"
    AGENT_OFFLINE = "AGENT_OFFLINE"
    TASK_NOT_FOUND = "TASK_NOT_FOUND"
    TASK_TIMEOUT = "TASK_TIMEOUT"
    INVALID_TOKEN = "INVALID_TOKEN"
    TOKEN_REVOKED = "TOKEN_REVOKED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    E2EE_NOT_IMPLEMENTED = "E2EE_NOT_IMPLEMENTED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
