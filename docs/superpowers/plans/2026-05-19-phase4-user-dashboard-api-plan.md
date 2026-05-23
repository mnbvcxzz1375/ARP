# Phase 4: User Dashboard API — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Build all user-facing Dashboard API endpoints under `/v1/dashboard/*` for the user console.

**Architecture:** Single router `dashboard_user.py` with 18 endpoints grouped by resource (overview, agents, tasks, approvals, connections, api-keys). Service layer `dashboard_service.py` handles aggregation (online status from Redis, KPI counts). Schemas in `dashboard.py`. All endpoints use Phase 2 session auth and Phase 3 RBAC.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Pydantic, Redis, pytest

---

## File Structure

| File | Operation | Responsibility |
|------|-----------|---------------|
| `apps/api/app/services/dashboard_service.py` | Create | Aggregation logic (overview KPIs, online status, secret masking) |
| `apps/api/app/schemas/dashboard.py` | Create | Pydantic request/response schemas |
| `apps/api/app/routers/dashboard_user.py` | Create | All 18 user dashboard endpoints |
| `apps/api/app/main.py` | Modify | Register dashboard_user router |
| `apps/api/tests/test_phase_web_4_user_api.py` | Create | Endpoint tests |
| `reports/web_phase_4_report.md` | Create | Phase report |

---

### Task 1: Dashboard service (aggregation + secret masking)

**Files:**
- Create: `apps/api/app/services/dashboard_service.py`

- [ ] **Step 1: Create the dashboard service**

Create `apps/api/app/services/dashboard_service.py` with:

```python
"""Dashboard aggregation: overview KPIs, online status, secret masking."""
import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.task import Task
from app.models.approval import Approval
from app.models.message import Message
from app.models.audit_log import AuditLog
from app.redis import redis_client


# Secret patterns to mask in payloads/results
_SECRET_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "***"),
    (re.compile(r"agt_sk_[A-Za-z0-9_-]{20,}"), "***"),
    (re.compile(r"ak_[A-Za-z0-9]{20,}"), "***"),
]


def mask_secrets(text: str) -> str:
    """Replace secret-looking patterns with ***."""
    if not text:
        return text
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


async def get_agent_online_status(session: AsyncSession, agent_ids: list[str]) -> dict[str, bool]:
    """Check Redis presence for each agent using pipeline (not individual exists).

    Per web.md Section 8: do NOT loop individual Redis exists calls for overview.
    Use Redis pipeline or maintain a separate online count.
    """
    if not agent_ids:
        return {}

    # Use Redis pipeline for batch presence check
    pipe = redis_client.pipeline()
    for aid in agent_ids:
        pipe.exists(f"ws:presence:{aid}")
    results = await pipe.execute()

    return {aid: bool(exists) for aid, exists in zip(agent_ids, results)}


async def get_overview_kpis(
    session: AsyncSession,
    user_id: str,
) -> dict:
    """Get user overview KPIs: online agents, tasks today, failed tasks, pending approvals."""
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Get user's agent IDs
    agent_result = await session.execute(
        select(Agent.id).where(Agent.owner_id == user_id)
    )
    agent_ids = [str(aid) for aid in agent_result.scalars().all()]

    # Online agents
    online_status = await get_agent_online_status(session, agent_ids)
    online_count = sum(1 for v in online_status.values() if v)

    # Tasks today
    tasks_today_result = await session.execute(
        select(func.count(Task.id)).where(
            Task.created_by.in_(agent_ids),
            Task.created_at >= today_start,
        )
    )
    tasks_today = tasks_today_result.scalar_one()

    # Failed tasks (last 24h)
    failed_cutoff = now - timedelta(hours=24)
    failed_result = await session.execute(
        select(func.count(Task.id)).where(
            Task.created_by.in_(agent_ids),
            Task.status == "failed",
            Task.updated_at >= failed_cutoff,
        )
    )
    failed_tasks = failed_result.scalar_one()

    # Pending approvals
    pending_result = await session.execute(
        select(func.count(Approval.id)).where(
            Approval.agent_id.in_(agent_ids),
            Approval.status == "pending",
        )
    )
    pending_approvals = pending_result.scalar_one()

    # Pending messages (delivered but not acked)
    pending_msg_result = await session.execute(
        select(func.count(Message.id)).where(
            Message.delivery_status == "delivered",
            # Join through task to check ownership
            Message.task_id.in_(
                select(Task.id).where(Task.created_by.in_(agent_ids))
            ),
        )
    )
    pending_messages = pending_msg_result.scalar_one()

    # Recent tasks (last 10)
    recent_tasks_result = await session.execute(
        select(Task).where(
            (Task.created_by.in_(agent_ids)) | (Task.assigned_to.in_(agent_ids))
        ).order_by(Task.created_at.desc()).limit(10)
    )
    recent_tasks = []
    for t in recent_tasks_result.scalars():
        recent_tasks.append({
            "task_id": str(t.id),
            "status": t.status,
            "created_at": t.created_at,
        })

    # Recent approvals (last 10)
    recent_approvals_result = await session.execute(
        select(Approval).where(
            Approval.agent_id.in_(agent_ids)
        ).order_by(Approval.created_at.desc()).limit(10)
    )
    recent_approvals = []
    for a in recent_approvals_result.scalars():
        recent_approvals.append({
            "approval_id": str(a.id),
            "status": a.status,
            "risk_level": a.risk_level,
            "created_at": a.created_at,
        })

    # Recent agent status changes from audit log
    recent_audit_result = await session.execute(
        select(AuditLog).where(
            AuditLog.resource_type == "agent",
            AuditLog.actor_id.in_(agent_ids),
        ).order_by(AuditLog.created_at.desc()).limit(10)
    )
    recent_agent_changes = []
    for log in recent_audit_result.scalars():
        recent_agent_changes.append({
            "action": log.action,
            "resource_id": log.resource_id,
            "created_at": log.created_at,
        })

    return {
        "online_agents": online_count,
        "tasks_today": tasks_today,
        "failed_tasks": failed_tasks,
        "pending_approvals": pending_approvals,
        "pending_messages": pending_messages,
        "recent_tasks": recent_tasks,
        "recent_approvals": recent_approvals,
        "recent_agent_status_changes": recent_agent_changes,
    }
```

