"""Bounded, owner-scoped traffic aggregates for the six-island viewport."""
from datetime import UTC, datetime, timedelta
from sqlalchemy import case, func, or_, select, union_all
from app.models.task import Task

ACTIVE = ("created", "queued", "delivered", "accepted", "running", "awaiting_approval")
FAILURE = ("failed", "expired", "rejected")
WAITING = ("created", "queued", "delivered", "accepted")
COUNTERS = ("running", "queued", "awaiting_approval", "failed_24h")

def _counts(status, updated, cutoff):
    return [
        func.sum(case((status == "running", 1), else_=0)).label("running"),
        func.sum(case((status.in_(WAITING), 1), else_=0)).label("queued"),
        func.sum(case((status == "awaiting_approval", 1), else_=0)).label("awaiting_approval"),
        func.sum(case((status.in_(FAILURE) & (updated >= cutoff), 1), else_=0)).label("failed_24h"),
    ]

def _numbers(row):
    return {k: int(row[k] or 0) for k in COUNTERS}

async def get_task_traffic(session, agent_ids):
    now = datetime.now(UTC)
    cutoff = now - timedelta(hours=24)
    eligible = or_(Task.status.in_(ACTIVE),
                   Task.status.in_(FAILURE) & (Task.updated_at >= cutoff))
    route_query = select(
        Task.created_by.label("source"), Task.assigned_to.label("target"),
        *_counts(Task.status, Task.updated_at, cutoff),
        func.max(Task.updated_at).label("revision"),
    ).where(
        Task.created_by.in_(agent_ids), Task.assigned_to.in_(agent_ids),
        Task.created_by != Task.assigned_to, eligible,
    ).group_by(Task.created_by, Task.assigned_to)
    rows = (await session.execute(route_query)).mappings().all()
    routes = [
        {"from": str(r["source"]), "to": str(r["target"]), **_numbers(r),
         "revision": r["revision"].isoformat()} for r in rows
    ]
    routes.sort(key=lambda r: (-r["failed_24h"], -r["running"], -r["queued"], r["from"], r["to"]))
    # Per-agent totals include permitted external counterparts; their identities
    # are not returned. Self-tasks count once rather than twice.
    involved = union_all(
        select(Task.created_by.label("agent_id"), Task.status, Task.updated_at)
        .where(Task.created_by.in_(agent_ids), eligible),
        select(Task.assigned_to.label("agent_id"), Task.status, Task.updated_at)
        .where(Task.assigned_to.in_(agent_ids), eligible,
               or_(Task.created_by != Task.assigned_to, Task.created_by.is_(None))),
    ).subquery()
    counts = (await session.execute(select(
        involved.c.agent_id, *_counts(involved.c.status, involved.c.updated_at, cutoff),
    ).group_by(involved.c.agent_id))).mappings().all()
    by_id = {str(r["agent_id"]): _numbers(r) for r in counts}
    agents = [{"agent_id": str(a), **by_id.get(str(a), {k: 0 for k in COUNTERS})} for a in agent_ids]
    return {"agents": agents, "routes": routes, "failure_window_hours": 24,
            "generated_at": now.isoformat()}
