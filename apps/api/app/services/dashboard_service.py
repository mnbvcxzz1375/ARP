"""Dashboard aggregation: overview KPIs, online status, secret masking."""
import json
import re
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.task import Task
from app.models.approval import Approval
from app.models.message import Message
from app.models.audit_log import AuditLog
from app.redis import redis_client


# Secret patterns to mask in payloads/results
_SECRET_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "***"),
    (re.compile(r"agt_sk_[A-Za-z0-9_-]{20,}"), "***"),
    (re.compile(r"ak_[A-Za-z0-9_-]{20,}"), "***"),
]


def mask_secrets(text: str) -> str:
    """Replace secret-looking patterns with ***."""
    if not text:
        return text
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def mask_secrets_obj(obj: object) -> str:
    """Mask secrets in a JSON-serializable object."""
    return mask_secrets(json.dumps(obj))


async def get_task_delivery_info(
    session: AsyncSession, task_id: uuid.UUID
) -> tuple[str, int]:
    """Query the most recent Message for a task and return (delivery_status, retry_count).

    Returns ("unknown", 0) if no message exists for the task.
    """
    result = await session.execute(
        select(Message)
        .where(Message.task_id == task_id)
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    msg = result.scalar_one_or_none()
    if msg is None:
        return ("unknown", 0)
    return (msg.delivery_status, msg.retry_count)


async def get_tasks_delivery_info_batch(
    session: AsyncSession, task_ids: list[uuid.UUID]
) -> dict[uuid.UUID, tuple[str, int]]:
    """Efficiently batch query delivery info for multiple tasks.

    Returns {task_id: (delivery_status, retry_count)}.
    Tasks with no messages get ("unknown", 0).
    """
    if not task_ids:
        return {}

    result = await session.execute(
        select(Message)
        .where(Message.task_id.in_(task_ids))
        .order_by(Message.created_at.desc())
    )
    messages = result.scalars().all()

    # Keep only the latest message per task (first encountered after DESC sort)
    seen: set[uuid.UUID] = set()
    info_map: dict[uuid.UUID, tuple[str, int]] = {}
    for msg in messages:
        if msg.task_id not in seen:
            seen.add(msg.task_id)
            info_map[msg.task_id] = (msg.delivery_status, msg.retry_count)

    # Fill in missing task_ids with default
    for tid in task_ids:
        if tid not in info_map:
            info_map[tid] = ("unknown", 0)

    return info_map


async def get_agent_owner_username(
    session: AsyncSession, agent_id: uuid.UUID | None
) -> str | None:
    """Return the owner username for a given agent, or None if not found / no owner."""
    if agent_id is None:
        return None

    result = await session.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if agent is None or agent.owner is None:
        return None
    return agent.owner.username


async def get_task_owner_username(session: AsyncSession, task: Task) -> str:
    """Return the owner username from task's created_by or assigned_to agent.

    Tries the created_by agent's owner first, then assigned_to agent's owner.
    Returns "unknown" if neither agent has an owner.
    """
    for agent_id in (task.created_by, task.assigned_to):
        if agent_id is None:
            continue
        result = await session.execute(select(Agent).where(Agent.id == agent_id))
        agent = result.scalar_one_or_none()
        if agent is not None and agent.owner is not None:
            return agent.owner.username
    return "unknown"


async def get_agent_online_status(session: AsyncSession, agent_ids: list[str]) -> dict[str, bool]:
    """Check Redis presence for each agent. Returns {agent_id: is_online}."""
    result = {}
    for aid in agent_ids:
        key = f"ws:presence:{aid}"
        exists = await redis_client.exists(key)
        result[aid] = bool(exists)
    return result


async def get_overview_kpis_cached(session: AsyncSession, user_id: str) -> dict:
    """Get overview KPIs with Redis snapshot cache (TTL 15s)."""
    cache_key = f"dashboard:overview:{user_id}"
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    result = await get_overview_kpis(session, user_id)
    await redis_client.setex(cache_key, 15, json.dumps(result, default=str))
    return result


async def get_overview_kpis(
    session: AsyncSession,
    user_id: str,
) -> dict:
    """Get user overview KPIs: online agents, tasks today, failed tasks, pending approvals."""
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Get user's agent IDs
    agent_result = await session.execute(
        select(Agent.id).where(Agent.owner_id == user_id)
    )
    agent_ids = [str(aid) for aid in agent_result.scalars().all()]

    if not agent_ids:
        return {
            "online_agents": 0,
            "tasks_today": 0,
            "failed_tasks": 0,
            "pending_approvals": 0,
            "pending_messages": 0,
            "recent_tasks": [],
            "recent_approvals": [],
            "recent_agent_status_changes": [],
        }

    # Online agents
    online_status = await get_agent_online_status(session, agent_ids)
    online_count = sum(1 for v in online_status.values() if v)

    # Tasks today
    tasks_today_result = await session.execute(
        select(func.count(Task.id)).where(
            Task.created_by.in_(agent_ids),
            Task.created_at >= today_start,
        )
    )
    tasks_today = tasks_today_result.scalar_one()

    # Failed tasks (last 24h)
    failed_cutoff = now - timedelta(hours=24)
    failed_result = await session.execute(
        select(func.count(Task.id)).where(
            Task.created_by.in_(agent_ids),
            Task.status == "failed",
            Task.updated_at >= failed_cutoff,
        )
    )
    failed_tasks = failed_result.scalar_one()

    # Pending approvals
    pending_result = await session.execute(
        select(func.count(Approval.id)).where(
            Approval.agent_id.in_(agent_ids),
            Approval.status == "pending",
        )
    )
    pending_approvals = pending_result.scalar_one()

    # Pending messages (delivered but not acked)
    pending_msg_result = await session.execute(
        select(func.count(Message.id)).where(
            Message.delivery_status == "delivered",
            Message.task_id.in_(
                select(Task.id).where(Task.created_by.in_(agent_ids))
            ),
        )
    )
    pending_messages = pending_msg_result.scalar_one()

    # Recent tasks (last 10)
    recent_tasks_result = await session.execute(
        select(Task).where(
            (Task.created_by.in_(agent_ids)) | (Task.assigned_to.in_(agent_ids))
        ).order_by(Task.created_at.desc()).limit(10)
    )
    recent_tasks = []
    for t in recent_tasks_result.scalars():
        recent_tasks.append({
            "task_id": str(t.id),
            "status": t.status,
            "created_at": t.created_at,
        })

    # Recent approvals (last 10)
    recent_approvals_result = await session.execute(
        select(Approval).where(
            Approval.agent_id.in_(agent_ids)
        ).order_by(Approval.created_at.desc()).limit(10)
    )
    recent_approvals = []
    for a in recent_approvals_result.scalars():
        recent_approvals.append({
            "approval_id": str(a.id),
            "status": a.status,
            "risk_level": a.risk_level,
            "created_at": a.created_at,
        })

    # Recent agent status changes from audit log
    recent_audit_result = await session.execute(
        select(AuditLog).where(
            AuditLog.resource_type == "agent",
            AuditLog.actor_id.in_(agent_ids),
        ).order_by(AuditLog.created_at.desc()).limit(10)
    )
    recent_agent_changes = []
    for log in recent_audit_result.scalars():
        recent_agent_changes.append({
            "action": log.action,
            "resource_id": log.resource_id,
            "created_at": log.created_at,
        })

    return {
        "online_agents": online_count,
        "tasks_today": tasks_today,
        "failed_tasks": failed_tasks,
        "pending_approvals": pending_approvals,
        "pending_messages": pending_messages,
        "recent_tasks": recent_tasks,
        "recent_approvals": recent_approvals,
        "recent_agent_status_changes": recent_agent_changes,
    }