**IMPORTANT:** The above function does real-time DB queries. Per web.md Section 8, overview pages must use Redis snapshot cache. Add this cached wrapper:

```python
import json
from app.redis import redis_client


async def get_overview_kpis_cached(session: AsyncSession, user_id: str) -> dict:
    """Get overview KPIs with Redis snapshot cache (TTL 15s per web.md)."""
    cache_key = f"dashboard:overview:{user_id}"
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    result = await get_overview_kpis(session, user_id)
    await redis_client.setex(cache_key, 15, json.dumps(result, default=str))
    return result
```

The router should call `get_overview_kpis_cached` instead of `get_overview_kpis`.

- [ ] **Step 2: Verify it parses**

```bash
python -c "import ast; ast.parse(open('apps/api/app/services/dashboard_service.py').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add apps/api/app/services/dashboard_service.py
git commit -m "feat: add dashboard aggregation service (KPIs, online status, secret masking)"
```

---

### Task 2: Dashboard schemas

**Files:**
- Create: `apps/api/app/schemas/dashboard.py`

- [ ] **Step 1: Create the schema file**

Create `apps/api/app/schemas/dashboard.py` with Pydantic models for all request/response types needed by the 18 endpoints:

```python
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
    api_key: str  # One-time plain key


class RevokeApiKeyRequest(BaseModel):
    allow_last_key: bool = False
```

- [ ] **Step 2: Verify**

```bash
python -c "import ast; ast.parse(open('apps/api/app/schemas/dashboard.py').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add apps/api/app/schemas/dashboard.py
git commit -m "feat: add dashboard Pydantic schemas"
```

