"""Admin Dashboard API endpoints — platform-wide visibility and controls."""
import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status as http_status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies.auth import CurrentSession
from app.dependencies.csrf import require_csrf
from app.dependencies.rbac import require_permission, require_high_risk, require_step_up
from app.exceptions import DomainException
from app.protocol.constants import ErrorCode
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
    get_admin_overview_kpis_cached,
    get_user_stats,
    get_agent_stats,
    get_system_health,
)
from app.services.dashboard_service import (
    get_task_delivery_info,
    get_tasks_delivery_info_batch,
    get_task_owner_username,
    mask_secrets_obj,
)
from app.services.audit_service import write_audit
from app.services.rbac_service import (
    has_permission, has_step_up,
    PERM_READ_GLOBAL_OVERVIEW, PERM_READ_GLOBAL_USERS,
    PERM_READ_GLOBAL_AGENTS, PERM_READ_GLOBAL_TASKS,
    PERM_READ_GLOBAL_TASK_DETAIL, PERM_READ_AUDIT_LOGS,
    PERM_CANCEL_PENDING_TASK,
    PERM_EXPORT_AUDIT, PERM_DISABLE_USER, PERM_DISABLE_AGENT,
    PERM_CANCEL_RUNNING_TASK, PERM_FORCE_REVOKE_KEYS,
    PERM_READ_SYSTEM, PERM_APPROVE_ACCESS_REQUEST,
)
from app.services.dashboard_session_service import revoke_all_sessions
from app.services.access_request_service import (
    list_access_requests,
    approve_access_request,
    reject_access_request,
)
from app.models.access_request import AccessRequest
from app.schemas.access_request import (
    AccessRequestListResponse,
    AccessRequestListItem,
    AccessRequestDetailResponse,
    ApproveAccessRequestBody,
    RejectAccessRequestBody,
    ApproveAccessRequestResponse,
    RejectAccessRequestResponse,
)

router = APIRouter(
    prefix="/v1/dashboard/admin",
    tags=["dashboard-admin"],
    dependencies=[Depends(require_csrf)],
)


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
    kpis = await get_admin_overview_kpis_cached(session)
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

    await write_audit(
        session,
        actor_type="user",
        actor_id=str(ds.user_id),
        action="dashboard.admin.read_user",
        resource_type="user",
        resource_id=str(user.id),
    )
    await session.flush()

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
    _: None = Depends(require_high_risk(PERM_DISABLE_USER)),
):
    """Disable or re-enable a user. Requires super_admin + step-up."""
    result = await session.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="User not found")

    is_disabled = body.get("is_disabled", True)
    user.is_disabled = is_disabled

    audit_details: dict = {"is_disabled": is_disabled}
    if is_disabled:
        revoked_sessions = await revoke_all_sessions(
            session, uuid.UUID(user_id), reason="user_disabled",
        )
        audit_details["revoked_sessions"] = revoked_sessions

    await write_audit(
        session,
        actor_type="user",
        actor_id=str(ds.user_id),
        action="dashboard.admin.disable_user",
        resource_type="user",
        resource_id=str(user.id),
        details=audit_details,
    )

    await session.commit()
    return {"user_id": str(user.id), "is_disabled": user.is_disabled}


