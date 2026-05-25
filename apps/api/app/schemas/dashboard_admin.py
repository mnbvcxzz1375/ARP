"""Pydantic schemas for Admin Dashboard API."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────────────────────────
# Admin Overview
# ──────────────────────────────────────────────────────────────────

class AdminOverviewResponse(BaseModel):
    total_users: int
    active_users: int
    disabled_users: int
    total_agents: int
    online_agents: int
    active_ws_connections: int
    tasks_1h: int
    tasks_24h: int
    tasks_7d: int
    failed_tasks: int
    expired_tasks: int
    pending_approvals: int
    pending_messages: int
    retry_worker_health: str
    timeout_worker_health: str
    api_5xx_rate: str


# ──────────────────────────────────────────────────────────────────
# Admin Users
# ──────────────────────────────────────────────────────────────────

class AdminUserListItem(BaseModel):
    user_id: str
    username: str
    role: str
    is_disabled: bool
    agents_count: int
    active_api_keys_count: int
    tasks_24h: int
    failed_tasks_24h: int
    created_at: datetime


class AdminUserListResponse(BaseModel):
    users: list[AdminUserListItem]
    total: int
    offset: int
    limit: int


class AdminUserDetailResponse(BaseModel):
    user_id: str
    username: str
    role: str
    is_disabled: bool
    created_at: datetime
    agents_count: int
    active_api_keys_count: int
    tasks_24h: int
    failed_tasks_24h: int
    recent_audit_count: int
    active_sessions_count: int


# ──────────────────────────────────────────────────────────────────
# Admin Agents
# ──────────────────────────────────────────────────────────────────

class AdminAgentListItem(BaseModel):
    agent_id: str
    agent_number: str
    owner_username: str
    name: str
    status: str
    runtime: str
    inbound_policy: str
    discoverable: bool
    tasks_24h: int
    failed_tasks_24h: int


class AdminAgentListResponse(BaseModel):
    agents: list[AdminAgentListItem]
    total: int
    offset: int
    limit: int


class AdminAgentDetailResponse(BaseModel):
    agent_id: str
    agent_number: str
    owner_username: str
    name: str
    runtime: str
    status: str
    inbound_policy: str
    discoverable: bool
    capabilities: list[str]
    token_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    tasks_24h: int
    failed_tasks_24h: int


# ──────────────────────────────────────────────────────────────────
# Admin Tasks
# ──────────────────────────────────────────────────────────────────

class AdminTaskListItem(BaseModel):
    task_id: str
    status: str
    sender_agent: str
    target_agent: str
    owner_username: str
    created_at: datetime
    updated_at: datetime
    error_code: str | None
    delivery_status: str


class AdminTaskListResponse(BaseModel):
    tasks: list[AdminTaskListItem]
    total: int
    offset: int
    limit: int


class AdminTaskDetailResponse(BaseModel):
    task_id: str
    status: str
    payload_preview: str | None
    result_preview: str | None
    error_message: str | None
    delivery_status: str
    retry_count: int
    owner_username: str
    created_at: datetime
    updated_at: datetime


# ──────────────────────────────────────────────────────────────────
# Audit Logs
# ──────────────────────────────────────────────────────────────────

class AuditLogListItem(BaseModel):
    audit_id: str
    actor_type: str
    actor_id: str
    action: str
    resource_type: str | None
    resource_id: str | None
    task_id: str | None
    error_code: str | None
    request_ip: str | None
    details: dict | None = None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    audit_logs: list[AuditLogListItem]
    total: int
    offset: int
    limit: int


# ──────────────────────────────────────────────────────────────────
# System Health
# ──────────────────────────────────────────────────────────────────

class SystemHealthResponse(BaseModel):
    api_health: str
    db_health: str
    redis_health: str
    migration_revision: str
    app_version: str
    retry_worker_health: str
    timeout_worker_health: str
    pending_queue_length: int
    https_wss_staging: str
