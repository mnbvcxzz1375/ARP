"""Personal edge relay toggle (strict opt-in) tests.

Verifies the three-state semantics of select_route's ``enable_edge_relay``
parameter:

- ``None`` (legacy callers that have not wired the personal routing
  strategy chain): admission unchanged — personal_edge candidates are
  still built for same-zone routes.
- ``False``: personal_edge candidates are excluded.
- ``True``: personal_edge candidates are admitted (still gated by the
  same-zone constraint and relay health).

Also covers the task_service reading point: the sender's PersonalScope
row is read once per task and passed into select_route; a missing row is
synonymous with enable_edge_relay=False, and only an explicit True is
passed through.
"""

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.network_scope import NetworkScope
from app.models.network_zone import NetworkZone
from app.models.personal_scope import PersonalScope
from app.models.relay_node import RelayNode
from app.models.user import User
from app.services.path_optimizer import select_route


def _candidate_types(decision) -> list[str]:
    return [c["route_type"] for c in decision.candidate_routes]


@pytest.fixture
async def test_user(session: AsyncSession) -> User:
    user = User(username=f"testuser_{uuid.uuid4().hex[:8]}", role="user")
    session.add(user)
    await session.flush()
    return user


@pytest.fixture
async def network_scope(session: AsyncSession, test_user: User) -> NetworkScope:
    scope = NetworkScope(
        user_id=test_user.id,
        scope_name="test-enterprise",
        scope_type="enterprise",
    )
    session.add(scope)
    await session.flush()
    return scope


@pytest.fixture
async def zone(session: AsyncSession, network_scope: NetworkScope) -> NetworkZone:
    zone = NetworkZone(
        scope_id=network_scope.id,
        zone_name="us-west-2",
        zone_type="regional",
        zone_metadata={"region": "us-west-2", "latency_target_ms": 50},
    )
    session.add(zone)
    await session.flush()
    return zone


@pytest.fixture
async def central_relay(session: AsyncSession) -> RelayNode:
    relay = RelayNode(
        node_name="central-relay-1",
        node_type="central",
        status="healthy",
        current_load=0.3,
        queue_depth=5,
        avg_latency_ms=50.0,
        success_rate=0.95,
        capabilities=["websocket", "task_delivery"],
        max_capacity=10000,
        enabled=True,
        last_heartbeat_at=datetime.now(UTC),
    )
    session.add(relay)
    await session.flush()
    return relay


@pytest.fixture
async def edge_relay(session: AsyncSession) -> RelayNode:
    """A healthy personal edge relay with fresh heartbeat."""
    relay = RelayNode(
        node_name="personal-edge-1",
        node_type="personal_edge",
        status="healthy",
        current_load=0.1,
        queue_depth=0,
        avg_latency_ms=10.0,
        success_rate=0.90,
        capabilities=["websocket", "task_delivery"],
        max_capacity=1000,
        enabled=True,
        last_heartbeat_at=datetime.now(UTC),
    )
    session.add(relay)
    await session.flush()
    return relay


@pytest.fixture
async def agent_a(
    session: AsyncSession,
    test_user: User,
    network_scope: NetworkScope,
    zone: NetworkZone,
) -> Agent:
    agent = Agent(
        owner_id=test_user.id,
        agent_number=f"AN-{uuid.uuid4().hex[:12].upper()}",
        name="Agent A",
        runtime="python",
        inbound_policy="public",
        scope_id=network_scope.id,
        zone_id=zone.id,
    )
    session.add(agent)
    await session.flush()
    return agent


@pytest.fixture
async def agent_b(
    session: AsyncSession,
    test_user: User,
    network_scope: NetworkScope,
    zone: NetworkZone,
) -> Agent:
    agent = Agent(
        owner_id=test_user.id,
        agent_number=f"AN-{uuid.uuid4().hex[:12].upper()}",
        name="Agent B",
        runtime="python",
        inbound_policy="public",
        scope_id=network_scope.id,
        zone_id=zone.id,
    )
    session.add(agent)
    await session.flush()
    return agent


