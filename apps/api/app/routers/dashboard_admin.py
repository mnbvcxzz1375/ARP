"""Admin Dashboard API endpoints — platform-wide visibility and controls."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies.auth import CurrentSession
from app.dependencies.rbac import require_permission, require_high_risk
from app.models.user import User
from app.models.agent import Agent
from app.models.task import Task
from app.models.message import Message
from app.models.api_key import ApiKey
from app.models.dashboard_session import DashboardSession
from app.models.audit_log import AuditLog
from app.schemas.dashboard_admin import (
    AdminOverviewResponse,
    AdminUserListItem, AdminUserListResponse, AdminUserDetailResponse,
    AdminAgentListItem, AdminAgentListResponse, AdminAgentDetailResponse,
    AdminTaskListItem, AdminTaskListResponse, AdminTaskDetailResponse,
    AuditLogListItem, AuditLogListResponse,
    SystemHealthResponse,
)
from app.services.admin_service import (
    get_admin_overview_kpis,
    get_user_stats,
    get_agent_stats,
    get_system_health,
)
from app.services.rbac_service import (
    PERM_READ_GLOBAL_OVERVIEW, PERM_READ_GLOBAL_USERS,
    PERM_READ_GLOBAL_AGENTS, PERM_READ_GLOBAL_TASKS,
    PERM_READ_GLOBAL_TASK_DETAIL, PERM_READ_AUDIT_LOGS,
    PERM_CANCEL_PENDING_TASK,
    PERM_EXPORT_AUDIT, PERM_DISABLE_USER, PERM_DISABLE_AGENT,
    PERM_CANCEL_RUNNING_TASK, PERM_FORCE_REVOKE_KEYS,
    PERM_READ_SYSTEM,
)

router = APIRouter(prefix="/v1/dashboard/admin", tags=["dashboard-admin"])


# ──────────────────────────────────────────────────────────────────
# Admin Overview
# ──────────────────────────────────────────────────────────────────

@router.get("/overview", response_model=AdminOverviewResponse)
async def admin_overview(
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_permission(PERM_READ_GLOBAL_OVERVIEW)),
):
    """Platform-wide KPIs: users, agents, tasks, worker health."""
    kpis = await get_admin_overview_kpis(session)
    return AdminOverviewResponse(**kpis)


# ──────────────────────────────────────────────────────────────────
# Admin Users
# ──────────────────────────────────────────────────────────────────

@router.get("/users", response_model=AdminUserListResponse)
async def list_users(
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    role_filter: str | None = None,
    search: str | None = None,
    _: None = Depends(require_permission(PERM_READ_GLOBAL_USERS)),
):
    """List all users with per-user stats."""
    stmt = select(User)
    if role_filter:
        stmt = stmt.where(User.role == role_filter)
    if search:
        stmt = stmt.where(User.username.ilike(f"%{search}%"))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(User.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    users = list(result.scalars().all())

    items = []
    for u in users:
        stats = await get_user_stats(session, str(u.id))
        items.append(AdminUserListItem(
            user_id=str(u.id),
            username=u.username,
            role=u.role,
            is_disabled=u.is_disabled,
            agents_count=stats["agents_count"],
            active_api_keys_count=stats["active_api_keys_count"],
            tasks_24h=stats["tasks_24h"],
            failed_tasks_24h=stats["failed_tasks_24h"],
            created_at=u.created_at,
        ))

    return AdminUserListResponse(users=items, total=total, offset=offset, limit=limit)


@router.get("/users/{user_id}", response_model=AdminUserDetailResponse)
async def get_user_detail(
    user_id: str,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_permission(PERM_READ_GLOBAL_USERS)),
):
    """Detailed view of a single user."""
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid user ID format",
        )

    result = await session.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="User not found")

    stats = await get_user_stats(session, str(user.id))

    recent_audit = (await session.execute(
        select(func.count(AuditLog.id)).where(AuditLog.actor_id == str(user_uuid))
    )).scalar_one()

    active_sessions = (await session.execute(
        select(func.count(DashboardSession.id)).where(
            DashboardSession.user_id == user_uuid,
            DashboardSession.revoked_at.is_(None),
        )
    )).scalar_one()

    return AdminUserDetailResponse(
        user_id=str(user.id),
        username=user.username,
        role=user.role,
        is_disabled=user.is_disabled,
        created_at=user.created_at,
        agents_count=stats["agents_count"],
        active_api_keys_count=stats["active_api_keys_count"],
        tasks_24h=stats["tasks_24h"],
        failed_tasks_24h=stats["failed_tasks_24h"],
        recent_audit_count=recent_audit,
        active_sessions_count=active_sessions,
    )


@router.post("/users/{user_id}/disable", status_code=200)
async def disable_user(
    user_id: str,
    body: dict,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_high_risk()),
):
    """Disable or re-enable a user. Requires super_admin + step-up."""
    result = await session.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_disabled = body.get("is_disabled", True)
    await session.commit()
    return {"user_id": str(user.id), "is_disabled": user.is_disabled}


@router.post("/users/{user_id}/force-revoke-keys")
async def force_revoke_keys(
    user_id: str,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_high_risk()),
):
    """Revoke all API keys for a user. Requires super_admin + step-up."""
    result = await session.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="User not found")

    from datetime import UTC, datetime

    keys_result = await session.execute(
        select(ApiKey).where(
            ApiKey.user_id == uuid.UUID(user_id),
            ApiKey.is_revoked == False,  # noqa: E712
        )
    )
    keys = list(keys_result.scalars().all())
    revoked_count = 0
    for k in keys:
        k.is_revoked = True
        k.revoked_at = datetime.now(UTC)
        revoked_count += 1

    await session.commit()
    return {"user_id": str(user.id), "revoked_keys": revoked_count}


# ──────────────────────────────────────────────────────────────────
# Admin Agents
# ──────────────────────────────────────────────────────────────────

@router.get("/agents", response_model=AdminAgentListResponse)
async def list_agents(
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    runtime_filter: str | None = None,
    status_filter: str | None = None,
    search: str | None = None,
    _: None = Depends(require_permission(PERM_READ_GLOBAL_AGENTS)),
):
    """List all agents across all users."""
    stmt = select(Agent)
    if runtime_filter:
        stmt = stmt.where(Agent.runtime == runtime_filter)
    if search:
        stmt = stmt.where(Agent.name.ilike(f"%{search}%"))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(Agent.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    agents = list(result.scalars().all())

    items = []
    for a in agents:
        stats = await get_agent_stats(session, str(a.id))
        status_val = "online" if a.status == "online" else "offline"
        if status_filter and status_val != status_filter:
            continue
        items.append(AdminAgentListItem(
            agent_id=str(a.id),
            agent_number=a.agent_number,
            owner_username=a.owner.username if a.owner else "unknown",
            name=a.name,
            status=status_val,
            runtime=a.runtime,
            inbound_policy=a.inbound_policy,
            discoverable=a.discoverable,
            tasks_24h=stats["tasks_24h"],
            failed_tasks_24h=stats["failed_tasks_24h"],
        ))

    return AdminAgentListResponse(agents=items, total=total, offset=offset, limit=limit)


@router.get("/agents/{agent_id}", response_model=AdminAgentDetailResponse)
async def get_agent_detail(
    agent_id: str,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_permission(PERM_READ_GLOBAL_AGENTS)),
):
    """Detailed view of a single agent."""
    result = await session.execute(select(Agent).where(Agent.id == uuid.UUID(agent_id)))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Agent not found")

    stats = await get_agent_stats(session, str(agent.id))

    token_meta = {}
    from app.models.agent_token import AgentToken
    token_result = await session.execute(
        select(AgentToken).where(
            AgentToken.agent_id == agent.id,
            AgentToken.is_revoked == False,  # noqa: E712
        )
    )
    token = token_result.scalar_one_or_none()
    if token:
        token_meta = {
            "prefix": token.token_prefix,
            "created_at": token.created_at,
            "rotated_at": token.rotated_at,
        }

    return AdminAgentDetailResponse(
        agent_id=str(agent.id),
        agent_number=agent.agent_number,
        owner_username=agent.owner.username if agent.owner else "unknown",
        name=agent.name,
        runtime=agent.runtime,
        status=agent.status,
        inbound_policy=agent.inbound_policy,
        discoverable=agent.discoverable,
        capabilities=agent.capabilities or [],
        token_metadata=token_meta,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
        tasks_24h=stats["tasks_24h"],
        failed_tasks_24h=stats["failed_tasks_24h"],
    )


@router.post("/agents/{agent_id}/disable")
async def disable_agent(
    agent_id: str,
    body: dict,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_high_risk()),
):
    """Disable or re-enable an agent. Requires super_admin + step-up."""
    result = await session.execute(select(Agent).where(Agent.id == uuid.UUID(agent_id)))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Agent not found")

    # Set status to offline to disable
    agent.status = body.get("status", "offline")
    await session.commit()
    return {"agent_id": str(agent.id), "status": agent.status}


# ──────────────────────────────────────────────────────────────────
# Admin Tasks
# ──────────────────────────────────────────────────────────────────

@router.get("/tasks", response_model=AdminTaskListResponse)
async def list_tasks(
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status_filter: str | None = None,
    _: None = Depends(require_permission(PERM_READ_GLOBAL_TASKS)),
):
    """List all tasks across all agents."""
    stmt = select(Task)
    if status_filter:
        stmt = stmt.where(Task.status == status_filter)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(Task.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    tasks = list(result.scalars().all())

    items = []
    for t in tasks:
        items.append(AdminTaskListItem(
            task_id=str(t.id),
            status=t.status,
            sender_agent=str(t.created_by) if t.created_by else "",
            target_agent=str(t.assigned_to) if t.assigned_to else "",
            owner_username="",  # Resolved via subquery if needed
            created_at=t.created_at,
            updated_at=t.updated_at,
            error_code=None,
            delivery_status="delivered",
        ))

    return AdminTaskListResponse(tasks=items, total=total, offset=offset, limit=limit)


@router.get("/tasks/{task_id}", response_model=AdminTaskDetailResponse)
async def get_task_detail(
    task_id: str,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_permission(PERM_READ_GLOBAL_TASK_DETAIL)),
):
    """Detailed view of a single task with payload/result previews."""
    from app.services.dashboard_service import mask_secrets_obj

    result = await session.execute(select(Task).where(Task.id == uuid.UUID(task_id)))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Task not found")

    payload_preview = None
    msg_result = await session.execute(
        select(Message).where(Message.task_id == task.id).order_by(Message.created_at.asc()).limit(1)
    )
    first_msg = msg_result.scalar_one_or_none()
    if first_msg and first_msg.content:
        payload_preview = mask_secrets_obj(first_msg.content)[:500]

    result_preview = None
    if task.result:
        result_preview = mask_secrets_obj(task.result)[:500]

    return AdminTaskDetailResponse(
        task_id=str(task.id),
        status=task.status,
        payload_preview=payload_preview,
        result_preview=result_preview,
        error_message=task.error_message,
        delivery_status="delivered",
        retry_count=0,
        owner_username="",
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_permission(PERM_CANCEL_PENDING_TASK)),
):
    """Cancel a pending or running task. Admin can cancel pending; super_admin can cancel running."""
    result = await session.execute(select(Task).where(Task.id == uuid.UUID(task_id)))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Task not found")

    if task.status not in ("pending", "running"):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel task in '{task.status}' state",
        )

    if task.status == "running":
        # Only super_admin can cancel running tasks
        if ds.user.role != "super_admin":
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail="Only super_admin can cancel running tasks",
            )

    task.status = "cancelled"
    await session.commit()
    return {"task_id": str(task.id), "status": "cancelled"}


# ──────────────────────────────────────────────────────────────────
# Audit Logs
# ──────────────────────────────────────────────────────────────────

@router.get("/audit-logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    actor_type: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    _: None = Depends(require_permission(PERM_READ_AUDIT_LOGS)),
):
    """List audit log entries."""
    stmt = select(AuditLog)
    if actor_type:
        stmt = stmt.where(AuditLog.actor_type == actor_type)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    logs = list(result.scalars().all())

    items = []
    for log in logs:
        items.append(AuditLogListItem(
            audit_id=str(log.id),
            actor_type=log.actor_type,
            actor_id=str(log.actor_id) if log.actor_id else None,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=str(log.resource_id) if log.resource_id else None,
            task_id=str(log.task_id) if log.task_id else None,
            error_code=log.error_code,
            request_ip=log.request_ip,
            created_at=log.created_at,
        ))

    return AuditLogListResponse(audit_logs=items, total=total, offset=offset, limit=limit)


@router.get("/audit-logs/export")
async def export_audit_logs(
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_permission(PERM_EXPORT_AUDIT)),
):
    """Export all audit logs as JSON. Requires super_admin + step-up."""
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
    result = await session.execute(stmt)
    logs = list(result.scalars().all())

    return {
        "total": len(logs),
        "logs": [
            {
                "audit_id": str(log.id),
                "actor_type": log.actor_type,
                "actor_id": str(log.actor_id) if log.actor_id else None,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": str(log.resource_id) if log.resource_id else None,
                "task_id": str(log.task_id) if log.task_id else None,
                "error_code": log.error_code,
                "request_ip": log.request_ip,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ],
    }


# ──────────────────────────────────────────────────────────────────
# System Health
# ──────────────────────────────────────────────────────────────────

@router.get("/system-health", response_model=SystemHealthResponse)
async def system_health(
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_permission(PERM_READ_SYSTEM)),
):
    """Platform health: DB, Redis, workers, migration revision."""
    health = await get_system_health(session)
    return SystemHealthResponse(**health)