@router.post("/users/{user_id}/force-revoke-keys")
async def force_revoke_keys(
    user_id: str,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_high_risk(PERM_FORCE_REVOKE_KEYS)),
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

    revoked_sessions = await revoke_all_sessions(
        session, uuid.UUID(user_id), reason="force_revoke_keys",
    )

    await write_audit(
        session,
        actor_type="user",
        actor_id=str(ds.user_id),
        action="dashboard.admin.force_revoke_keys",
        resource_type="user",
        resource_id=str(user.id),
        details={"revoked_keys": revoked_count, "revoked_sessions": revoked_sessions},
    )

    await session.commit()
    return {"user_id": str(user.id), "revoked_keys": revoked_count, "revoked_sessions": revoked_sessions}


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
    if status_filter:
        if status_filter == "online":
            stmt = stmt.where(Agent.status == "online")
        else:
            stmt = stmt.where(Agent.status != "online")

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(Agent.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    agents = list(result.scalars().all())

    items = []
    for a in agents:
        stats = await get_agent_stats(session, str(a.id))
        items.append(AdminAgentListItem(
            agent_id=str(a.id),
            agent_number=a.agent_number,
            owner_username=a.owner.username if a.owner else "unknown",
            name=a.name,
            status="online" if a.status == "online" else "offline",
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

    await write_audit(
        session,
        actor_type="user",
        actor_id=str(ds.user_id),
        action="dashboard.admin.read_agent",
        resource_type="agent",
        resource_id=str(agent.id),
    )
    await session.flush()

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
    _: None = Depends(require_high_risk(PERM_DISABLE_AGENT)),
):
    """Disable or re-enable an agent. Requires super_admin + step-up."""
    result = await session.execute(select(Agent).where(Agent.id == uuid.UUID(agent_id)))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Agent not found")

    # Set status to offline to disable
    agent.status = body.get("status", "offline")

    await write_audit(
        session,
        actor_type="user",
        actor_id=str(ds.user_id),
        action="dashboard.admin.disable_agent",
        resource_type="agent",
        resource_id=str(agent.id),
        details={"status": body.get("status", "offline")},
    )

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
    task_ids = [t.id for t in tasks]
    delivery_info = await get_tasks_delivery_info_batch(session, task_ids)

    for t in tasks:
        delivery_status, _rc = delivery_info.get(t.id, ("unknown", 0))
        owner_username = await get_task_owner_username(session, t)
        items.append(AdminTaskListItem(
            task_id=str(t.id),
            status=t.status,
            sender_agent=str(t.created_by) if t.created_by else "",
            target_agent=str(t.assigned_to) if t.assigned_to else "",
            owner_username=owner_username,
            created_at=t.created_at,
            updated_at=t.updated_at,
            error_code=None,
            delivery_status=delivery_status,
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

    auditor_id = str(ds.user_id)
    ds, rc = await get_task_delivery_info(session, task.id)
    owner_username = await get_task_owner_username(session, task)

    await write_audit(
        session,
        actor_type="user",
        actor_id=auditor_id,
        action="dashboard.admin.read_task",
        resource_type="task",
        resource_id=str(task.id),
        task_id=str(task.id),
    )
    await session.flush()

    return AdminTaskDetailResponse(
        task_id=str(task.id),
        status=task.status,
        payload_preview=payload_preview,
        result_preview=result_preview,
        error_message=task.error_message,
        delivery_status=ds,
        retry_count=rc,
        owner_username=owner_username,
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
        # Running tasks require PERM_CANCEL_RUNNING_TASK AND step-up
        if not has_permission(ds.user, PERM_CANCEL_RUNNING_TASK):
            raise DomainException(
                ErrorCode.INVALID_REQUEST,
                "Insufficient permissions to cancel running tasks",
                status_code=http_status.HTTP_403_FORBIDDEN,
            )
        if not has_step_up(ds):
            raise DomainException(
                ErrorCode.STEP_UP_REQUIRED,
                "Step-up authentication required to cancel running tasks",
                status_code=http_status.HTTP_403_FORBIDDEN,
            )

    task.status = "cancelled"

    await write_audit(
        session,
        actor_type="user",
        actor_id=str(ds.user_id),
        action="dashboard.admin.cancel_task",
        resource_type="task",
        resource_id=str(task.id),
        task_id=str(task.id),
    )

    await session.commit()
    return {"task_id": str(task.id), "status": "cancelled"}


_TERMINAL_TASK_STATUSES = frozenset({"completed", "failed", "cancelled", "expired"})


@router.post("/tasks/{task_id}/expire")
async def expire_task(
    task_id: str,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_high_risk(PERM_CANCEL_RUNNING_TASK)),
):
    """Force expire a task. super_admin + step-up only."""
    result = await session.execute(select(Task).where(Task.id == uuid.UUID(task_id)))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Task not found")

    if task.status in _TERMINAL_TASK_STATUSES:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot expire task in '{task.status}' state",
        )

    previous_status = task.status
    task.status = "expired"

    await write_audit(
        session,
        actor_type="user",
        actor_id=str(ds.user_id),
        action="dashboard.admin.expire_task",
        resource_type="task",
        resource_id=str(task.id),
        task_id=str(task.id),
        details={"previous_status": previous_status},
    )

    await session.commit()
    return {"task_id": str(task.id), "status": "expired"}


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
    resource_id: str | None = None,
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
    if resource_id:
        stmt = stmt.where(AuditLog.resource_id == resource_id)

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
            details=log.details,
            created_at=log.created_at,
        ))

    return AuditLogListResponse(audit_logs=items, total=total, offset=offset, limit=limit)


@router.get("/audit-logs/export")
async def export_audit_logs(
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=10000),
    _: None = Depends(require_permission(PERM_EXPORT_AUDIT)),
    __: None = Depends(require_step_up()),
):
    """Export audit logs as JSON with pagination. Requires export permission + step-up."""
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    logs = list(result.scalars().all())

    await write_audit(
        session,
        actor_type="user",
        actor_id=str(ds.user_id),
        action="dashboard.admin.export_audit",
        resource_type="audit_log",
        details={"limit": limit, "offset": offset},
    )
    await session.flush()

    return {
        "total": len(logs),
        "offset": offset,
        "limit": limit,
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


# ──────────────────────────────────────────────────────────────────
# Access Requests
# ──────────────────────────────────────────────────────────────────

@router.get("/access-requests", response_model=AccessRequestListResponse)
async def list_access_requests_admin(
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status_filter: str | None = None,
    _: None = Depends(require_permission(PERM_READ_GLOBAL_USERS)),
):
    """List access requests. Admin-only."""
    requests, total = await list_access_requests(
        session, status_filter=status_filter, offset=offset, limit=limit,
    )
    items = [
        AccessRequestListItem(
            request_id=str(r.id),
            applicant_name=r.applicant_name,
            applicant_email=r.applicant_email,
            organization=r.organization,
            requested_mode=r.requested_mode,
            status=r.status,
            review_notes=r.review_notes,
            created_at=r.created_at,
            reviewed_at=r.reviewed_at,
        )
        for r in requests
    ]
    return AccessRequestListResponse(
        access_requests=items, total=total, offset=offset, limit=limit,
    )


@router.get("/access-requests/{request_id}", response_model=AccessRequestDetailResponse)
async def get_access_request_detail(
    request_id: str,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_permission(PERM_READ_GLOBAL_USERS)),
):
    """Get full detail of a single access request. Admin-only."""
    try:
        req_uuid = uuid.UUID(request_id)
    except ValueError:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid request ID format",
        )

    result = await session.execute(select(AccessRequest).where(AccessRequest.id == req_uuid))
    ar = result.scalar_one_or_none()
    if ar is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Access request not found",
        )

    return AccessRequestDetailResponse(
        request_id=str(ar.id),
        applicant_name=ar.applicant_name,
        applicant_email=ar.applicant_email,
        organization=ar.organization,
        requested_mode=ar.requested_mode,
        use_case=ar.use_case,
        terms_acknowledged=ar.terms_acknowledged,
        status=ar.status,
        review_notes=ar.review_notes,
        reviewed_by=ar.reviewed_by,
        reviewed_at=ar.reviewed_at,
        request_ip=ar.request_ip,
        created_at=ar.created_at,
    )


