from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.exceptions import DomainException
from app.models.egress_gateway import EgressGateway
from app.models.user import User
from app.protocol.constants import ErrorCode
from app.schemas.agent import PublicKeys
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
    public_keys: PublicKeys | None = Field(
        default=None,
        description=(
            "Published E2EE public keys: {'kem': base64 X25519, 'sig': base64 "
            "Ed25519, 'v': 1}. Omit for a plaintext-only (legacy) agent."
        ),
    )


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
    public_keys: PublicKeys | None = Field(
        default=None,
        description="Published E2EE public keys, if the agent registered any.",
    )
    egress_gateway_id: str | None = Field(
        default=None,
        description="Egress gateway this agent must route external requests through, if any.",
    )


class UpdateAgentRequest(BaseModel):
    """Request body for PATCH /v1/agents/{id}.

    The agent↔gateway binding is the egress policy attachment point:
    binding an agent to a gateway forces all of its permitted external
    traffic through the egress policy decision point. Omit the field to
    leave the binding unchanged; send explicit null to unbind (which
    fails the adapter closed — no external access at all).
    """

    egress_gateway_id: UUID | None = Field(
        default=None,
        description="Bind (UUID) or unbind (null) this agent's egress gateway.",
    )


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
        public_keys=(
            body.public_keys.model_dump() if body.public_keys is not None else None
        ),
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
        public_keys=agent.public_keys,
        egress_gateway_id=str(agent.egress_gateway_id) if agent.egress_gateway_id else None,
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
                public_keys=a.public_keys,
                egress_gateway_id=str(a.egress_gateway_id) if a.egress_gateway_id else None,
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
        public_keys=agent.public_keys,
        egress_gateway_id=str(agent.egress_gateway_id) if agent.egress_gateway_id else None,
    )


@router.patch(
    "/{agent_id}",
    response_model=AgentResponse,
    summary="Update an agent",
    description=(
        "Bind or unbind an agent's egress gateway. Binding forces the agent's "
        "external requests through the egress policy decision point "
        "(default deny); unbinding leaves it fail closed (no external access). "
        "Omit egress_gateway_id to leave the binding unchanged, send null to unbind."
    ),
)
async def update_agent_endpoint(
    agent_id: str,
    body: UpdateAgentRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(authenticate),
):
    from uuid import UUID

    agent = await get_agent_by_id(session, UUID(agent_id), user)
    updates = body.model_dump(exclude_unset=True)
    if "egress_gateway_id" in updates:
        gateway_id = updates["egress_gateway_id"]
        if gateway_id is not None:
            gateway = await session.get(EgressGateway, gateway_id)
            if gateway is None:
                raise DomainException(
                    ErrorCode.RESOURCE_NOT_FOUND,
                    f"Egress gateway {gateway_id} not found",
                    status_code=404,
                )
            if not gateway.enabled:
                raise DomainException(
                    ErrorCode.INVALID_REQUEST,
                    f"Egress gateway {gateway_id} is disabled",
                    status_code=400,
                )
        agent.egress_gateway_id = gateway_id
    await session.commit()
    await session.refresh(agent)
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
        public_keys=agent.public_keys,
        egress_gateway_id=str(agent.egress_gateway_id) if agent.egress_gateway_id else None,
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
