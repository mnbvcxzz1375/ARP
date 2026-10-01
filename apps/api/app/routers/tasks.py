"""Task routes: create, get, list, messages."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.exceptions import DomainException
from app.protocol.constants import ErrorCode
from app.schemas.task import CreateTaskRequest, TaskResponse, TaskListResponse
from app.schemas.message import MessageResponse, MessageListResponse
from app.dependencies.auth import authenticate_session_or_key
from app.services.task_service import create_task, get_task, list_tasks
from app.services.message_service import list_task_messages
from app.models.user import User
from app.models.agent import Agent

router = APIRouter(prefix="/v1/tasks", tags=["tasks"])


async def _get_calling_agent(
    session: AsyncSession, user: User, *, agent_number: str | None = None
) -> Agent:
    from sqlalchemy import select
    stmt = select(Agent).where(Agent.owner_id == user.id)
    if agent_number:
        stmt = stmt.where(Agent.agent_number == agent_number)
    else:
        stmt = stmt.order_by(Agent.created_at.asc()).limit(1)
    result = await session.execute(stmt)
    agent = result.scalar_one_or_none()
    if agent is None:
        raise DomainException(
            ErrorCode.AGENT_NOT_FOUND,
            "User has no agents; create one first" if not agent_number
            else f"Agent {agent_number} not found or not owned by user",
            status_code=400,
        )
    return agent


@router.post(
    "",
    response_model=TaskResponse,
    status_code=201,
    summary="Create a task",
    description=(
        "Create an asynchronous task from one owned sender agent to a target Agent Number. "
        "Delivery is routed online immediately or stored for offline delivery."
    ),
)
async def create_task_endpoint(
    body: CreateTaskRequest,
    user: User = Depends(authenticate_session_or_key),
    session: AsyncSession = Depends(get_session),
):
    agent = await _get_calling_agent(session, user, agent_number=body.from_agent_number)
    task = await create_task(
        session,
        from_agent=agent,
        to_agent_number=body.assigned_to,
        idempotency_key=body.idempotency_key,
        payload=body.payload,
        timeliness_mode=body.timeliness_mode or "normal",
        ttl_seconds=body.ttl_seconds,
        deadline_at=body.deadline_at,
        priority=body.priority if body.priority is not None else 0,
        max_retry_count=body.max_retry_count,
        retry_policy=body.retry_policy,
        route_policy_hint=body.route_policy_hint,
    )
    return _task_to_response(task)


@router.get(
    "",
    response_model=TaskListResponse,
    summary="List tasks",
    description="List tasks visible to the authenticated user with optional status filtering.",
)
async def list_tasks_endpoint(
    status: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(authenticate_session_or_key),
    session: AsyncSession = Depends(get_session),
):
    tasks, total = await list_tasks(session, user_id=user.id, status=status, offset=offset, limit=limit)
    return TaskListResponse(
        tasks=[_task_to_response(t) for t in tasks],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Get a task",
    description="Return a task owned by or assigned to an agent owned by the authenticated user.",
)
async def get_task_endpoint(
    task_id: str,
    user: User = Depends(authenticate_session_or_key),
    session: AsyncSession = Depends(get_session),
):
    try:
        tid = uuid.UUID(task_id)
    except ValueError:
        raise DomainException(ErrorCode.TASK_NOT_FOUND, f"Invalid task id: {task_id}", status_code=404)
    task = await get_task(session, tid, owner_id=user.id)
    return _task_to_response(task)


@router.get(
    "/{task_id}/messages",
    response_model=MessageListResponse,
    summary="List task messages",
    description="Return persisted messages for a task after verifying user ownership.",
)
async def get_task_messages_endpoint(
    task_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(authenticate_session_or_key),
    session: AsyncSession = Depends(get_session),
):
    try:
        tid = uuid.UUID(task_id)
    except ValueError:
        raise DomainException(ErrorCode.TASK_NOT_FOUND, f"Invalid task id: {task_id}", status_code=404)
    # Verify ownership before returning messages
    await get_task(session, tid, owner_id=user.id)
    msgs, total = await list_task_messages(session, tid, offset=offset, limit=limit)
    return MessageListResponse(
        messages=[
            MessageResponse(
                message_id=m.message_id,
                task_id=str(m.task_id),
                type=m.type,
                delivery_status=m.delivery_status,
                content=m.content,
                created_at=m.created_at,
                updated_at=m.updated_at,
            )
            for m in msgs
        ],
        total=total,
        offset=offset,
        limit=limit,
    )


def _task_to_response(t) -> TaskResponse:
    return TaskResponse(
        task_id=str(t.id),
        idempotency_key=t.idempotency_key,
        created_by=str(t.created_by) if t.created_by else None,
        assigned_to=str(t.assigned_to) if t.assigned_to else None,
        status=t.status,
        message_id=t.message_id,
        lease_agent_id=str(t.lease_agent_id) if t.lease_agent_id else None,
        lease_expires_at=t.lease_expires_at,
        last_progress_at=t.last_progress_at,
        last_heartbeat_at=t.last_heartbeat_at,
        result=t.result,
        error_message=t.error_message,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


@router.get(
    "/{task_id}/progress",
    summary="List task progress",
    description="Return historical progress entries for a task after verifying user ownership.",
)
async def get_task_progress_endpoint(
    task_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    user: "User" = Depends(authenticate_session_or_key),
    session: AsyncSession = Depends(get_session),
):
    from app.services.task_service import list_task_progress
    from app.schemas.task import TaskProgressResponse, TaskProgressListResponse
    try:
        tid = uuid.UUID(task_id)
    except ValueError:
        raise DomainException(ErrorCode.TASK_NOT_FOUND, f"Invalid task id: {task_id}", status_code=404)
    # Verify ownership before returning progress
    await get_task(session, tid, owner_id=user.id)
    entries, total = await list_task_progress(session, tid, offset=offset, limit=limit)
    return TaskProgressListResponse(
        entries=[
            TaskProgressResponse(
                id=str(e.id),
                task_id=str(e.task_id),
                seq=e.seq,
                status=e.status,
                progress_pct=e.progress_pct,
                message=e.message,
                data=e.data,
                created_at=e.created_at,
            )
            for e in entries
        ],
        total=total,
    )
