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


class InboundPolicy(StrEnum):
    PRIVATE = "private"
    CONTACTS_ONLY = "contacts_only"
    REQUEST_APPROVAL = "request_approval"
    PUBLIC = "public"


class SecurityMode(StrEnum):
    RELAY_VISIBLE = "relay_visible"
    RELAY_ENCRYPTED = "relay_encrypted"
    E2EE = "e2ee"


class ErrorCode(StrEnum):
    AGENT_NOT_FOUND = "AGENT_NOT_FOUND"
    AGENT_OFFLINE = "AGENT_OFFLINE"
    AGENT_FORBIDDEN = "AGENT_FORBIDDEN"
    CONNECTION_APPROVAL_REQUIRED = "CONNECTION_APPROVAL_REQUIRED"
    CONNECTION_REJECTED = "CONNECTION_REJECTED"
    SECURITY_MODE_NOT_SUPPORTED = "SECURITY_MODE_NOT_SUPPORTED"
    TASK_NOT_FOUND = "TASK_NOT_FOUND"
    TASK_TIMEOUT = "TASK_TIMEOUT"
    TASK_EXPIRED = "TASK_EXPIRED"
    TASK_LEASE_EXPIRED = "TASK_LEASE_EXPIRED"
    INVALID_TASK_STATE_TRANSITION = "INVALID_TASK_STATE_TRANSITION"
    MESSAGE_TOO_LARGE = "MESSAGE_TOO_LARGE"
    RATE_LIMITED = "RATE_LIMITED"
    INVALID_TOKEN = "INVALID_TOKEN"
    TOKEN_REVOKED = "TOKEN_REVOKED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"
    E2EE_NOT_IMPLEMENTED = "E2EE_NOT_IMPLEMENTED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    INVALID_AGENT_POLICY = "INVALID_AGENT_POLICY"
    INVALID_REQUEST = "INVALID_REQUEST"
    UNSUPPORTED_MESSAGE_TYPE = "UNSUPPORTED_MESSAGE_TYPE"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    USER_DISABLED = "USER_DISABLED"
    CSRF_TOKEN_MISSING = "CSRF_TOKEN_MISSING"
    CSRF_TOKEN_INVALID = "CSRF_TOKEN_INVALID"
    INVALID_STEP_UP = "INVALID_STEP_UP"
    STEP_UP_REQUIRED = "STEP_UP_REQUIRED"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    SESSION_REVOKED = "SESSION_REVOKED"
    INVALID_SESSION = "INVALID_SESSION"


MESSAGE_TYPES = [item.value for item in MessageType]
TASK_STATUSES = [item.value for item in TaskStatus]
DELIVERY_STATUSES = [item.value for item in DeliveryStatus]
INBOUND_POLICIES = [item.value for item in InboundPolicy]
SECURITY_MODES = [item.value for item in SecurityMode]
ERROR_CODES = [item.value for item in ErrorCode]