async def _make_task(session: AsyncSession, agent_a: Agent, agent_b: Agent):
    from app.models.task import Task

    task = Task(
        created_by=agent_a.id,
        assigned_to=agent_b.id,
        status="created",
    )
    session.add(task)
    await session.flush()
    return task


async def _select(session, task, agent_a, agent_b, **kwargs):
    return await select_route(
        session,
        task=task,
        from_agent=agent_a,
        to_agent=agent_b,
        message_id=f"msg-{uuid.uuid4().hex[:8]}",
        scope_id=agent_a.scope_id,
        source_zone_id=agent_a.zone_id,
        target_zone_id=agent_b.zone_id,
        **kwargs,
    )


@pytest.mark.asyncio
async def test_none_preserves_legacy_admission(
    session: AsyncSession,
    agent_a: Agent,
    agent_b: Agent,
    central_relay: RelayNode,
    edge_relay: RelayNode,
):
    """enable_edge_relay=None (default): legacy admission is unchanged.

    Callers that have not wired the personal routing strategy chain keep
    the pre-toggle behavior: personal_edge candidates are admitted for
    same-zone routes.
    """
    task = await _make_task(session, agent_a, agent_b)
    decision = await _select(session, task, agent_a, agent_b)

    assert "personal_edge" in _candidate_types(decision)
    # Edge relay is faster (10ms vs 50ms), so it wins the score contest.
    assert decision.selected_route_type == "personal_edge"


@pytest.mark.asyncio
async def test_false_excludes_personal_edge(
    session: AsyncSession,
    agent_a: Agent,
    agent_b: Agent,
    central_relay: RelayNode,
    edge_relay: RelayNode,
):
    """enable_edge_relay=False: personal_edge candidates are excluded."""
    task = await _make_task(session, agent_a, agent_b)
    decision = await _select(
        session, task, agent_a, agent_b, enable_edge_relay=False
    )

    assert "personal_edge" not in _candidate_types(decision)
    assert decision.selected_route_type == "central_relay"


@pytest.mark.asyncio
async def test_true_includes_personal_edge(
    session: AsyncSession,
    agent_a: Agent,
    agent_b: Agent,
    central_relay: RelayNode,
    edge_relay: RelayNode,
):
    """enable_edge_relay=True: personal_edge candidates are admitted."""
    task = await _make_task(session, agent_a, agent_b)
    decision = await _select(
        session, task, agent_a, agent_b, enable_edge_relay=True
    )

    assert "personal_edge" in _candidate_types(decision)
    assert decision.selected_route_type == "personal_edge"


@pytest.mark.asyncio
async def test_true_cross_zone_still_excluded(
    session: AsyncSession,
    test_user: User,
    network_scope: NetworkScope,
    zone: NetworkZone,
    central_relay: RelayNode,
    edge_relay: RelayNode,
):
    """The toggle never bypasses the same-zone constraint.

    A cross-zone route cannot traverse a personal edge relay even when the
    sender explicitly opted in.
    """
    other_zone = NetworkZone(
        scope_id=network_scope.id,
        zone_name="us-east-1",
        zone_type="regional",
        zone_metadata={"region": "us-east-1", "latency_target_ms": 50},
    )
    session.add(other_zone)
    await session.flush()

    agent_a = Agent(
        owner_id=test_user.id,
        agent_number=f"AN-{uuid.uuid4().hex[:12].upper()}",
        name="Agent A",
        runtime="python",
        inbound_policy="public",
        scope_id=network_scope.id,
        zone_id=zone.id,
    )
    agent_b = Agent(
        owner_id=test_user.id,
        agent_number=f"AN-{uuid.uuid4().hex[:12].upper()}",
        name="Agent B",
        runtime="python",
        inbound_policy="public",
        scope_id=network_scope.id,
        zone_id=other_zone.id,
    )
    session.add_all([agent_a, agent_b])
    await session.flush()

    task = await _make_task(session, agent_a, agent_b)
    decision = await _select(
        session, task, agent_a, agent_b, enable_edge_relay=True
    )

    assert "personal_edge" not in _candidate_types(decision)
    assert decision.selected_route_type == "central_relay"


