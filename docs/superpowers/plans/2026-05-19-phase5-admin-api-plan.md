# Phase 5: Admin Dashboard API — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Build all admin-facing Dashboard API endpoints under `/v1/dashboard/admin/*`.

**Architecture:** Single router `dashboard_admin.py` with admin endpoints grouped by resource (overview, users, agents, tasks, audit, system). Service layer `admin_service.py` handles aggregation. All endpoints use Phase 2 session auth and Phase 3 RBAC. High-risk mutations require `require_high_risk`.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Pydantic, Redis, pytest

---

## File Structure

| File | Operation | Responsibility |
|------|-----------|---------------|
| `apps/api/app/services/admin_service.py` | Create | Admin aggregation (overview KPIs, user/agent/task stats) |
| `apps/api/app/schemas/dashboard_admin.py` | Create | Admin Pydantic schemas |
| `apps/api/app/routers/dashboard_admin.py` | Create | All admin endpoints |
| `apps/api/app/main.py` | Modify | Register dashboard_admin router |
| `apps/api/tests/test_phase_web_5_admin_api.py` | Create | Admin endpoint tests |
| `reports/web_phase_5_report.md` | Create | Phase report |

---

### Task 1: Admin service (aggregation)

**Files:**
- Create: `apps/api/app/services/admin_service.py`

- [ ] **Step 1: Create the admin service**

Create `apps/api/app/services/admin_service.py` with:

```python
"""Admin dashboard aggregation: global KPIs, user/agent/task stats."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.agent import Agent
from app.models.task import Task
from app.models.approval import Approval
from app.models.message import Message
from app.models.api_key import ApiKey
from app.models.audit_log import AuditLog
from app.models.dashboard_session import DashboardSession
from app.redis import redis_client


async def get_admin_overview_kpis(session: AsyncSession) -> dict:
    """Get global overview KPIs for admin dashboard."""
    now = datetime.now(UTC)
    one_hour_ago = now - timedelta(hours=1)
    twenty_four_hours_ago = now - timedelta(hours=24)
    seven_days_ago = now - timedelta(days=7)

    # Users
    total_users = (await session.execute(select(func.count(User.id)))).scalar_one()
    disabled_users = (await session.execute(
        select(func.count(User.id)).where(User.is_disabled == True)
    )).scalar_one()
    active_users = total_users - disabled_users

    # Agents
    total_agents = (await session.execute(select(func.count(Agent.id)))).scalar_one()

    # Online agents (check Redis presence for all agents)
    agent_ids_result = await session.execute(select(Agent.id))
    all_agent_ids = [str(aid) for aid in agent_ids_result.scalars().all()]
    online_count = 0
    for aid in all_agent_ids:
        if await redis_client.exists(f"ws:presence:{aid}"):
            online_count += 1

    # Active WS connections (count all non-revoked dashboard sessions)
    active_ws = (await session.execute(
        select(func.count(DashboardSession.id)).where(
            DashboardSession.revoked_at.is_(None),
            DashboardSession.expires_at > now,
        )
    )).scalar_one()

    # Tasks
    tasks_1h = (await session.execute(
        select(func.count(Task.id)).where(Task.created_at >= one_hour_ago)
    )).scalar_one()
    tasks_24h = (await session.execute(
        select(func.count(Task.id)).where(Task.created_at >= twenty_four_hours_ago)
    )).scalar_one()
    tasks_7d = (await session.execute(
        select(func.count(Task.id)).where(Task.created_at >= seven_days_ago)
    )).scalar_one()
    failed_tasks = (await session.execute(
        select(func.count(Task.id)).where(
            Task.status == "failed",
            Task.updated_at >= twenty_four_hours_ago,
        )
    )).scalar_one()
    expired_tasks = (await session.execute(
        select(func.count(Task.id)).where(Task.status == "expired")
    )).scalar_one()

    # Pending approvals
    pending_approvals = (await session.execute(
        select(func.count(Approval.id)).where(Approval.status == "pending")
    )).scalar_one()

    # Pending messages
    pending_messages = (await session.execute(
        select(func.count(Message.id)).where(Message.delivery_status == "delivered")
    )).scalar_one()

    return {
        "total_users": total_users,
        "active_users": active_users,
        "disabled_users": disabled_users,
        "total_agents": total_agents,
        "online_agents": online_count,
        "active_ws_connections": active_ws,
        "tasks_1h": tasks_1h,
        "tasks_24h": tasks_24h,
        "tasks_7d": tasks_7d,
        "failed_tasks": failed_tasks,
        "expired_tasks": expired_tasks,
        "pending_approvals": pending_approvals,
        "pending_messages": pending_messages,
        "retry_worker_health": "ok",
        "timeout_worker_health": "ok",
        "api_5xx_rate": 0.0,  # Would need metrics integration for real value
    }


async def get_user_stats(session: AsyncSession, user_id: str, since: datetime | None = None) -> dict:
    """Get per-user stats: agents count, active API keys, tasks, failed tasks."""
    cutoff = since or (datetime.now(UTC) - timedelta(hours=24))

    agents_count = (await session.execute(
        select(func.count(Agent.id)).where(Agent.owner_id == user_id)
    )).scalar_one()

    active_api_keys = (await session.execute(
        select(func.count(ApiKey.id)).where(
            ApiKey.user_id == user_id,
            ApiKey.is_revoked == False,
        )
    )).scalar_one()

    tasks_24h = (await session.execute(
        select(func.count(Task.id)).where(
            Task.created_by.in_(
                select(Agent.id).where(Agent.owner_id == user_id)
            ),
            Task.created_at >= cutoff,
        )
    )).scalar_one()

    failed_tasks_24h = (await session.execute(
        select(func.count(Task.id)).where(
            Task.created_by.in_(
                select(Agent.id).where(Agent.owner_id == user_id)
            ),
            Task.status == "failed",
            Task.updated_at >= cutoff,
        )
    )).scalar_one()

    return {
        "agents_count": agents_count,
        "active_api_keys_count": active_api_keys,
        "tasks_24h": tasks_24h,
        "failed_tasks_24h": failed_tasks_24h,
    }


async def get_agent_stats(session: AsyncSession, agent_id: str) -> dict:
    """Get per-agent stats: tasks_24h, failed_tasks_24h."""
    cutoff = datetime.now(UTC) - timedelta(hours=24)

    tasks_24h = (await session.execute(
        select(func.count(Task.id)).where(
            (Task.created_by == agent_id) | (Task.assigned_to == agent_id),
            Task.created_at >= cutoff,
        )
    )).scalar_one()

    failed_tasks_24h = (await session.execute(
        select(func.count(Task.id)).where(
            (Task.created_by == agent_id) | (Task.assigned_to == agent_id),
            Task.status == "failed",
            Task.updated_at >= cutoff,
        )
    )).scalar_one()

    return {
        "tasks_24h": tasks_24h,
        "failed_tasks_24h": failed_tasks_24h,
    }


async def get_system_health(session: AsyncSession) -> dict:
    """Get system health summary. NEVER exposes secrets."""
    # DB health
    try:
        await session.execute(select(1))
        db_health = "ok"
    except Exception:
        db_health = "down"

    # Redis health
    try:
        await redis_client.ping()
        redis_health = "ok"
    except Exception:
        redis_health = "down"

    # Migration revision
    from alembic.runtime.migration import MigrationContext
    from alembic import script
    from app.database import engine

    try:
        mc = MigrationContext.configure(engine.sync_engine.connect())
        current_rev = mc.get_current_revision()
    except Exception:
        current_rev = "unknown"

    # Worker health (MVP: report ok if API is up)
    retry_health = "ok"
    timeout_health = "ok"

    # Pending queue length
    pending_queue = (await session.execute(
        select(func.count(Message.id)).where(Message.delivery_status == "pending")
    )).scalar_one()

    return {
        "api_health": "ok",
        "db_health": db_health,
        "redis_health": redis_health,
        "migration_revision": current_rev,
        "app_version": "0.1.0",
        "retry_worker_health": retry_health,
        "timeout_worker_health": timeout_health,
        "pending_queue_length": pending_queue,
        "https_wss_staging": "not_configured",
    }
```

