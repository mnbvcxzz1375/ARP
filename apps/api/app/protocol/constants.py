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
    """Message delivery status.

    Status flow:
    1. queued -> route_selected -> delivering -> delivered -> acknowledged
    2. queued -> route_selected -> delivering -> delivery_failed (retry or expire)
    3. queued -> expired (TTL exceeded before delivery)
    """
    QUEUED = "queued"  # Message queued for offline agent
    ROUTE_SELECTED = "route_selected"  # Route decision made (Phase 13+)
    DELIVERING = "delivering"  # Delivery in progress
    DELIVERED = "delivered"  # Successfully delivered to agent
    ACKNOWLEDGED = "acknowledged"  # Agent acknowledged receipt
    DELIVERY_FAILED = "delivery_failed"  # Delivery failed (will retry)
    EXPIRED = "expired"  # TTL exceeded

    # Legacy aliases for backward compatibility
    PENDING = "queued"  # Alias for QUEUED
    ACKED = "acknowledged"  # Alias for ACKNOWLEDGED
    FAILED = "delivery_failed"  # Alias for DELIVERY_FAILED


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
    EGRESS_BLOCKED = "EGRESS_BLOCKED"
    CSRF_TOKEN_MISSING = "CSRF_TOKEN_MISSING"
    CSRF_TOKEN_INVALID = "CSRF_TOKEN_INVALID"
    INVALID_STEP_UP = "INVALID_STEP_UP"
    STEP_UP_REQUIRED = "STEP_UP_REQUIRED"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    SESSION_REVOKED = "SESSION_REVOKED"
    INVALID_SESSION = "INVALID_SESSION"
    ROUTE_POLICY_DENIED = "ROUTE_POLICY_DENIED"
    DATA_BOUNDARY_VIOLATION = "DATA_BOUNDARY_VIOLATION"
    ADAPTER_NOT_FOUND = "ADAPTER_NOT_FOUND"
    ADAPTER_EXECUTION_FAILED = "ADAPTER_EXECUTION_FAILED"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    NO_AVAILABLE_RELAY = "NO_AVAILABLE_RELAY"
    INVALID_STATE = "INVALID_STATE"


MESSAGE_TYPES = [item.value for item in MessageType]
TASK_STATUSES = [item.value for item in TaskStatus]
DELIVERY_STATUSES = [item.value for item in DeliveryStatus]
INBOUND_POLICIES = [item.value for item in InboundPolicy]
SECURITY_MODES = [item.value for item in SecurityMode]
ERROR_CODES = [item.value for item in ErrorCode]