@pytest.mark.asyncio
async def test_unhealthy_relay_not_admitted_despite_opt_in(
    session: AsyncSession,
    agent_a: Agent,
    agent_b: Agent,
    central_relay: RelayNode,
):
    """The toggle only relaxes the opt-in gate, never the health gate.

    A personal_edge relay with a stale heartbeat is never admitted even
    when enable_edge_relay=True: the 60s heartbeat window in
    _get_healthy_relays is a precondition that runs before candidate
    construction.

    Asserted per relay id: the shared test database accumulates
    personal_edge rows committed by other suites (worker/API paths that
    commit via their own sessions), so the absence of *any* personal_edge
    candidate cannot be assumed here.
    """
    stale_relay = RelayNode(
        node_name="personal-edge-stale",
        node_type="personal_edge",
        status="healthy",
        current_load=0.1,
        queue_depth=0,
        avg_latency_ms=10.0,
        success_rate=0.90,
        capabilities=["websocket", "task_delivery"],
        max_capacity=1000,
        enabled=True,
        last_heartbeat_at=datetime.now(UTC) - timedelta(hours=2),
    )
    session.add(stale_relay)
    await session.flush()

    task = await _make_task(session, agent_a, agent_b)
    decision = await _select(
        session, task, agent_a, agent_b, enable_edge_relay=True
    )

    personal_edge_relay_ids = [
        c["relay_node_id"]
        for c in decision.candidate_routes
        if c["route_type"] == "personal_edge"
    ]
    assert str(stale_relay.id) not in personal_edge_relay_ids


# ---------------------------------------------------------------------------
# task_service reading point (single PersonalScope query per task, D2)
# ---------------------------------------------------------------------------


async def _create_task_with_mocked_routing(
    session: AsyncSession,
    from_agent: Agent,
    to_agent: Agent,
):
    """Run create_task with the delivery path mocked out.

    select_route and deliver_task_request are replaced so the test only
    exercises the PersonalScope read and the parameters handed to
    select_route.
    """
    from app.services.task_service import create_task

    captured = {}

    async def _fake_select_route(db_session, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(selected_route_type="central_relay")

    with patch(
        "app.services.path_optimizer.select_route", new=_fake_select_route
    ), patch(
        "app.services.task_service.deliver_task_request",
        new=AsyncMock(return_value="delivered"),
    ):
        await create_task(
            session,
            from_agent=from_agent,
            to_agent_number=to_agent.agent_number,
            idempotency_key=f"key-{uuid.uuid4().hex[:8]}",
            payload={"hello": "world"},
        )

    return captured


@pytest.mark.asyncio
async def test_task_service_missing_scope_row_passes_false(
    session: AsyncSession,
    test_user: User,
    agent_a: Agent,
    agent_b: Agent,
    central_relay: RelayNode,
):
    """A missing PersonalScope row is synonymous with enable_edge_relay=False."""
    # No PersonalScope row for test_user.
    captured = await _create_task_with_mocked_routing(session, agent_a, agent_b)

    assert captured.get("enable_edge_relay") is False


@pytest.mark.asyncio
async def test_task_service_reads_scope_row(
    session: AsyncSession,
    test_user: User,
    agent_a: Agent,
    agent_b: Agent,
    central_relay: RelayNode,
):
    """The PersonalScope row's enable_edge_relay is passed through verbatim."""
    session.add(
        PersonalScope(user_id=test_user.id, enable_edge_relay=True)
    )
    await session.flush()
    captured_true = await _create_task_with_mocked_routing(session, agent_a, agent_b)
    assert captured_true.get("enable_edge_relay") is True

    # Flip the row to False and create another task.
    from sqlalchemy import select as sa_select

    row = await session.scalar(
        sa_select(PersonalScope).where(PersonalScope.user_id == test_user.id)
    )
    row.enable_edge_relay = False
    await session.flush()
    captured_false = await _create_task_with_mocked_routing(session, agent_a, agent_b)
    assert captured_false.get("enable_edge_relay") is False
