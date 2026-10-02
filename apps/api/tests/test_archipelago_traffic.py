"""Traffic counts must include old active tasks and preserve ownership."""
import uuid
from datetime import UTC, datetime, timedelta
import pytest
from app.models.agent import Agent
from app.models.task import Task
from app.models.user import User
from test_phase_web_4_user_api import dashboard_user, login

async def add_agent(session, owner_id):
    a = Agent(id=uuid.uuid4(), owner_id=owner_id, name="peer", runtime="test",
              agent_number="AN-" + uuid.uuid4().hex[:20], inbound_policy="public")
    session.add(a)
    await session.flush()
    return a

async def test_full_traffic_counts_and_isolation(client, session, dashboard_user):
    user, _, first, key = dashboard_user
    second = await add_agent(session, user.id)
    outsider = User(username="outsider-" + uuid.uuid4().hex)
    session.add(outsider)
    await session.flush()
    foreign = await add_agent(session, outsider.id)
    now = datetime.now(UTC)
    rows = [Task(created_by=first.id, assigned_to=second.id, status="running",
                 created_at=now-timedelta(days=10)) for _ in range(61)]
    rows += [Task(created_by=first.id, assigned_to=second.id, status="completed") for _ in range(75)]
    rows += [Task(created_by=second.id, assigned_to=first.id, status="queued"),
             Task(created_by=first.id, assigned_to=second.id, status="awaiting_approval"),
             Task(created_by=first.id, assigned_to=second.id, status="failed"),
             Task(created_by=first.id, assigned_to=second.id, status="failed", updated_at=now-timedelta(days=3)),
             Task(created_by=first.id, assigned_to=foreign.id, status="running"),
             Task(created_by=first.id, assigned_to=first.id, status="running"),
             Task(created_by=foreign.id, assigned_to=foreign.id, status="running")]
    session.add_all(rows)
    await session.flush()
    assert (await login(client, user.username, key.decode())).status_code == 200
    response = await client.get("/v1/dashboard/task-traffic", params={"agent_ids": f"{first.id},{second.id}"})
    assert response.status_code == 200
    data = response.json()
    forward = next(r for r in data["routes"] if r["from"] == str(first.id) and r["to"] == str(second.id))
    assert forward["running"] == 61
    assert forward["awaiting_approval"] == 1
    assert forward["failed_24h"] == 1
    assert all(r["from"] != str(foreign.id) and r["to"] != str(foreign.id) for r in data["routes"])
    assert all(r["from"] != r["to"] for r in data["routes"])
    own = next(a for a in data["agents"] if a["agent_id"] == str(first.id))
    assert own["running"] == 63  # one external counterpart + self task, once each
    assert (await client.get("/v1/dashboard/task-traffic", params={"agent_ids": str(foreign.id)})).status_code == 404
    assert (await client.get("/v1/dashboard/task-traffic", params={"agent_ids": "not-uuid"})).status_code == 422

async def test_attention_tasks_and_filters(client, session, dashboard_user):
    user, _, first, key = dashboard_user
    second = await add_agent(session, user.id)
    third = await add_agent(session, user.id)
    now = datetime.now(UTC)
    old = Task(created_by=first.id, assigned_to=second.id, status="running", created_at=now-timedelta(days=9))
    session.add(old)
    session.add_all([Task(created_by=first.id, assigned_to=second.id, status="completed") for _ in range(55)])
    session.add(Task(created_by=third.id, assigned_to=third.id, status="running"))
    await session.flush()
    await login(client, user.username, key.decode())
    response = await client.get("/v1/dashboard/tasks", params={"view": "attention", "agent_id": str(second.id), "limit": 50})
    assert response.status_code == 200
    assert response.json()["tasks"][0]["task_id"] == str(old.id)
    assert all(t["sender_agent"] == str(first.id) for t in response.json()["tasks"])
    filtered = await client.get("/v1/dashboard/tasks", params={"view": "active", "search": str(old.id)[:8]})
    assert filtered.json()["total"] == 1
    assert filtered.json()["tasks"][0]["task_id"] == str(old.id)


async def test_auth_bounds_and_oldest_agent_paging(client, session, dashboard_user):
    user, _, first, key = dashboard_user
    assert (await client.get('/v1/dashboard/task-traffic', params={'agent_ids':str(first.id)})).status_code == 401
    now = datetime.now(UTC)
    first.created_at = now-timedelta(days=10)
    second = await add_agent(session, user.id)
    second.created_at = now-timedelta(days=5)
    await session.flush()
    await login(client, user.username, key.decode())
    before = await client.get('/v1/dashboard/agents', params={'page_size':2,'order':'oldest'})
    third = await add_agent(session, user.id)
    third.created_at = now
    await session.flush()
    after = await client.get('/v1/dashboard/agents', params={'page_size':2,'order':'oldest'})
    assert [a['agent_id'] for a in before.json()['agents']] == [a['agent_id'] for a in after.json()['agents']]
    assert after.json()['total'] == 3
    page2 = await client.get('/v1/dashboard/agents', params={'page':2,'page_size':2,'order':'oldest'})
    assert page2.json()['agents'][0]['agent_id'] == str(third.id)
    too_many = ','.join(str(uuid.uuid4()) for _ in range(7))
    assert (await client.get('/v1/dashboard/task-traffic', params={'agent_ids':too_many})).status_code == 422
    assert (await client.get('/v1/dashboard/tasks', params={'view':'invalid'})).status_code == 422
