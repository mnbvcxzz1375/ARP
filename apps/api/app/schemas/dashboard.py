"""Pydantic schemas for Dashboard API."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────────────────────────
# Overview
# ──────────────────────────────────────────────────────────────────

class OverviewResponse(BaseModel):
    online_agents: int
    tasks_today: int
    failed_tasks: int
    pending_approvals: int
    pending_messages: int
    recent_tasks: list[dict[str, Any]]
    recent_approvals: list[dict[str, Any]]
    recent_agent_status_changes: list[dict[str, Any]]


# ──────────────────────────────────────────────────────────────────
# Agents
# ──────────────────────────────────────────────────────────────────

class AgentListItem(BaseModel):
    agent_id: str
    agent_number: str
    name: str
    runtime: str
    status: str
    inbound_policy: str
    discoverable: bool
    capabilities: list[str]
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime | None


class AgentListResponse(BaseModel):
    agents: list[AgentListItem]
    total: int
    offset: int
    limit: int


class CreateAgentRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    runtime: str = Field(min_length=1, max_length=64)
    inbound_policy: str = "public"
    discoverable: bool = False
    capabilities: list[str] = []


class UpdateAgentRequest(BaseModel):
    name: str | None = None
    inbound_policy: str | None = None
    discoverable: bool | None = None
    capabilities: list[str] | None = None


class AgentDetailResponse(BaseModel):
    agent_id: str
    agent_number: str
    name: str
    runtime: str
    status: str
    inbound_policy: str
    discoverable: bool
    capabilities: list[str]
    token_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


# ──────────────────────────────────────────────────────────────────
# Tasks
# ──────────────────────────────────────────────────────────────────

class TaskListItem(BaseModel):
    task_id: str
    status: str
    sender_agent: str
    target_agent: str
    created_at: datetime
    updated_at: datetime
    duration_sec: int | None
    error_code: str | None
    delivery_status: str


class TaskListResponse(BaseModel):
    tasks: list[TaskListItem]
    total: int
    offset: int
    limit: int


class TaskDetailResponse(BaseModel):
    task_id: str
    status: str
    payload_preview: str | None
    result_preview: str | None
    error_message: str | None
    delivery_status: str
    retry_count: int
    created_at: datetime
    updated_at: datetime


# ──────────────────────────────────────────────────────────────────
# Approvals
# ──────────────────────────────────────────────────────────────────

class ApprovalListItem(BaseModel):
    approval_id: str
    type: str
    status: str
    risk_level: str
    action_kind: str
    action_preview: str | None
    created_at: datetime


class ApprovalListResponse(BaseModel):
    approvals: list[ApprovalListItem]
    total: int
    offset: int
    limit: int


# ──────────────────────────────────────────────────────────────────
# Connections / Firewall
# ──────────────────────────────────────────────────────────────────

class FirewallAgentInfo(BaseModel):
    agent_id: str
    agent_number: str
    inbound_policy: str
    pending_requests: int
    accepted_connections: int
    rejected_connections: int


class PendingConnection(BaseModel):
    connection_id: str
    agent_number: str
    requester_agent: str
    requested_policy: str
    created_at: datetime


class ConnectionsResponse(BaseModel):
    agents: list[FirewallAgentInfo]
    pending_requests: list[PendingConnection]


class UpdateFirewallRequest(BaseModel):
    inbound_policy: str | None = None
    allowed_contacts: list[str] | None = None
    denied_contacts: list[str] | None = None


# ──────────────────────────────────────────────────────────────────
# API Keys
# ──────────────────────────────────────────────────────────────────

class ApiKeyListItem(BaseModel):
    api_key_id: str
    key_prefix: str
    name: str
    created_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None


class ApiKeyListResponse(BaseModel):
    api_keys: list[ApiKeyListItem]
    total: int


class CreateApiKeyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    expires_at: datetime | None = None


class CreateApiKeyResponse(BaseModel):
    api_key_id: str
    key_prefix: str
    name: str
    expires_at: datetime | None
    api_key: str


class RevokeApiKeyRequest(BaseModel):
    allow_last_key: bool = False
