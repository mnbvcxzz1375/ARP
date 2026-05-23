"""Admin dashboard aggregation: global KPIs, user/agent/task stats."""
import json

from datetime import UTC, datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.agent import Agent
from app.models.task import Task
from app.models.approval import Approval
from app.models.message import Message
from app.models.api_key import ApiKey
from app.models.dashboard_session import DashboardSession
from app.redis import redis_client


async def get_admin_overview_kpis_cached(session: AsyncSession) -> dict:
    """Get admin overview KPIs with Redis snapshot cache (TTL 30s)."""
    cache_key = "dashboard:admin:overview"
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    result = await get_admin_overview_kpis(session)
    await redis_client.setex(cache_key, 30, json.dumps(result, default=str))
    return result


async def get_admin_overview_kpis(session: AsyncSession) -> dict:
    """Get global overview KPIs for admin dashboard."""
    now = datetime.now(UTC)
    one_hour_ago = now - timedelta(hours=1)
    twenty_four_hours_ago = now - timedelta(hours=24)
    seven_days_ago = now - timedelta(days=7)

    # Users
    total_users = (await session.execute(select(func.count(User.id)))).scalar_one()
    disabled_users = (await session.execute(
        select(func.count(User.id)).where(User.is_disabled == True)  # noqa: E712
    )).scalar_one()
    active_users = total_users - disabled_users

    # Agents
    total_agents = (await session.execute(select(func.count(Agent.id)))).scalar_one()

    # Online agents (check Redis presence for all agents)
    agent_ids_result = await session.execute(select(Agent.id))
    all_agent_ids = [str(aid) for aid in agent_ids_result.scalars().all()]
    online_count = 0
    for aid in all_agent_ids:
        if await redis_client.exists(f"ws:presence:{aid}"):
            online_count += 1

    # Active WS connections (count non-revoked dashboard sessions)
    active_ws = (await session.execute(
        select(func.count(DashboardSession.id)).where(
            DashboardSession.revoked_at.is_(None),
            DashboardSession.expires_at > now,
        )
    )).scalar_one()

    # Tasks
    tasks_1h = (await session.execute(
        select(func.count(Task.id)).where(Task.created_at >= one_hour_ago)
    )).scalar_one()
    tasks_24h = (await session.execute(
        select(func.count(Task.id)).where(Task.created_at >= twenty_four_hours_ago)
    )).scalar_one()
    tasks_7d = (await session.execute(
        select(func.count(Task.id)).where(Task.created_at >= seven_days_ago)
    )).scalar_one()
    failed_tasks = (await session.execute(
        select(func.count(Task.id)).where(
            Task.status == "failed",
            Task.updated_at >= twenty_four_hours_ago,
        )
    )).scalar_one()
    expired_tasks = (await session.execute(
        select(func.count(Task.id)).where(Task.status == "expired")
    )).scalar_one()

    # Pending approvals
    pending_approvals = (await session.execute(
        select(func.count(Approval.id)).where(Approval.status == "pending")
    )).scalar_one()

    # Pending messages
    pending_messages = (await session.execute(
        select(func.count(Message.id)).where(Message.delivery_status == "delivered")
    )).scalar_one()

    return {
        "total_users": total_users,
        "active_users": active_users,
        "disabled_users": disabled_users,
        "total_agents": total_agents,
        "online_agents": online_count,
        "active_ws_connections": active_ws,
        "tasks_1h": tasks_1h,
        "tasks_24h": tasks_24h,
        "tasks_7d": tasks_7d,
        "failed_tasks": failed_tasks,
        "expired_tasks": expired_tasks,
        "pending_approvals": pending_approvals,
        "pending_messages": pending_messages,
        "retry_worker_health": "not_configured",
        "timeout_worker_health": "not_configured",
        "api_5xx_rate": "not_configured",
    }


async def get_user_stats(session: AsyncSession, user_id: str, since: datetime | None = None) -> dict:
    """Get per-user stats: agents count, active API keys, tasks, failed tasks."""
    cutoff = since or (datetime.now(UTC) - timedelta(hours=24))

    agents_count = (await session.execute(
        select(func.count(Agent.id)).where(Agent.owner_id == user_id)
    )).scalar_one()

    active_api_keys = (await session.execute(
        select(func.count(ApiKey.id)).where(
            ApiKey.user_id == user_id,
            ApiKey.is_revoked == False,  # noqa: E712
        )
    )).scalar_one()

    tasks_24h = (await session.execute(
        select(func.count(Task.id)).where(
            Task.created_by.in_(
                select(Agent.id).where(Agent.owner_id == user_id)
            ),
            Task.created_at >= cutoff,
        )
    )).scalar_one()

    failed_tasks_24h = (await session.execute(
        select(func.count(Task.id)).where(
            Task.created_by.in_(
                select(Agent.id).where(Agent.owner_id == user_id)
            ),
            Task.status == "failed",
            Task.updated_at >= cutoff,
        )
    )).scalar_one()

    return {
        "agents_count": agents_count,
        "active_api_keys_count": active_api_keys,
        "tasks_24h": tasks_24h,
        "failed_tasks_24h": failed_tasks_24h,
    }


async def get_agent_stats(session: AsyncSession, agent_id: str) -> dict:
    """Get per-agent stats: tasks_24h, failed_tasks_24h."""
    cutoff = datetime.now(UTC) - timedelta(hours=24)

    tasks_24h = (await session.execute(
        select(func.count(Task.id)).where(
            (Task.created_by == agent_id) | (Task.assigned_to == agent_id),
            Task.created_at >= cutoff,
        )
    )).scalar_one()

    failed_tasks_24h = (await session.execute(
        select(func.count(Task.id)).where(
            (Task.created_by == agent_id) | (Task.assigned_to == agent_id),
            Task.status == "failed",
            Task.updated_at >= cutoff,
        )
    )).scalar_one()

    return {
        "tasks_24h": tasks_24h,
        "failed_tasks_24h": failed_tasks_24h,
    }


async def get_system_health(session: AsyncSession) -> dict:
    """Get system health summary. NEVER exposes secrets."""
    # DB health
    try:
        await session.execute(select(1))
        db_health = "ok"
    except Exception:
        db_health = "down"

    # Redis health
    try:
        await redis_client.ping()
        redis_health = "ok"
    except Exception:
        redis_health = "down"

    # Migration revision
    from alembic.runtime.migration import MigrationContext
    from app.database import engine

    try:
        mc = MigrationContext.configure(engine.sync_engine.connect())
        current_rev = mc.get_current_revision()
    except Exception:
        current_rev = "unknown"

    # Worker health (not actually monitored — returns not_configured)
    retry_health = "not_configured"
    timeout_health = "not_configured"

    # Pending queue length
    pending_queue = (await session.execute(
        select(func.count(Message.id)).where(Message.delivery_status == "pending")
    )).scalar_one()

    return {
        "api_health": "ok",
        "db_health": db_health,
        "redis_health": redis_health,
        "migration_revision": current_rev,
        "app_version": "0.1.0",
        "retry_worker_health": retry_health,
        "timeout_worker_health": timeout_health,
        "pending_queue_length": pending_queue,
        "https_wss_staging": "not_configured",
    }