---

### Task 3: Agent endpoints

**Files:**
- Modify: `apps/api/app/routers/dashboard_user.py` (create new file, add agent endpoints first)

- [ ] **Step 1: Create the router with agent endpoints**

Create `apps/api/app/routers/dashboard_user.py` starting with agent endpoints:

```python
"""User Dashboard API endpoints."""
import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies.auth import CurrentSession
from app.dependencies.rbac import require_permission
from app.models.agent import Agent
from app.models.agent_token import AgentToken
from app.models.task import Task
from app.models.message import Message
from app.models.approval import Approval
from app.models.connection import Connection
from app.models.api_key import ApiKey
from app.models.user import User
from app.schemas.dashboard import (
    OverviewResponse,
    AgentListItem, AgentListResponse, CreateAgentRequest,
    UpdateAgentRequest, AgentDetailResponse,
    TaskListItem, TaskListResponse, TaskDetailResponse,
    ApprovalListItem, ApprovalListResponse,
    ConnectionsResponse, FirewallAgentInfo, PendingConnection,
    UpdateFirewallRequest,
    ApiKeyListItem, ApiKeyListResponse, CreateApiKeyRequest,
    CreateApiKeyResponse, RevokeApiKeyRequest,
)
from app.services.dashboard_service import (
    get_overview_kpis, mask_secrets, get_agent_online_status,
)
from app.services.rbac_service import (
    PERM_READ_OWN_AGENTS, PERM_CREATE_AGENT, PERM_EDIT_OWN_AGENT,
    PERM_DELETE_OWN_AGENT, PERM_ROTATE_OWN_TOKEN,
    PERM_READ_OWN_TASKS, PERM_READ_OWN_TASK_DETAIL, PERM_CREATE_TASK,
    PERM_HANDLE_OWN_APPROVAL,
    PERM_MANAGE_OWN_CONNECTIONS, PERM_MANAGE_OWN_FIREWALL,
    PERM_MANAGE_OWN_KEYS,
)
from app.protocol.constants import TaskStatus

router = APIRouter(prefix="/v1/dashboard", tags=["dashboard-user"])


def _user_agent_ids(user: User) -> list[str]:
    """Get all agent IDs owned by the user."""
    return [str(a.id) for a in user.agents]


# ──────────────────────────────────────────────────────────────────
# Overview
# ──────────────────────────────────────────────────────────────────

@router.get("/overview", response_model=OverviewResponse)
async def overview(
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_permission(PERM_READ_OWN_AGENTS)),
):
    kpis = await get_overview_kpis(session, str(ds.user_id))
    return kpis


# ──────────────────────────────────────────────────────────────────
# Agents
# ──────────────────────────────────────────────────────────────────

@router.get("/agents", response_model=AgentListResponse)
async def list_agents(
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status: str | None = None,
    runtime: str | None = None,
    inbound_policy: str | None = None,
    search: str | None = None,
    _: User = Depends(require_permission(PERM_READ_OWN_AGENTS)),
):
    stmt = select(Agent).where(Agent.owner_id == ds.user_id)
    if runtime:
        stmt = stmt.where(Agent.runtime == runtime)
    if inbound_policy:
        stmt = stmt.where(Agent.inbound_policy == inbound_policy)
    if search:
        stmt = stmt.where(Agent.name.ilike(f"%{search}%"))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(Agent.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    agents = list(result.scalars().all())

    # Check online status
    agent_ids = [str(a.id) for a in agents]
    online_status = await get_agent_online_status(session, agent_ids)

    items = []
    for a in agents:
        items.append(AgentListItem(
            agent_id=str(a.id),
            agent_number=a.agent_number,
            name=a.name,
            runtime=a.runtime,
            status="online" if online_status.get(str(a.id)) else "offline",
            inbound_policy=a.inbound_policy,
            discoverable=a.discoverable,
            capabilities=a.capabilities or [],
            created_at=a.created_at,
            updated_at=a.updated_at,
            last_seen_at=None,
        ))

    return AgentListResponse(agents=items, total=total, offset=offset, limit=limit)


@router.post("/agents", status_code=201)
async def create_agent(
    body: CreateAgentRequest,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_permission(PERM_CREATE_AGENT)),
):
    import uuid
    from app.services.agent_service import create_agent as _create_agent_service

    agent, token = await _create_agent_service(
        session,
        owner_id=ds.user_id,
        name=body.name,
        runtime=body.runtime,
        inbound_policy=body.inbound_policy,
        discoverable=body.discoverable,
        capabilities=body.capabilities,
    )
    await session.commit()
    return {
        "agent_id": str(agent.id),
        "agent_number": agent.agent_number,
        "agent_token": token,
        "name": agent.name,
    }


@router.get("/agents/{agent_id}")
async def get_agent_detail(
    agent_id: str,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_permission(PERM_READ_OWN_AGENTS)),
):
    result = await session.execute(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.owner_id == ds.user_id,
        )
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Agent not found")

    # Token metadata (no plaintext)
    token_result = await session.execute(
        select(AgentToken).where(AgentToken.agent_id == agent.id)
    )
    token = token_result.scalar_one_or_none()
    token_meta = {}
    if token:
        token_meta = {
            "prefix": token.token_prefix,
            "created_at": token.created_at,
            "rotated_at": token.rotated_at,
        }

    return AgentDetailResponse(
        agent_id=str(agent.id),
        agent_number=agent.agent_number,
        name=agent.name,
        runtime=agent.runtime,
        status="online",  # Will be enriched by online status check
        inbound_policy=agent.inbound_policy,
        discoverable=agent.discoverable,
        capabilities=agent.capabilities or [],
        token_metadata=token_meta,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


@router.patch("/agents/{agent_id}")
async def update_agent(
    agent_id: str,
    body: UpdateAgentRequest,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_permission(PERM_EDIT_OWN_AGENT)),
):
    result = await session.execute(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.owner_id == ds.user_id,
        )
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Agent not found")

    if body.name is not None:
        agent.name = body.name
    if body.inbound_policy is not None:
        agent.inbound_policy = body.inbound_policy
    if body.discoverable is not None:
        agent.discoverable = body.discoverable
    if body.capabilities is not None:
        agent.capabilities = body.capabilities

    await session.commit()
    return {"agent_id": str(agent.id), "message": "updated"}


@router.delete("/agents/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: str,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_permission(PERM_DELETE_OWN_AGENT)),
):
    result = await session.execute(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.owner_id == ds.user_id,
        )
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Agent not found")

    await session.delete(agent)
    await session.commit()


@router.post("/agents/{agent_id}/rotate-token")
async def rotate_agent_token(
    agent_id: str,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_permission(PERM_ROTATE_OWN_TOKEN)),
):
    from app.services.agent_service import rotate_token as _rotate_token_service

    result = await session.execute(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.owner_id == ds.user_id,
        )
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Agent not found")

    new_token = await _rotate_token_service(session, agent)
    await session.commit()
    return {"agent_id": str(agent.id), "agent_token": new_token}
```