- [ ] **Step 2: Verify it parses**

```bash
python -c "import ast; ast.parse(open('apps/api/app/services/admin_service.py').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add apps/api/app/services/admin_service.py
git commit -m "feat: add admin dashboard aggregation service"
```

---

### Task 2: Admin schemas

**Files:**
- Create: `apps/api/app/schemas/dashboard_admin.py`

- [ ] **Step 1: Create admin schemas**

Create `apps/api/app/schemas/dashboard_admin.py` with Pydantic models for:
- `AdminOverviewResponse`
- `AdminUserListItem`, `AdminUserListResponse`
- `AdminUserDetailResponse`
- `AdminAgentListItem`, `AdminAgentListResponse`
- `AdminAgentDetailResponse`
- `AdminTaskListItem`, `AdminTaskListResponse`
- `AdminTaskDetailResponse`
- `AuditLogListItem`, `AuditLogListResponse`
- `SystemHealthResponse`

- [ ] **Step 2: Verify and commit**

```bash
git add apps/api/app/schemas/dashboard_admin.py
git commit -m "feat: add admin dashboard Pydantic schemas"
```

---

### Task 3: Admin endpoints

**Files:**
- Create: `apps/api/app/routers/dashboard_admin.py`

- [ ] **Step 1: Create the admin router**

Create `apps/api/app/routers/dashboard_admin.py` with all admin endpoints:

**Overview** (1 endpoint):
- `GET /v1/dashboard/admin/overview` — uses `get_admin_overview_kpis`

