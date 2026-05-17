from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.user import User
from app.services.agent_service import (
    create_agent,
    delete_agent,
    get_agent_by_id,
    list_agents,
    rotate_agent_token,
)
from app.services.auth import authenticate


router = APIRouter(prefix="/v1/agents", tags=["agents"])


class CreateAgentRequest(BaseModel):
    name: str = Field(min_length=1, max_length=256, description="Human-readable agent name.")
    runtime: str = Field(min_length=1, max_length=64, description="Runtime or framework label.")
    description: str | None = Field(default=None, description="Optional agent description.")
    capabilities: list[str] = Field(
        default_factory=list,
        description="Capability labels advertised by this agent.",
    )
    inbound_policy: str = Field(
        default="request_approval",
        description="Inbound policy: private, contacts_only, request_approval, or public.",
    )
    discoverable: bool = Field(default=False, description="Whether other users can discover this agent.")


class AgentResponse(BaseModel):
    agent_id: str = Field(description="Agent UUID.")
    agent_number: str = Field(description="Opaque Agent Number used for routing.")
    agent_token: str | None = Field(default=None, description="One-time raw agent token when issued.")
    name: str = Field(description="Human-readable agent name.")
    runtime: str = Field(description="Runtime or framework label.")
    description: str | None = Field(default=None, description="Optional agent description.")
    capabilities: list[str] = Field(description="Capability labels advertised by this agent.")
    inbound_policy: str = Field(description="Inbound policy for cross-agent requests.")
    discoverable: bool = Field(description="Whether the agent is discoverable.")
    status: str = Field(description="Current presence status.")


class AgentListResponse(BaseModel):
    agents: list[AgentResponse] = Field(description="Agents on this page.")
    total: int = Field(description="Total matching agents.")
    page: int = Field(description="Current one-based page.")
    page_size: int = Field(description="Requested page size.")


class RotateTokenResponse(BaseModel):
    agent_id: str = Field(description="Agent UUID.")
    agent_token: str = Field(description="One-time replacement raw agent token.")


@router.post(
    "",
    response_model=AgentResponse,
    status_code=201,
    summary="Create an agent",
    description=(
        "Register a new agent owned by the authenticated user. The response includes "
        "the one-time raw agent token used for WebSocket connections."
    ),
)
async def create_agent_endpoint(
    body: CreateAgentRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(authenticate),
):
    agent = await create_agent(
        session,
        user,
        name=body.name,
        runtime=body.runtime,
        description=body.description,
        capabilities=body.capabilities,
        inbound_policy=body.inbound_policy,
        discoverable=body.discoverable,
    )
    raw_token = getattr(agent, "_raw_token", None)
    await session.commit()
    return AgentResponse(
        agent_id=str(agent.id),
        agent_number=agent.agent_number,
        agent_token=raw_token,
        name=agent.name,
        runtime=agent.runtime,
        description=agent.description,
        capabilities=agent.capabilities,
        inbound_policy=agent.inbound_policy,
        discoverable=agent.discoverable,
        status=agent.status,
    )


@router.get(
    "",
    response_model=AgentListResponse,
    summary="List agents",
    description="List the authenticated user's agents with pagination, status filtering, and search.",
)
async def list_agents_endpoint(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(authenticate),
):
    agents, total = await list_agents(
        session,
        user,
        page=page,
        page_size=page_size,
        status_filter=status,
        search=search,
    )
    return AgentListResponse(
        agents=[
            AgentResponse(
                agent_id=str(a.id),
                agent_number=a.agent_number,
                name=a.name,
                runtime=a.runtime,
                description=a.description,
                capabilities=a.capabilities,
                inbound_policy=a.inbound_policy,
                discoverable=a.discoverable,
                status=a.status,
            )
            for a in agents
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{agent_id}",
    response_model=AgentResponse,
    summary="Get an agent",
    description="Return one agent owned by the authenticated user.",
)
async def get_agent_endpoint(
    agent_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(authenticate),
):
    from uuid import UUID

    agent = await get_agent_by_id(session, UUID(agent_id), user)
    return AgentResponse(
        agent_id=str(agent.id),
        agent_number=agent.agent_number,
        name=agent.name,
        runtime=agent.runtime,
        description=agent.description,
        capabilities=agent.capabilities,
        inbound_policy=agent.inbound_policy,
        discoverable=agent.discoverable,
        status=agent.status,
    )


@router.post(
    "/{agent_id}/rotate-token",
    response_model=RotateTokenResponse,
    summary="Rotate an agent token",
    description=(
        "Revoke the existing active token for an agent and issue a replacement. "
        "The raw replacement token is shown only in this response."
    ),
)
async def rotate_token_endpoint(
    agent_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(authenticate),
):
    from uuid import UUID

    raw_token = await rotate_agent_token(session, UUID(agent_id), user)
    await session.commit()
    return RotateTokenResponse(agent_id=agent_id, agent_token=raw_token)


@router.delete(
    "/{agent_id}",
    status_code=204,
    summary="Delete an agent",
    description="Delete an agent owned by the authenticated user.",
)
async def delete_agent_endpoint(
    agent_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(authenticate),
):
    from uuid import UUID

    await delete_agent(session, UUID(agent_id), user)
    await session.commit()
