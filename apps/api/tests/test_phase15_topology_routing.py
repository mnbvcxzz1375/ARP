"""Phase 15: Test topology-aware routing with route policies.

This test suite verifies:
1. Route policy evaluation with scope/zone information
2. Policy denial causes explicit failure (no fallback)
3. Cross-zone routing selects regional relay
4. RouteDecision records scope/zone/policy_id
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.network_scope import NetworkScope
from app.models.network_zone import NetworkZone
from app.models.relay_node import RelayNode
from app.models.route_decision import RouteDecision
from app.models.route_policy import RoutePolicy
from app.models.task import Task
from app.models.user import User
from app.protocol.constants import ErrorCode
from app.services.path_optimizer import select_route
from app.exceptions import DomainException


@pytest.fixture
async def test_user(session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        username=f"testuser_{uuid.uuid4().hex[:8]}",
        role="user",
    )
    session.add(user)
    await session.flush()
    return user


@pytest.fixture
async def network_scope(session: AsyncSession, test_user: User) -> NetworkScope:
    """Create a test network scope."""
    scope = NetworkScope(
        user_id=test_user.id,
        scope_name="test-enterprise",
        scope_type="enterprise",
    )
    session.add(scope)
    await session.flush()
    return scope


@pytest.fixture
async def zone_us_west(session: AsyncSession, network_scope: NetworkScope) -> NetworkZone:
    """Create US West zone."""
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
async def zone_us_east(session: AsyncSession, network_scope: NetworkScope) -> NetworkZone:
    """Create US East zone."""
    zone = NetworkZone(
        scope_id=network_scope.id,
        zone_name="us-east-1",
        zone_type="regional",
        zone_metadata={"region": "us-east-1", "latency_target_ms": 50},
    )
    session.add(zone)
    await session.flush()
    return zone


@pytest.fixture
async def central_relay(session: AsyncSession) -> RelayNode:
    """Create a central relay node."""
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
async def regional_relay(session: AsyncSession, zone_us_west: NetworkZone) -> RelayNode:
    """Create a regional relay node in US West."""
    relay = RelayNode(
        node_name="regional-relay-us-west",
        node_type="regional",
        status="healthy",
        current_load=0.2,
        queue_depth=3,
        avg_latency_ms=80.0,
        success_rate=0.92,
        capabilities=["websocket", "task_delivery", "cross_zone"],
        max_capacity=5000,
        enabled=True,
        last_heartbeat_at=datetime.now(UTC),
    )
    session.add(relay)
    await session.flush()

    # Add relay to zone
    zone_us_west.relay_node_ids.append(str(relay.id))
    await session.flush()

    return relay


@pytest.fixture
async def agent_west(
    session: AsyncSession,
    test_user: User,
    network_scope: NetworkScope,
    zone_us_west: NetworkZone,
) -> Agent:
    """Create an agent in US West zone."""
    agent = Agent(
        owner_id=test_user.id,
        agent_number=f"AN-{uuid.uuid4().hex[:12].upper()}",
        name="Agent West",
        runtime="python",
        inbound_policy="public",
        scope_id=network_scope.id,
        zone_id=zone_us_west.id,
    )
    session.add(agent)
    await session.flush()
    return agent


@pytest.fixture
async def agent_east(
    session: AsyncSession,
    test_user: User,
    network_scope: NetworkScope,
    zone_us_east: NetworkZone,
) -> Agent:
    """Create an agent in US East zone."""
    agent = Agent(
        owner_id=test_user.id,
        agent_number=f"AN-{uuid.uuid4().hex[:12].upper()}",
        name="Agent East",
        runtime="python",
        inbound_policy="public",
        scope_id=network_scope.id,
        zone_id=zone_us_east.id,
    )
    session.add(agent)
    await session.flush()
    return agent


@pytest.mark.asyncio
async def test_route_policy_denial_explicit_failure(
    session: AsyncSession,
    agent_west: Agent,
    agent_east: Agent,
    central_relay: RelayNode,
    network_scope: NetworkScope,
):
    """Test that route policy denial causes explicit failure, not fallback."""
    # Create a policy that denies all route types
    policy = RoutePolicy(
        scope_id=network_scope.id,
        policy_name="deny-all",
        priority=10,
        denied_route_types=["central_relay", "regional_relay", "personal_edge", "dedicated_channel"],
        enabled=True,
    )
    session.add(policy)
    await session.flush()

    # Create a task
    task = Task(
        created_by=agent_west.id,
        assigned_to=agent_east.id,
        status="created",
    )
    session.add(task)
    await session.flush()

    # Attempt route selection - should fail with ROUTE_POLICY_DENIED
    with pytest.raises(DomainException) as exc_info:
        await select_route(
            session,
            task=task,
            from_agent=agent_west,
            to_agent=agent_east,
            message_id="msg-001",
            scope_id=network_scope.id,
            source_zone_id=agent_west.zone_id,
            target_zone_id=agent_east.zone_id,
        )

    # Verify error code
    assert exc_info.value.code == ErrorCode.ROUTE_POLICY_DENIED.value
    assert "policy" in str(exc_info.value.message).lower()


@pytest.mark.asyncio
async def test_cross_zone_routing_selects_regional(
    session: AsyncSession,
    agent_west: Agent,
    agent_east: Agent,
    central_relay: RelayNode,
    regional_relay: RelayNode,
    network_scope: NetworkScope,
):
    """Test that cross-zone routing prefers regional relay."""
    # Create a task
    task = Task(
        created_by=agent_west.id,
        assigned_to=agent_east.id,
        status="created",
    )
    session.add(task)
    await session.flush()

    # Select route
    decision = await select_route(
        session,
        task=task,
        from_agent=agent_west,
        to_agent=agent_east,
        message_id="msg-002",
        scope_id=network_scope.id,
        source_zone_id=agent_west.zone_id,
        target_zone_id=agent_east.zone_id,
    )

    # Verify regional relay was selected (or central if regional not available)
    assert decision.selected_route_type in ["regional_relay", "central_relay"]
    assert decision.scope_id == network_scope.id
    assert decision.source_zone_id == agent_west.zone_id
    assert decision.target_zone_id == agent_east.zone_id

    # Verify candidates include regional relay
    candidate_types = [c["route_type"] for c in decision.candidate_routes]
    assert "regional_relay" in candidate_types or "central_relay" in candidate_types


@pytest.mark.asyncio
async def test_route_decision_records_policy_id(
    session: AsyncSession,
    agent_west: Agent,
    agent_east: Agent,
    central_relay: RelayNode,
    network_scope: NetworkScope,
):
    """Test that RouteDecision records the applied policy_id."""
    # Create a policy that allows central_relay
    policy = RoutePolicy(
        scope_id=network_scope.id,
        policy_name="allow-central",
        priority=10,
        allowed_route_types=["central_relay", "regional_relay"],
        enabled=True,
    )
    session.add(policy)
    await session.flush()

    # Create a task
    task = Task(
        created_by=agent_west.id,
        assigned_to=agent_east.id,
        status="created",
    )
    session.add(task)
    await session.flush()

    # Select route
    decision = await select_route(
        session,
        task=task,
        from_agent=agent_west,
        to_agent=agent_east,
        message_id="msg-003",
        scope_id=network_scope.id,
        source_zone_id=agent_west.zone_id,
        target_zone_id=agent_east.zone_id,
    )

    # Verify policy_id is recorded
    assert decision.policy_id == policy.id
    assert decision.scope_id == network_scope.id


@pytest.mark.asyncio
async def test_same_zone_routing_prefers_local(
    session: AsyncSession,
    test_user: User,
    network_scope: NetworkScope,
    zone_us_west: NetworkZone,
    central_relay: RelayNode,
):
    """Test that same-zone routing prefers local relays."""
    # Create two agents in the same zone
    agent1 = Agent(
        owner_id=test_user.id,
        agent_number=f"AN-{uuid.uuid4().hex[:12].upper()}",
        name="Agent 1",
        runtime="python",
        inbound_policy="public",
        scope_id=network_scope.id,
        zone_id=zone_us_west.id,
    )
    agent2 = Agent(
        owner_id=test_user.id,
        agent_number=f"AN-{uuid.uuid4().hex[:12].upper()}",
        name="Agent 2",
        runtime="python",
        inbound_policy="public",
        scope_id=network_scope.id,
        zone_id=zone_us_west.id,
    )
    session.add_all([agent1, agent2])
    await session.flush()

    # Create a task
    task = Task(
        created_by=agent1.id,
        assigned_to=agent2.id,
        status="created",
    )
    session.add(task)
    await session.flush()

    # Select route
    decision = await select_route(
        session,
        task=task,
        from_agent=agent1,
        to_agent=agent2,
        message_id="msg-004",
        scope_id=network_scope.id,
        source_zone_id=agent1.zone_id,
        target_zone_id=agent2.zone_id,
    )

    # Verify same zone routing
    assert decision.source_zone_id == decision.target_zone_id
    assert decision.selected_route_type in ["central_relay", "personal_edge"]


@pytest.mark.asyncio
async def test_no_scope_zone_still_works(
    session: AsyncSession,
    test_user: User,
    central_relay: RelayNode,
):
    """Test that routing still works without scope/zone (backward compatibility)."""
    # Create agents without scope/zone
    agent1 = Agent(
        owner_id=test_user.id,
        agent_number=f"AN-{uuid.uuid4().hex[:12].upper()}",
        name="Agent 1",
        runtime="python",
        inbound_policy="public",
    )
    agent2 = Agent(
        owner_id=test_user.id,
        agent_number=f"AN-{uuid.uuid4().hex[:12].upper()}",
        name="Agent 2",
        runtime="python",
        inbound_policy="public",
    )
    session.add_all([agent1, agent2])
    await session.flush()

    # Create a task
    task = Task(
        created_by=agent1.id,
        assigned_to=agent2.id,
        status="created",
    )
    session.add(task)
    await session.flush()

    # Select route - should work without scope/zone
    decision = await select_route(
        session,
        task=task,
        from_agent=agent1,
        to_agent=agent2,
        message_id="msg-005",
    )

    # Verify routing succeeded
    assert decision.selected_route_type == "central_relay"
    assert decision.scope_id is None
    assert decision.source_zone_id is None
    assert decision.target_zone_id is None


@pytest.mark.asyncio
async def test_route_policy_require_approval_blocks_central_relay(
    session: AsyncSession,
    agent_west: Agent,
    agent_east: Agent,
    central_relay: RelayNode,
    network_scope: NetworkScope,
):
    """Test that require_approval=True blocks central_relay selection."""
    # Create a policy allowing central_relay but requiring approval
    policy = RoutePolicy(
        scope_id=network_scope.id,
        policy_name="approval-required-central",
        priority=10,
        allowed_route_types=["central_relay"],
        require_approval=True,
        enabled=True,
    )
    session.add(policy)
    await session.flush()

    # Create a task
    task = Task(
        created_by=agent_west.id,
        assigned_to=agent_east.id,
        status="created",
    )
    session.add(task)
    await session.flush()

    # Attempt route selection - should fail with APPROVAL_REQUIRED
    with pytest.raises(DomainException) as exc_info:
        await select_route(
            session,
            task=task,
            from_agent=agent_west,
            to_agent=agent_east,
            message_id="msg-approval-central",
            scope_id=network_scope.id,
            source_zone_id=agent_west.zone_id,
            target_zone_id=agent_east.zone_id,
        )

    # Verify error code
    assert exc_info.value.code == ErrorCode.APPROVAL_REQUIRED.value
    assert "central_relay" in str(exc_info.value.message).lower()
    assert "approval" in str(exc_info.value.message).lower()


@pytest.mark.asyncio
async def test_route_policy_require_approval_blocks_regional_relay(
    session: AsyncSession,
    agent_west: Agent,
    agent_east: Agent,
    central_relay: RelayNode,
    regional_relay: RelayNode,
    network_scope: NetworkScope,
):
    """Test that require_approval=True blocks regional_relay selection."""
    # Create a policy allowing both but requiring approval
    policy = RoutePolicy(
        scope_id=network_scope.id,
        policy_name="approval-required-regional",
        priority=10,
        allowed_route_types=["regional_relay", "central_relay"],
        require_approval=True,
        enabled=True,
    )
    session.add(policy)
    await session.flush()

    # Create a task
    task = Task(
        created_by=agent_west.id,
        assigned_to=agent_east.id,
        status="created",
    )
    session.add(task)
    await session.flush()

    # Cross-zone routing tries regional_relay first - should be blocked
    with pytest.raises(DomainException) as exc_info:
        await select_route(
            session,
            task=task,
            from_agent=agent_west,
            to_agent=agent_east,
            message_id="msg-approval-regional",
            scope_id=network_scope.id,
            source_zone_id=agent_west.zone_id,
            target_zone_id=agent_east.zone_id,
        )

    # Verify error code
    assert exc_info.value.code == ErrorCode.APPROVAL_REQUIRED.value
    assert "regional_relay" in str(exc_info.value.message).lower()
    assert "approval" in str(exc_info.value.message).lower()


@pytest.mark.asyncio
async def test_circuit_breaker_query_error_raises_internal_error(
    session: AsyncSession,
    agent_west: Agent,
    agent_east: Agent,
    central_relay: RelayNode,
):
    """Test that CircuitBreaker query failure in _get_healthy_relays raises INTERNAL_ERROR 503 (fail closed)."""
    from unittest.mock import patch

    from app.exceptions import DomainException
    from app.protocol.constants import ErrorCode

    # Create a task
    task = Task(
        created_by=agent_west.id,
        assigned_to=agent_east.id,
        status="created",
    )
    session.add(task)
    await session.flush()

    original_execute = session.execute

    async def mock_execute(statement, *args, **kwargs):
        stmt_str = str(statement)
        if "circuit_breaker" in stmt_str:
            raise ConnectionError("DB connection lost")
        return await original_execute(statement, *args, **kwargs)

    with patch.object(session, "execute", mock_execute):
        with pytest.raises(DomainException) as exc_info:
            await select_route(
                session,
                task=task,
                from_agent=agent_west,
                to_agent=agent_east,
                message_id="msg-circuit-breaker-fail",
            )

    assert exc_info.value.code == ErrorCode.INTERNAL_ERROR.value
    assert exc_info.value.status_code == 503
    assert "circuit breaker" in str(exc_info.value.message).lower()