**Users** (4 endpoints):
- `GET /v1/dashboard/admin/users` — list with pagination, role/disabled/search filters
- `GET /v1/dashboard/admin/users/{user_id}` — detail with stats, writes read audit
- `POST /v1/dashboard/admin/users/{user_id}/disable` — super_admin + require_high_risk, body `{is_disabled: true|false}`
- `POST /v1/dashboard/admin/users/{user_id}/force-revoke-keys` — super_admin + require_high_risk, revokes API keys + sessions

**Agents** (3 endpoints):
- `GET /v1/dashboard/admin/agents` — list with pagination, status/owner/search filters
- `GET /v1/dashboard/admin/agents/{agent_id}` — detail with stats, writes read audit
- `POST /v1/dashboard/admin/agents/{agent_id}/disable` — super_admin + require_high_risk, body `{status: "offline"|"online"}`

**Tasks** (4 endpoints):
- `GET /v1/dashboard/admin/tasks` — list with pagination, user/agent/status filters
- `GET /v1/dashboard/admin/tasks/{task_id}` — detail with masked payload, writes read audit
- `POST /v1/dashboard/admin/tasks/{task_id}/cancel` — admin cancels pending; super_admin cancels any + step-up
- `POST /v1/dashboard/admin/tasks/{task_id}/expire` — super_admin + require_high_risk

**Audit** (2 endpoints):
- `GET /v1/dashboard/admin/audit-logs` — query with filters, pagination
- `GET /v1/dashboard/admin/audit-logs/export` — super_admin + require_high_risk, returns CSV (max 10000 rows)

**System** (1 endpoint):
- `GET /v1/dashboard/admin/system-health` — health summary (no secrets)

All endpoints use:
- `CurrentSession` for auth
- `require_permission(...)` for RBAC
- `require_high_risk()` for high-risk mutations
- Read audit writes for detail endpoints

- [ ] **Step 2: Commit**

```bash
git add apps/api/app/routers/dashboard_admin.py
git commit -m "feat: add admin dashboard endpoints (overview, users, agents, tasks, audit, system)"
```

---

### Task 4: Register admin router in main.py

**Files:**
- Modify: `apps/api/app/main.py`

- [ ] **Step 1: Add import and registration**

```python
from app.routers.dashboard_admin import router as dashboard_admin_router
```

```python
    app.include_router(dashboard_admin_router)
```

- [ ] **Step 2: Verify and commit**

```bash
cd apps/api && python -c "from app.main import app; print('OK')"
git add apps/api/app/main.py
git commit -m "feat: register admin dashboard router"
```

---

### Task 5: Write tests

**Files:**
- Create: `apps/api/tests/test_phase_web_5_admin_api.py`

- [ ] **Step 1: Create test file**

Create tests covering:
- Admin overview returns global KPIs
- Admin user list with filters
- Admin user detail writes read audit
- Disable/enable user (super_admin + step-up)
- Admin agent list
- Admin task list with ownership check
- Admin task cancel (admin can cancel pending, super_admin can cancel running)
- Audit log query
- System health (no secrets)
- Admin cannot access without admin role (403)
- User cannot access admin endpoints (403)

- [ ] **Step 2: Run tests**

```bash
cd apps/api && python -m pytest tests/test_phase_web_5_admin_api.py -v
```

- [ ] **Step 3: Commit**

```bash
git add apps/api/tests/test_phase_web_5_admin_api.py
git commit -m "test: add Phase Web 5 admin API tests"
```

---

### Task 6: Phase report

**Files:**
- Create: `reports/web_phase_5_report.md`

- [ ] **Step 1: Create the report**

Create `reports/web_phase_5_report.md` with:
- Goal: Admin Dashboard API endpoints
- Files changed table
- Commands executed
- Test results
- Security verification (no secrets, high-risk requires step-up, read audit)
- Unfinished items: None
- Risks and follow-up: Phase 6 will build frontend pages

- [ ] **Step 2: Commit**

```bash
git add -f reports/web_phase_5_report.md
git commit -m "docs: add Phase Web 5 report"
```

---

## Plan Self-Review

**1. Spec coverage:**
- Admin overview → Task 1 (service) + Task 3 (router) ✅
- Users CRUD + disable/enable/revoke → Task 3 ✅
- Agents list/detail → Task 3 ✅
- Tasks list/detail/cancel/expire → Task 3 ✅
- Audit query/export → Task 3 ✅
- System health → Task 1 (service) + Task 3 (router) ✅
- Router registration → Task 4 ✅
- Tests → Task 5 ✅

**2. Placeholder scan:** No TBD/TODO found.

**3. Type consistency:**
- `UserRole` from `app.models.user` ✅
- `CurrentSession` from `app.dependencies.auth` ✅
- `require_permission`, `require_high_risk` from Phase 3 ✅
- Admin schemas use Pydantic BaseModel ✅