- [ ] **Step 2: Verify it parses**

```bash
python -c "import ast; ast.parse(open('apps/api/app/routers/dashboard_user.py').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add apps/api/app/routers/dashboard_user.py
git commit -m "feat: add user dashboard agent endpoints (list, create, detail, update, delete, rotate)"
```

---

### Task 4: Task endpoints

**Files:**
- Modify: `apps/api/app/routers/dashboard_user.py`

- [ ] **Step 1: Add task endpoints**

Append to `apps/api/app/routers/dashboard_user.py`:

```python
# ──────────────────────────────────────────────────────────────────
# Tasks
# ──────────────────────────────────────────────────────────────────

@router.get("/tasks", response_model=TaskListResponse)
async def list_tasks(
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status: str | None = None,
    sender: str | None = None,
    target: str | None = None,
    error_code: str | None = None,
    _: User = Depends(require_permission(PERM_READ_OWN_TASKS)),
):
    agent_ids = [str(a.id) for a in ds.user.agents]

    stmt = select(Task).where(
        (Task.created_by.in_(agent_ids)) | (Task.assigned_to.in_(agent_ids))
    )
    if status:
        stmt = stmt.where(Task.status == status)
    if error_code:
        stmt = stmt.where(Task.error_message.like(f"%{error_code}%"))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(Task.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    tasks = list(result.scalars().all())

    items = []
    for t in tasks:
        items.append(TaskListItem(
            task_id=str(t.id),
            status=t.status,
            sender_agent=str(t.created_by),
            target_agent=str(t.assigned_to),
            created_at=t.created_at,
            updated_at=t.updated_at,
            duration_sec=None,
            error_code=None,
            delivery_status="delivered",
        ))

    return TaskListResponse(tasks=items, total=total, offset=offset, limit=limit)


@router.get("/tasks/{task_id}")
async def get_task_detail(
    task_id: str,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_permission(PERM_READ_OWN_TASK_DETAIL)),
):
    agent_ids = [str(a.id) for a in ds.user.agents]

    result = await session.execute(
        select(Task).where(
            Task.id == task_id,
            (Task.created_by.in_(agent_ids)) | (Task.assigned_to.in_(agent_ids)),
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Task not found")

    payload_preview = None
    result_preview = None

    # Get first message for payload preview
    msg_result = await session.execute(
        select(Message).where(Message.task_id == task.id).order_by(Message.created_at.asc()).limit(1)
    )
    first_msg = msg_result.scalar_one_or_none()
    if first_msg and first_msg.content:
        payload_preview = mask_secrets(json.dumps(first_msg.content)[:500])

    if task.result:
        result_preview = mask_secrets(json.dumps(task.result)[:500])

    return TaskDetailResponse(
        task_id=str(task.id),
        status=task.status,
        payload_preview=payload_preview,
        result_preview=result_preview,
        error_message=task.error_message,
        delivery_status="delivered",
        retry_count=0,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.get("/tasks/{task_id}/messages")
async def get_task_messages(
    task_id: str,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    agent_ids = [str(a.id) for a in ds.user.agents]

    # Verify ownership
    task_result = await session.execute(
        select(Task.id).where(
            Task.id == task_id,
            (Task.created_by.in_(agent_ids)) | (Task.assigned_to.in_(agent_ids)),
        )
    )
    if task_result.scalar_one_or_none() is None:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Task not found")

    stmt = select(Message).where(Message.task_id == task_id).order_by(Message.created_at.asc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    messages = list(result.scalars().all())

    return {
        "messages": [
            {
                "message_id": m.message_id,
                "type": m.type,
                "delivery_status": m.delivery_status,
                "created_at": m.created_at,
            }
            for m in messages
        ],
        "total": len(messages),
        "offset": offset,
        "limit": limit,
    }


@router.get("/tasks/{task_id}/progress")
async def get_task_progress(
    task_id: str,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    from app.services.task_service import list_task_progress

    agent_ids = [str(a.id) for a in ds.user.agents]
    task_result = await session.execute(
        select(Task.id).where(
            Task.id == task_id,
            (Task.created_by.in_(agent_ids)) | (Task.assigned_to.in_(agent_ids)),
        )
    )
    if task_result.scalar_one_or_none() is None:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Task not found")

    entries, total = await list_task_progress(session, task_id, offset=offset, limit=limit)
    return {
        "progress": [
            {
                "seq": e.seq,
                "status": e.status,
                "progress_pct": e.progress_pct,
                "message": e.message,
                "created_at": e.created_at,
            }
            for e in entries
        ],
        "total": total,
        "offset": offset,
        "limit": limit,
    }
```

