"""Connection API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.exceptions import DomainException
from app.protocol.constants import ErrorCode
from app.models.agent import Agent
from app.models.user import User
from app.schemas.connection import (
    ConnectionAcceptRequest,
    ConnectionRejectRequest,
    ConnectionRequestRequest,
    ConnectionResponse,
    ConnectionListResponse,
)
from app.services.auth import authenticate
from app.services import connection_service

router = APIRouter(prefix="/v1/connections", tags=["connections"])


async def _get_calling_agent(session: AsyncSession, user: User) -> Agent:
    from sqlalchemy import select
    result = await session.execute(
        select(Agent).where(Agent.owner_id == user.id).order_by(Agent.created_at.asc()).limit(1)
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise DomainException(
            ErrorCode.AGENT_NOT_FOUND,
            "User has no agents; create one first",
            status_code=400,
        )
    return agent


@router.post(
    "/request",
    response_model=ConnectionResponse,
    status_code=201,
    summary="Request an agent connection",
    description="Create a pending connection request from the user's first agent to a target Agent Number.",
)
async def request_connection(
    body: ConnectionRequestRequest,
    user: User = Depends(authenticate),
    session: AsyncSession = Depends(get_session),
):
    """Request a connection to another agent."""
    from app.services.routing_service import resolve_agent

    from_agent = await _get_calling_agent(session, user)
    to_agent = await resolve_agent(session, body.to_agent_number)
    conn = await connection_service.create_connection_request(
        session,
        from_agent=from_agent,
        to_agent=to_agent,
        reason=body.reason,
        requested_capabilities=body.requested_capabilities,
        requested_security_modes=body.requested_security_modes,
    )
    return conn


@router.post(
    "/{connection_id}/accept",
    response_model=ConnectionResponse,
    summary="Accept a connection request",
    description="Accept a pending connection request after verifying target agent ownership.",
)
async def accept_connection(
    connection_id: str,
    body: ConnectionAcceptRequest | None = None,
    user: User = Depends(authenticate),
    session: AsyncSession = Depends(get_session),
):
    """Accept a pending connection request."""
    conn = await connection_service.get_connection(session, connection_id)
    # Verify the authenticated user owns the target agent of this connection
    from app.models.agent import Agent
    target = await session.get(Agent, conn.to_agent_id)
    if target is None or target.owner_id != user.id:
        raise DomainException(
            ErrorCode.AGENT_FORBIDDEN,
            "Only the target agent's owner can accept a connection request.",
            status_code=403,
        )
    conn = await connection_service.accept_connection(
        session,
        connection_id,
        allowed_capabilities=body.allowed_capabilities if body else None,
        preferred_security_mode=body.preferred_security_mode if body else None,
        expires_at=body.expires_at if body else None,
    )
    return conn


@router.post(
    "/{connection_id}/reject",
    response_model=ConnectionResponse,
    summary="Reject a connection request",
    description="Reject a pending connection request after verifying target agent ownership.",
)
async def reject_connection(
    connection_id: str,
    body: ConnectionRejectRequest | None = None,
    user: User = Depends(authenticate),
    session: AsyncSession = Depends(get_session),
):
    """Reject a pending connection request."""
    conn = await connection_service.get_connection(session, connection_id)
    # Verify the authenticated user owns the target agent of this connection
    from app.models.agent import Agent
    target = await session.get(Agent, conn.to_agent_id)
    if target is None or target.owner_id != user.id:
        raise DomainException(
            ErrorCode.AGENT_FORBIDDEN,
            "Only the target agent's owner can reject a connection request.",
            status_code=403,
        )
    conn = await connection_service.reject_connection(
        session,
        connection_id,
        reason=body.reason if body else None,
    )
    return conn


@router.get(
    "",
    response_model=ConnectionListResponse,
    summary="List connections",
    description="List connection records for the authenticated user's first agent.",
)
async def list_connections(
    status: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(authenticate),
    session: AsyncSession = Depends(get_session),
):
    """List connections for the current agent."""
    agent = await _get_calling_agent(session, user)
    connections, total = await connection_service.list_connections(
        session,
        str(agent.id),
        status=status,
        offset=offset,
        limit=limit,
    )
    return ConnectionListResponse(
        connections=[ConnectionResponse.model_validate(c) for c in connections],
        total=total,
    )