@router.get("/access-requests/{request_id}/audit-trail", response_model=AuditLogListResponse)
async def get_access_request_audit_trail(
    request_id: str,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    _: None = Depends(require_permission(PERM_READ_AUDIT_LOGS)),
):
    """Fetch audit trail for a single access request."""
    try:
        req_uuid = uuid.UUID(request_id)
    except ValueError:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid request ID format",
        )

    # Verify the access request exists
    ar_result = await session.execute(
        select(AccessRequest).where(AccessRequest.id == req_uuid)
    )
    if ar_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Access request not found",
        )

    stmt = select(AuditLog).where(
        AuditLog.resource_type == "access_request",
        AuditLog.resource_id == request_id,
    ).order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)

    count_stmt = select(func.count()).select_from(
        select(AuditLog).where(
            AuditLog.resource_type == "access_request",
            AuditLog.resource_id == request_id,
        ).subquery()
    )
    total = (await session.execute(count_stmt)).scalar_one()

    result = await session.execute(stmt)
    logs = list(result.scalars().all())

    items = [
        AuditLogListItem(
            audit_id=str(log.id),
            actor_type=log.actor_type,
            actor_id=str(log.actor_id) if log.actor_id else None,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=str(log.resource_id) if log.resource_id else None,
            task_id=str(log.task_id) if log.task_id else None,
            error_code=log.error_code,
            request_ip=log.request_ip,
            details=log.details,
            created_at=log.created_at,
        )
        for log in logs
    ]
    return AuditLogListResponse(audit_logs=items, total=total, offset=offset, limit=limit)


@router.post("/access-requests/{request_id}/approve", response_model=ApproveAccessRequestResponse)
async def approve_request(
    request_id: str,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_high_risk(PERM_APPROVE_ACCESS_REQUEST)),
    body: ApproveAccessRequestBody | None = None,
):
    """Approve an access request. Admin-only."""
    result = await approve_access_request(
        session,
        request_id=uuid.UUID(request_id),
        reviewer_id=str(ds.user_id),
        review_notes=body.review_notes if body else None,
    )
    await session.commit()
    return result


@router.post("/access-requests/{request_id}/reject", response_model=RejectAccessRequestResponse)
async def reject_request(
    request_id: str,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_high_risk(PERM_APPROVE_ACCESS_REQUEST)),
    body: RejectAccessRequestBody = Body(...),
):
    """Reject an access request. Admin-only. Rejection reason is required."""
    ar = await reject_access_request(
        session,
        request_id=uuid.UUID(request_id),
        reviewer_id=str(ds.user_id),
        review_notes=body.review_notes,
    )
    await session.commit()
    return {
        "request_id": str(ar.id),
        "status": ar.status,
        "reviewed_by": ar.reviewed_by,
        "review_notes": ar.review_notes,
    }