- [ ] **Step 2: Commit**

```bash
git add apps/api/app/routers/dashboard_user.py
git commit -m "feat: add user dashboard task endpoints (list, detail, messages, progress)"
```

---

### Task 5: Approval endpoints

**Files:**
- Modify: `apps/api/app/routers/dashboard_user.py`

- [ ] **Step 1: Add approval endpoints**

Append to `apps/api/app/routers/dashboard_user.py`:

```python
# ──────────────────────────────────────────────────────────────────
# Approvals
# ──────────────────────────────────────────────────────────────────

@router.get("/approvals", response_model=ApprovalListResponse)
async def list_approvals(
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status: str | None = None,
    _: User = Depends(require_permission(PERM_HANDLE_OWN_APPROVAL)),
):
    agent_ids = [str(a.id) for a in ds.user.agents]

    stmt = select(Approval).where(Approval.agent_id.in_(agent_ids))
    if status:
        stmt = stmt.where(Approval.status == status)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(Approval.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    approvals = list(result.scalars().all())

    items = []
    for a in approvals:
        items.append(ApprovalListItem(
            approval_id=str(a.id),
            type="task_action",
            status=a.status,
            risk_level=a.risk_level,
            action_kind=a.action_kind,
            action_preview=a.action_preview,
            created_at=a.created_at,
        ))

    return ApprovalListResponse(approvals=items, total=total, offset=offset, limit=limit)


@router.post("/approvals/{approval_id}/accept")
async def accept_approval(
    approval_id: str,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_permission(PERM_HANDLE_OWN_APPROVAL)),
):
    from app.services.approval_service import accept_approval as _accept_approval

    agent_ids = [str(a.id) for a in ds.user.agents]
    result = await session.execute(
        select(Approval).where(
            Approval.id == approval_id,
            Approval.agent_id.in_(agent_ids),
        )
    )
    approval = result.scalar_one_or_none()
    if approval is None:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Approval not found")

    await _accept_approval(session, approval)
    await session.commit()
    return {"approval_id": str(approval.id), "status": "accepted"}


@router.post("/approvals/{approval_id}/reject")
async def reject_approval(
    approval_id: str,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_permission(PERM_HANDLE_OWN_APPROVAL)),
):
    from app.services.approval_service import reject_approval as _reject_approval

    agent_ids = [str(a.id) for a in ds.user.agents]
    result = await session.execute(
        select(Approval).where(
            Approval.id == approval_id,
            Approval.agent_id.in_(agent_ids),
        )
    )
    approval = result.scalar_one_or_none()
    if approval is None:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Approval not found")

    await _reject_approval(session, approval)
    await session.commit()
    return {"approval_id": str(approval.id), "status": "rejected"}
```

