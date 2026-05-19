"""User Dashboard API endpoints."""
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies.auth import CurrentSession
from app.dependencies.csrf import require_csrf
from app.dependencies.rbac import require_permission
from app.models.agent import Agent
from app.models.agent_token import AgentToken
from app.models.task import Task
from app.models.message import Message
from app.models.approval import Approval
from app.models.connection import Connection
from app.models.audit_log import AuditLog
from app.schemas.dashboard import (
    OverviewResponse,
    AgentListItem, AgentListResponse, CreateAgentRequest,
    UpdateAgentRequest, AgentDetailResponse,
)
from app.services.dashboard_service import get_overview_kpis_cached, get_agent_online_status
from app.services.agent_service import (
    create_agent as _create_agent_service,
    list_agents as _list_agents_service,
    rotate_agent_token as _rotate_agent_token_service,
    delete_agent as _delete_agent_service,
    get_agent_by_id as _get_agent_by_id_service,
)
from app.services.rbac_service import (
    PERM_READ_OWN_AGENTS, PERM_CREATE_AGENT, PERM_EDIT_OWN_AGENT,
    PERM_DELETE_OWN_AGENT, PERM_ROTATE_OWN_TOKEN,
    PERM_READ_OWN_TASKS, PERM_READ_OWN_TASK_DETAIL,
    PERM_HANDLE_OWN_APPROVAL,
    PERM_MANAGE_OWN_CONNECTIONS, PERM_MANAGE_OWN_FIREWALL,
    PERM_MANAGE_OWN_KEYS,
)

router = APIRouter(
    prefix="/v1/dashboard",
    tags=["dashboard-user"],
    dependencies=[Depends(require_csrf)],
)


# ──────────────────────────────────────────────────────────────────
# Overview
# ──────────────────────────────────────────────────────────────────

@router.get("/overview", response_model=OverviewResponse)
async def overview(
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_permission(PERM_READ_OWN_AGENTS)),
):
    return await get_overview_kpis_cached(session, str(ds.user_id))


# ──────────────────────────────────────────────────────────────────
# Agents
# ──────────────────────────────────────────────────────────────────

@router.get("/agents", response_model=AgentListResponse)
async def list_agents(
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status_filter: str | None = None,
    search: str | None = None,
    _: None = Depends(require_permission(PERM_READ_OWN_AGENTS)),
):
    agents, total = await _list_agents_service(
        session, ds.user, page=page, page_size=page_size,
        status_filter=status_filter, search=search,
    )
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

    return AgentListResponse(agents=items, total=total, offset=page, limit=page_size)


@router.post("/agents", status_code=201)
async def create_agent(
    body: CreateAgentRequest,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_permission(PERM_CREATE_AGENT)),
):
    agent = await _create_agent_service(
        session, ds.user,
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
        "agent_token": getattr(agent, '_raw_token', ''),
        "name": agent.name,
    }


@router.get("/agents/{agent_id}")
async def get_agent_detail(
    agent_id: str,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_permission(PERM_READ_OWN_AGENTS)),
):
    try:
        agent = await _get_agent_by_id_service(session, uuid.UUID(agent_id), ds.user)
    except Exception:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Agent not found")

    token_result = await session.execute(
        select(AgentToken).where(
            AgentToken.agent_id == agent.id,
            AgentToken.is_revoked == False,
        )
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
        status="online",
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
    _: None = Depends(require_permission(PERM_EDIT_OWN_AGENT)),
):
    try:
        agent = await _get_agent_by_id_service(session, uuid.UUID(agent_id), ds.user)
    except Exception:
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
    _: None = Depends(require_permission(PERM_DELETE_OWN_AGENT)),
):
    try:
        await _delete_agent_service(session, uuid.UUID(agent_id), ds.user)
    except Exception:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Agent not found")
    await session.commit()


@router.post("/agents/{agent_id}/rotate-token")
async def rotate_agent_token(
    agent_id: str,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_permission(PERM_ROTATE_OWN_TOKEN)),
):
    try:
        new_token = await _rotate_agent_token_service(session, uuid.UUID(agent_id), ds.user)
    except Exception:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Agent not found")
    await session.commit()
    return {"agent_id": agent_id, "agent_token": new_token}


# ──────────────────────────────────────────────────────────────────
# Tasks
# ──────────────────────────────────────────────────────────────────

