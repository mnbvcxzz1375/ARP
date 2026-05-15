"""Error codes matching the AgentNet protocol standard."""

from enum import StrEnum


class ErrorCode(StrEnum):
    INVALID_REQUEST = "INVALID_REQUEST"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
