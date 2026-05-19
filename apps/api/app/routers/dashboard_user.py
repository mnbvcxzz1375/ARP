"""User Dashboard API endpoints."""
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from sqlalchemy import select
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
from app.models.audit_log import AuditLog
from app.schemas.dashboard import (
    OverviewResponse,
    AgentListItem, AgentListResponse, CreateAgentRequest,
    UpdateAgentRequest, AgentDetailResponse,
)
from app.services.dashboard_service import get_overview_kpis, get_agent_online_status
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

router = APIRouter(prefix="/v1/dashboard", tags=["dashboard-user"])


# ──────────────────────────────────────────────────────────────────
# Overview
# ──────────────────────────────────────────────────────────────────

@router.get("/overview", response_model=OverviewResponse)
async def overview(
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_permission(PERM_READ_OWN_AGENTS)),
):
    return await get_overview_kpis(session, str(ds.user_id))


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
