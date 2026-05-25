"""Dedicated channel request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class DedicatedChannelCreate(BaseModel):
    """Request body for creating a dedicated channel."""

    scope_id: UUID | None = Field(None, description="Network scope ID")
    channel_name: str = Field(..., min_length=1, max_length=128, description="Human-readable channel name")
    channel_type: str = Field(..., description="Channel type (vpn, private_link, p2p, direct_connect)")
    source_agent_id: UUID = Field(..., description="Source agent ID")
    target_agent_id: UUID = Field(..., description="Target agent ID")
    connection_config: dict[str, Any] = Field(default_factory=dict, description="Connection configuration")
    encryption_config: dict[str, Any] = Field(default_factory=dict, description="Encryption configuration")
    bandwidth_mbps: float | None = Field(None, gt=0, description="Target bandwidth in Mbps")
    latency_target_ms: float | None = Field(None, gt=0, description="Target latency in ms")


class DedicatedChannelUpdate(BaseModel):
    """Request body for updating a dedicated channel."""

    channel_name: str | None = Field(None, min_length=1, max_length=128)
    connection_config: dict[str, Any] | None = None
    encryption_config: dict[str, Any] | None = None
    bandwidth_mbps: float | None = Field(None, gt=0)
    latency_target_ms: float | None = Field(None, gt=0)


class DedicatedChannelResponse(BaseModel):
    """Single dedicated channel response."""

    id: UUID
    scope_id: UUID | None
    channel_name: str
    channel_type: str
    source_agent_id: UUID
    target_agent_id: UUID
    connection_config: dict[str, Any]
    encryption_config: dict[str, Any]
    bandwidth_mbps: float | None
    latency_target_ms: float | None
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = dict(from_attributes=True)

    @classmethod
    def from_channel(cls, channel: Any) -> DedicatedChannelResponse:
        """Build response, masking sensitive fields in connection/encryption config."""
        safe_connection = _mask_secrets(channel.connection_config or {})
        safe_encryption = _mask_secrets(channel.encryption_config or {})
        data = {
            "id": channel.id,
            "scope_id": channel.scope_id,
            "channel_name": channel.channel_name,
            "channel_type": channel.channel_type,
            "source_agent_id": channel.source_agent_id,
            "target_agent_id": channel.target_agent_id,
            "connection_config": safe_connection,
            "encryption_config": safe_encryption,
            "bandwidth_mbps": channel.bandwidth_mbps,
            "latency_target_ms": channel.latency_target_ms,
            "enabled": channel.enabled,
            "created_at": channel.created_at,
            "updated_at": channel.updated_at,
        }
        return cls.model_validate(data)


class DedicatedChannelListResponse(BaseModel):
    """Paginated list of dedicated channels."""

    channels: list[DedicatedChannelResponse]
    total: int
    offset: int
    limit: int


class ChannelHealthCheckResponse(BaseModel):
    """Health check result for a dedicated channel."""

    id: UUID
    channel_id: UUID
    check_time: datetime
    latency_ms: float | None
    packet_loss_percent: float | None
    bandwidth_mbps: float | None
    status: str
    error_message: str | None

    model_config = dict(from_attributes=True)


def _mask_secrets(config: dict[str, Any]) -> dict[str, Any]:
    """Mask secret values in channel config dicts.

    Keys whose name contains 'key', 'secret', 'token', 'password',
    'credential', or 'private' are replaced with '***MASKED***'.

    Recurses into nested dicts and list-of-dict structures so that
    patterns like ``peers: [{private_key: "..."}]`` are also masked.
    """
    sensitive_fragments = {"key", "secret", "token", "password", "credential", "private"}
    masked: dict[str, Any] = {}
    for k, v in config.items():
        if any(frag in k.lower() for frag in sensitive_fragments):
            masked[k] = "***MASKED***"
        elif isinstance(v, dict):
            masked[k] = _mask_secrets(v)
        elif isinstance(v, list):
            masked[k] = [_mask_value(item, sensitive_fragments) for item in v]
        else:
            masked[k] = v
    return masked


def _mask_value(value: Any, sensitive_fragments: set[str]) -> Any:
    """Recursively mask secrets in list items (dicts or nested lists)."""
    if isinstance(value, dict):
        return _mask_secrets(value)
    if isinstance(value, list):
        return [_mask_value(item, sensitive_fragments) for item in value]
    return value