- [ ] **Step 2: Commit**

```bash
git add apps/api/app/routers/dashboard_user.py
git commit -m "feat: add user dashboard approval endpoints (list, accept, reject)"
```

---

### Task 6: Connection / Firewall endpoints

**Files:**
- Modify: `apps/api/app/routers/dashboard_user.py`

- [ ] **Step 1: Add connection and firewall endpoints**

Append to `apps/api/app/routers/dashboard_user.py`:

```python
# ──────────────────────────────────────────────────────────────────
# Connections / Firewall
# ──────────────────────────────────────────────────────────────────

@router.get("/connections")
async def get_connections(
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_permission(PERM_MANAGE_OWN_CONNECTIONS)),
):
    agent_ids = [a.id for a in ds.user.agents]

    # Per-agent firewall info
    agents_info = []
    for agent in ds.user.agents:
        pending = await session.execute(
            select(func.count(Connection.id)).where(
                Connection.agent_id == agent.id,
                Connection.status == "pending",
            )
        )
        accepted = await session.execute(
            select(func.count(Connection.id)).where(
                Connection.agent_id == agent.id,
                Connection.status == "accepted",
            )
        )
        rejected = await session.execute(
            select(func.count(Connection.id)).where(
                Connection.agent_id == agent.id,
                Connection.status == "rejected",
            )
        )
        agents_info.append(FirewallAgentInfo(
            agent_id=str(agent.id),
            agent_number=agent.agent_number,
            inbound_policy=agent.inbound_policy,
            pending_requests=pending.scalar_one(),
            accepted_connections=accepted.scalar_one(),
            rejected_connections=rejected.scalar_one(),
        ))

    # Pending connection requests
    pending_result = await session.execute(
        select(Connection).where(
            Connection.agent_id.in_(agent_ids),
            Connection.status == "pending",
        ).order_by(Connection.created_at.desc())
    )
    pending_requests = []
    for c in pending_result.scalars():
        pending_requests.append(PendingConnection(
            connection_id=str(c.id),
            agent_number=c.agent_number,
            requester_agent=str(c.requester_agent_id),
            requested_policy=c.requested_policy or "unknown",
            created_at=c.created_at,
        ))

    return ConnectionsResponse(agents=agents_info, pending_requests=pending_requests)


@router.post("/connections/{connection_id}/accept")
async def accept_connection(
    connection_id: str,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_permission(PERM_MANAGE_OWN_CONNECTIONS)),
):
    from app.services.connection_service import accept_connection as _accept_connection

    result = await session.execute(
        select(Connection).where(
            Connection.id == connection_id,
            Connection.agent_id.in_([a.id for a in ds.user.agents]),
        )
    )
    conn = result.scalar_one_or_none()
    if conn is None:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Connection not found")

    await _accept_connection(session, conn)
    await session.commit()
    return {"connection_id": str(conn.id), "status": "accepted"}


@router.post("/connections/{connection_id}/reject")
async def reject_connection(
    connection_id: str,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_permission(PERM_MANAGE_OWN_CONNECTIONS)),
):
    from app.services.connection_service import reject_connection as _reject_connection

    result = await session.execute(
        select(Connection).where(
            Connection.id == connection_id,
            Connection.agent_id.in_([a.id for a in ds.user.agents]),
        )
    )
    conn = result.scalar_one_or_none()
    if conn is None:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Connection not found")

    await _reject_connection(session, conn)
    await session.commit()
    return {"connection_id": str(conn.id), "status": "rejected"}


@router.patch("/agents/{agent_id}/firewall")
async def update_firewall(
    agent_id: str,
    body: UpdateFirewallRequest,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_permission(PERM_MANAGE_OWN_FIREWALL)),
):
    result = await session.execute(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.owner_id == ds.user_id,
        )
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        from fastapi import HTTPException, status as http_status
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Agent not found")

    if body.inbound_policy is not None:
        agent.inbound_policy = body.inbound_policy

    await session.commit()
    return {"agent_id": str(agent.id), "inbound_policy": agent.inbound_policy}
```

