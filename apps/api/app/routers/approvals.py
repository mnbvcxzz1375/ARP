"""Approval API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.user import User
from app.models.agent import Agent
from app.models.approval import Approval
from app.schemas.approval import ApprovalResponse, ApprovalListResponse
from app.services.auth import authenticate
from app.services import approval_service
from app.exceptions import DomainException
from app.protocol.constants import ErrorCode

router = APIRouter(prefix="/v1/approvals", tags=["approvals"])


@router.get("", response_model=ApprovalListResponse)
async def list_approvals(
    task_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(authenticate),
    session: AsyncSession = Depends(get_session),
):
    approvals, total = await approval_service.list_approvals(
        session,
        task_id=UUID(task_id) if task_id else None,
        status=status,
        owner_id=user.id,
        offset=offset,
        limit=limit,
    )
    return ApprovalListResponse(
        approvals=[ApprovalResponse.model_validate(a) for a in approvals],
        total=total,
    )


async def _verify_ownership(session: AsyncSession, approval_id: UUID, user: User) -> Approval:
    result = await session.execute(
        select(Approval).where(Approval.id == approval_id)
    )
    approval = result.scalar_one_or_none()
    if approval is None:
        raise DomainException(
            ErrorCode.APPROVAL_REQUIRED,
            f"Approval {approval_id} not found",
            status_code=404,
        )
    agent = await session.get(Agent, approval.agent_id)
    if agent is None:
        raise DomainException(
            ErrorCode.INTERNAL_ERROR,
            f"Agent for approval {approval_id} not found",
            status_code=404,
        )
    if agent.owner_id != user.id:
        raise DomainException(
            ErrorCode.AGENT_FORBIDDEN,
            f"User does not own the agent for approval {approval_id}",
            status_code=403,
        )
    return approval


@router.post("/{approval_id}/accept", response_model=ApprovalResponse)
async def accept_approval(
    approval_id: str,
    user: User = Depends(authenticate),
    session: AsyncSession = Depends(get_session),
):
    await _verify_ownership(session, UUID(approval_id), user)
    approval = await approval_service.accept_approval(session, UUID(approval_id))
    return approval


@router.post("/{approval_id}/reject", response_model=ApprovalResponse)
async def reject_approval(
    approval_id: str,
    user: User = Depends(authenticate),
    session: AsyncSession = Depends(get_session),
):
    await _verify_ownership(session, UUID(approval_id), user)
    approval = await approval_service.reject_approval(session, UUID(approval_id))
    return approval