@router.get("/tasks")
async def list_tasks(
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status_filter: str | None = None,
    error_code: str | None = None,
    _: None = Depends(require_permission(PERM_READ_OWN_TASKS)),
):
    agent_ids = [str(a.id) for a in ds.user.agents]

    stmt = select(Task).where(
        (Task.created_by.in_(agent_ids)) | (Task.assigned_to.in_(agent_ids))
    )
    if status_filter:
        stmt = stmt.where(Task.status == status_filter)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(Task.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    tasks = list(result.scalars().all())

    items = []
    for t in tasks:
        items.append({
            "task_id": str(t.id),
            "status": t.status,
            "sender_agent": str(t.created_by),
            "target_agent": str(t.assigned_to),
            "created_at": t.created_at,
            "updated_at": t.updated_at,
            "duration_sec": None,
            "error_code": None,
            "delivery_status": "delivered",
        })

    return {"tasks": items, "total": total, "offset": offset, "limit": limit}


@router.get("/tasks/{task_id}")
async def get_task_detail(
    task_id: str,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_permission(PERM_READ_OWN_TASK_DETAIL)),
):
    from app.services.dashboard_service import mask_secrets_obj

    agent_ids = [str(a.id) for a in ds.user.agents]

    result = await session.execute(
        select(Task).where(
            Task.id == uuid.UUID(task_id),
            (Task.created_by.in_(agent_ids)) | (Task.assigned_to.in_(agent_ids)),
        )
    )
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

    return {
        "task_id": str(task.id),
        "status": task.status,
        "payload_preview": payload_preview,
        "result_preview": result_preview,
        "error_message": task.error_message,
        "delivery_status": "delivered",
        "retry_count": 0,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


@router.get("/tasks/{task_id}/messages")
async def get_task_messages(
    task_id: str,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    agent_ids = [str(a.id) for a in ds.user.agents]

    task_check = await session.execute(
        select(Task.id).where(
            Task.id == uuid.UUID(task_id),
            (Task.created_by.in_(agent_ids)) | (Task.assigned_to.in_(agent_ids)),
        )
    )
    if task_check.scalar_one_or_none() is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Task not found")

    stmt = select(Message).where(Message.task_id == uuid.UUID(task_id)).order_by(Message.created_at.asc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    messages = list(result.scalars().all())

    return {
        "messages": [
            {"message_id": m.message_id, "type": m.type, "delivery_status": m.delivery_status, "created_at": m.created_at}
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
    from app.services.task_service import list_task_progress as _list_task_progress

    agent_ids = [str(a.id) for a in ds.user.agents]
    task_check = await session.execute(
        select(Task.id).where(
            Task.id == uuid.UUID(task_id),
            (Task.created_by.in_(agent_ids)) | (Task.assigned_to.in_(agent_ids)),
        )
    )
    if task_check.scalar_one_or_none() is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Task not found")

    entries, total = await _list_task_progress(session, uuid.UUID(task_id), offset=offset, limit=limit)
    return {
        "progress": [
            {"seq": e.seq, "status": e.status, "progress_pct": e.progress_pct, "message": e.message, "created_at": e.created_at}
            for e in entries
        ],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


# ──────────────────────────────────────────────────────────────────
# Approvals
# ──────────────────────────────────────────────────────────────────

@router.get("/approvals")
async def list_approvals(
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status_filter: str | None = None,
    _: None = Depends(require_permission(PERM_HANDLE_OWN_APPROVAL)),
):
    agent_ids = [a.id for a in ds.user.agents]

    stmt = select(Approval).where(Approval.agent_id.in_(agent_ids))
    if status_filter:
        stmt = stmt.where(Approval.status == status_filter)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(Approval.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    approvals = list(result.scalars().all())

    items = []
    for a in approvals:
        items.append({
            "approval_id": str(a.id),
            "type": "task_action",
            "status": a.status,
            "risk_level": a.risk_level,
            "action_kind": a.action_kind,
            "action_preview": a.action_preview,
            "created_at": a.created_at,
        })

    return {"approvals": items, "total": total, "offset": offset, "limit": limit}


@router.post("/approvals/{approval_id}/accept")
async def accept_approval(
    approval_id: str,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_permission(PERM_HANDLE_OWN_APPROVAL)),
):
    from app.services.approval_service import accept_approval as _accept_approval

    agent_ids = [a.id for a in ds.user.agents]
    result = await session.execute(
        select(Approval).where(Approval.id == uuid.UUID(approval_id), Approval.agent_id.in_(agent_ids))
    )
    approval = result.scalar_one_or_none()
    if approval is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Approval not found")

    await _accept_approval(session, approval)
    await session.commit()
    return {"approval_id": str(approval.id), "status": "accepted"}


@router.post("/approvals/{approval_id}/reject")
async def reject_approval(
    approval_id: str,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_permission(PERM_HANDLE_OWN_APPROVAL)),
):
    from app.services.approval_service import reject_approval as _reject_approval

    agent_ids = [a.id for a in ds.user.agents]
    result = await session.execute(
        select(Approval).where(Approval.id == uuid.UUID(approval_id), Approval.agent_id.in_(agent_ids))
    )
    approval = result.scalar_one_or_none()
    if approval is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Approval not found")

    await _reject_approval(session, approval)
    await session.commit()
    return {"approval_id": str(approval.id), "status": "rejected"}


# ──────────────────────────────────────────────────────────────────
# Connections / Firewall
# ──────────────────────────────────────────────────────────────────

@router.get("/connections")
async def get_connections(
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_permission(PERM_MANAGE_OWN_CONNECTIONS)),
):
    agents_info = []
    for agent in ds.user.agents:
        pending = await session.execute(
            select(func.count(Connection.id)).where(Connection.agent_id == agent.id, Connection.status == "pending")
        )
        accepted = await session.execute(
            select(func.count(Connection.id)).where(Connection.agent_id == agent.id, Connection.status == "accepted")
        )
        rejected = await session.execute(
            select(func.count(Connection.id)).where(Connection.agent_id == agent.id, Connection.status == "rejected")
        )
        agents_info.append({
            "agent_id": str(agent.id),
            "agent_number": agent.agent_number,
            "inbound_policy": agent.inbound_policy,
            "pending_requests": pending.scalar_one(),
            "accepted_connections": accepted.scalar_one(),
            "rejected_connections": rejected.scalar_one(),
        })

    agent_ids = [a.id for a in ds.user.agents]
    pending_result = await session.execute(
        select(Connection).where(Connection.agent_id.in_(agent_ids), Connection.status == "pending").order_by(Connection.created_at.desc())
    )
    pending_requests = []
    for c in pending_result.scalars():
        pending_requests.append({
            "connection_id": str(c.id),
            "agent_number": c.agent_number,
            "requester_agent": str(c.requester_agent_id),
            "requested_policy": c.requested_policy or "unknown",
            "created_at": c.created_at,
        })

    return {"agents": agents_info, "pending_requests": pending_requests}


@router.post("/connections/{connection_id}/accept")
async def accept_connection(
    connection_id: str,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_permission(PERM_MANAGE_OWN_CONNECTIONS)),
):
    from app.services.connection_service import accept_connection as _accept_connection

    result = await session.execute(
        select(Connection).where(Connection.id == uuid.UUID(connection_id), Connection.agent_id.in_([a.id for a in ds.user.agents]))
    )
    conn = result.scalar_one_or_none()
    if conn is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Connection not found")

    await _accept_connection(session, conn)
    await session.commit()
    return {"connection_id": str(conn.id), "status": "accepted"}


@router.post("/connections/{connection_id}/reject")
async def reject_connection(
    connection_id: str,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_permission(PERM_MANAGE_OWN_CONNECTIONS)),
):
    from app.services.connection_service import reject_connection as _reject_connection

    result = await session.execute(
        select(Connection).where(Connection.id == uuid.UUID(connection_id), Connection.agent_id.in_([a.id for a in ds.user.agents]))
    )
    conn = result.scalar_one_or_none()
    if conn is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Connection not found")

    await _reject_connection(session, conn)
    await session.commit()
    return {"connection_id": str(conn.id), "status": "rejected"}


@router.patch("/agents/{agent_id}/firewall")
async def update_firewall(
    agent_id: str,
    body: dict,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_permission(PERM_MANAGE_OWN_FIREWALL)),
):
    try:
        agent = await _get_agent_by_id_service(session, uuid.UUID(agent_id), ds.user)
    except Exception:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Agent not found")

    if body.get("inbound_policy") is not None:
        agent.inbound_policy = body["inbound_policy"]

    await session.commit()
    return {"agent_id": str(agent.id), "inbound_policy": agent.inbound_policy}


# ──────────────────────────────────────────────────────────────────
# API Keys
# ──────────────────────────────────────────────────────────────────

@router.get("/api-keys")
async def list_api_keys(
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_permission(PERM_MANAGE_OWN_KEYS)),
):
    from app.services.api_key_service import list_api_keys as _list_api_keys

    keys = await _list_api_keys(session, ds.user)
    return {
        "api_keys": [
            {"api_key_id": str(k.id), "key_prefix": k.key_prefix, "name": k.name,
             "created_at": k.created_at, "expires_at": k.expires_at, "revoked_at": k.revoked_at}
            for k in keys
        ],
        "total": len(keys),
    }


@router.post("/api-keys", status_code=201)
async def create_api_key(
    body: dict,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_permission(PERM_MANAGE_OWN_KEYS)),
):
    from app.services.api_key_service import create_api_key as _create_api_key

    name = body.get("name", "dashboard-key")
    expires_at = body.get("expires_at")
    key, raw = await _create_api_key(session, ds.user, name=name, expires_at=expires_at)
    await session.commit()
    return {"api_key_id": str(key.id), "key_prefix": key.key_prefix, "name": key.name, "expires_at": key.expires_at, "api_key": raw}


@router.post("/api-keys/{api_key_id}/revoke")
async def revoke_api_key(
    api_key_id: str,
    body: dict,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_permission(PERM_MANAGE_OWN_KEYS)),
):
    from app.services.api_key_service import revoke_api_key as _revoke_api_key

    allow_last_key = body.get("allow_last_key", False)
    key = await _revoke_api_key(session, ds.user, uuid.UUID(api_key_id), allow_last_key=allow_last_key)
    await session.commit()
    return {"api_key_id": str(key.id), "key_prefix": key.key_prefix, "name": key.name, "revoked_at": key.revoked_at}