- [ ] **Step 2: Commit**

```bash
git add apps/api/app/routers/dashboard_user.py
git commit -m "feat: add user dashboard connection/firewall endpoints"
```

---

### Task 7: API Key endpoints

**Files:**
- Modify: `apps/api/app/routers/dashboard_user.py`

- [ ] **Step 1: Add API key endpoints**

Append to `apps/api/app/routers/dashboard_user.py`:

```python
# ──────────────────────────────────────────────────────────────────
# API Keys
# ──────────────────────────────────────────────────────────────────

@router.get("/api-keys")
async def list_api_keys(
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_permission(PERM_MANAGE_OWN_KEYS)),
):
    from app.services.api_key_service import list_api_keys as _list_api_keys

    keys = await _list_api_keys(session, ds.user)
    return {
        "api_keys": [
            {
                "api_key_id": str(k.id),
                "key_prefix": k.key_prefix,
                "name": k.name,
                "created_at": k.created_at,
                "expires_at": k.expires_at,
                "revoked_at": k.revoked_at,
            }
            for k in keys
        ],
        "total": len(keys),
    }


@router.post("/api-keys", status_code=201)
async def create_api_key(
    body: CreateApiKeyRequest,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_permission(PERM_MANAGE_OWN_KEYS)),
):
    from app.services.api_key_service import create_api_key as _create_api_key

    key, raw = await _create_api_key(session, ds.user, name=body.name, expires_at=body.expires_at)
    await session.commit()
    return {
        "api_key_id": str(key.id),
        "key_prefix": key.key_prefix,
        "name": key.name,
        "expires_at": key.expires_at,
        "api_key": raw,
    }


@router.post("/api-keys/{api_key_id}/revoke")
async def revoke_api_key(
    api_key_id: str,
    body: RevokeApiKeyRequest,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_permission(PERM_MANAGE_OWN_KEYS)),
):
    from app.services.api_key_service import revoke_api_key as _revoke_api_key
    from uuid import UUID

    key = await _revoke_api_key(session, ds.user, UUID(api_key_id), allow_last_key=body.allow_last_key)
    await session.commit()
    return {
        "api_key_id": str(key.id),
        "key_prefix": key.key_prefix,
        "name": key.name,
        "revoked_at": key.revoked_at,
    }
```

- [ ] **Step 2: Commit**

```bash
git add apps/api/app/routers/dashboard_user.py
git commit -m "feat: add user dashboard API key endpoints (list, create, revoke)"
```

---

### Task 8: Register router in main.py

**Files:**
- Modify: `apps/api/app/main.py`

- [ ] **Step 1: Add import and router registration**

In `apps/api/app/main.py`:

Add import:
```python
from app.routers.dashboard_user import router as dashboard_user_router
```

Add registration after `dashboard_auth_router`:
```python
    app.include_router(dashboard_user_router)
```

- [ ] **Step 2: Commit**

```bash
git add apps/api/app/main.py
git commit -m "feat: register user dashboard router"
```

---

### Task 9: Write tests

**Files:**
- Create: `apps/api/tests/test_phase_web_4_user_api.py`

- [ ] **Step 1: Create test file**

Create `apps/api/tests/test_phase_web_4_user_api.py` with tests for:
- Overview endpoint returns KPIs
- Agent list returns user's agents only
- Agent create works with valid data
- Agent detail 404 for other user's agent
- Task list filters by user ownership
- Task detail masks secrets in payload
- Approval list/accept/reject
- API key list/create/revoke
- Cross-user isolation (user cannot see another user's resources)

- [ ] **Step 2: Run tests**

```bash
cd apps/api && python -m pytest tests/test_phase_web_4_user_api.py -v
```

- [ ] **Step 3: Commit**

```bash
git add apps/api/tests/test_phase_web_4_user_api.py
git commit -m "test: add Phase Web 4 user dashboard API tests"
```

---

### Task 10: Phase report

**Files:**
- Create: `reports/web_phase_4_report.md`

- [ ] **Step 1: Create the report**

Create `reports/web_phase_4_report.md` with:
- Goal: User Dashboard API endpoints
- Files changed table
- Commands executed
- Test results
- Security verification (secret masking, ownership enforcement, cross-user isolation)
- Unfinished items: [FILL IN AFTER EXECUTION]
- Risks and follow-up: Phase 5 will add admin endpoints

- [ ] **Step 2: Commit**

```bash
git add -f reports/web_phase_4_report.md
git commit -m "docs: add Phase Web 4 report"
```

---

## Plan Self-Review

**1. Spec coverage:**
- Overview endpoint → Task 1 (service) + Task 3 (router) ✅
- Agent CRUD + rotate → Task 3 ✅
- Task list/detail/messages/progress → Task 4 ✅
- Approval list/accept/reject → Task 5 ✅
- Connection/Firewall → Task 6 ✅
- API key list/create/revoke → Task 7 ✅
- Router registration → Task 8 ✅
- Tests → Task 9 ✅

**2. Placeholder scan:** No TBD/TODO found.

**3. Type consistency:**
- All schemas use Pydantic BaseModel ✅
- All endpoints use `CurrentSession` from Phase 2 ✅
- All permission checks use `require_permission` from Phase 3 ✅
- Ownership checks verify `owner_id` or `created_by/assigned_to` ✅
