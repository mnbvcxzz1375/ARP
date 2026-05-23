"""Phase 18: Business Continuity and Failover Tests."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.circuit_breaker import CircuitBreaker
from app.models.failover_config import FailoverConfig
from app.models.failover_event import FailoverEvent
from app.models.relay_node import RelayNode
from app.services.continuity_service import (
    check_and_trigger_auto_failover,
    check_relay_health,
    execute_failover,
    get_backup_relay,
    rollback_failover,
    trigger_failover,
    update_circuit_breaker,
)


@pytest.mark.asyncio
async def test_check_relay_health_healthy(session):
    """Test relay health check for healthy relay."""
    relay = RelayNode(
        node_name="test-relay-healthy",
        node_type="central",
        status="healthy",
        enabled=True,
        last_heartbeat_at=datetime.now(UTC),
    )
    session.add(relay)
    await session.commit()

    health = await check_relay_health(session, relay.id)

    assert health["is_healthy"] is True
    assert health["status"] == "healthy"
    assert health["last_heartbeat_age_seconds"] < 5


@pytest.mark.asyncio
async def test_check_relay_health_timeout(session):
    """Test relay health check for relay with heartbeat timeout."""
    relay = RelayNode(
        node_name="test-relay-timeout",
        node_type="central",
        status="healthy",
        enabled=True,
        last_heartbeat_at=datetime.now(UTC) - timedelta(seconds=120),
    )
    session.add(relay)
    await session.commit()

    health = await check_relay_health(session, relay.id)

    assert health["is_healthy"] is False
    assert health["status"] == "heartbeat_timeout"
    assert health["last_heartbeat_age_seconds"] > 60


@pytest.mark.asyncio
async def test_check_relay_health_disabled(session):
    """Test relay health check for disabled relay."""
    relay = RelayNode(
        node_name="test-relay-disabled",
        node_type="central",
        status="healthy",
        enabled=False,
        last_heartbeat_at=datetime.now(UTC),
    )
    session.add(relay)
    await session.commit()

    health = await check_relay_health(session, relay.id)

    assert health["is_healthy"] is False
    assert health["status"] == "disabled"


@pytest.mark.asyncio
async def test_circuit_breaker_trip_on_failures(session):
    """Test circuit breaker trips after consecutive failures."""
    relay = RelayNode(
        node_name="test-relay-cb",
        node_type="central",
        status="healthy",
        enabled=True,
        last_heartbeat_at=datetime.now(UTC),
    )
    session.add(relay)
    await session.commit()

    # Record 5 consecutive failures (default threshold)
    for i in range(5):
        breaker = await update_circuit_breaker(
            session,
            relay_node_id=relay.id,
            success=False,
            error_code="DELIVERY_FAILED",
        )
        await session.commit()

    # Circuit should be open
    assert breaker.state == "open"
    assert breaker.failure_count == 5
    assert breaker.open_until is not None
    assert breaker.is_open is True


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_recovery(session):
    """Test circuit breaker transitions to half_open and recovers."""
    relay = RelayNode(
        node_name="test-relay-recovery",
        node_type="central",
        status="healthy",
        enabled=True,
        last_heartbeat_at=datetime.now(UTC),
    )
    session.add(relay)
    await session.commit()

    # Create circuit breaker in open state with expired timeout
    breaker = CircuitBreaker(
        relay_node_id=relay.id,
        state="open",
        failure_count=5,
        open_until=datetime.now(UTC) - timedelta(seconds=1),  # Already expired
        success_threshold=3,
        failure_threshold=5,
    )
    session.add(breaker)
    await session.commit()

    # First success should transition to half_open
    breaker = await update_circuit_breaker(
        session,
        relay_node_id=relay.id,
        success=True,
    )
    await session.commit()

    assert breaker.state == "half_open"
    assert breaker.success_count == 1

    # 2 more successes should close the circuit
    for i in range(2):
        breaker = await update_circuit_breaker(
            session,
            relay_node_id=relay.id,
            success=True,
        )
        await session.commit()

    assert breaker.state == "closed"
    assert breaker.success_count == 0
    assert breaker.failure_count == 0


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_failure(session):
    """Test circuit breaker reopens on failure in half_open state."""
    relay = RelayNode(
        node_name="test-relay-reopen",
        node_type="central",
        status="healthy",
        enabled=True,
        last_heartbeat_at=datetime.now(UTC),
    )
    session.add(relay)
    await session.commit()

    # Create circuit breaker in half_open state
    breaker = CircuitBreaker(
        relay_node_id=relay.id,
        state="half_open",
        failure_count=0,
        success_count=1,
        success_threshold=3,
        failure_threshold=5,
    )
    session.add(breaker)
    await session.commit()

    # Failure in half_open should reopen circuit
    breaker = await update_circuit_breaker(
        session,
        relay_node_id=relay.id,
        success=False,
        error_code="DELIVERY_FAILED",
    )
    await session.commit()

    assert breaker.state == "open"
    assert breaker.open_until is not None


@pytest.mark.asyncio
async def test_failover_config_creation(session):
    """Test creating a failover configuration."""
    primary_relay = RelayNode(
        node_name="primary-relay",
        node_type="central",
        status="healthy",
        enabled=True,
        last_heartbeat_at=datetime.now(UTC),
    )
    backup_relay = RelayNode(
        node_name="backup-relay",
        node_type="central",
        status="healthy",
        enabled=True,
        last_heartbeat_at=datetime.now(UTC),
    )
    session.add_all([primary_relay, backup_relay])
    await session.commit()

    scope_id = uuid.uuid4()
    config = FailoverConfig(
        scope_id=scope_id,
        primary_relay_id=primary_relay.id,
        backup_relay_ids=[str(backup_relay.id)],
        failover_threshold_seconds=60,
        auto_failover_enabled=True,
        manual_approval_required=False,
    )
    session.add(config)
    await session.commit()

    assert config.id is not None
    assert config.primary_relay_id == primary_relay.id
    assert len(config.backup_relay_ids) == 1


@pytest.mark.asyncio
async def test_get_backup_relay(session):
    """Test selecting a healthy backup relay."""
    primary_relay = RelayNode(
        node_name="primary-relay-2",
        node_type="central",
        status="healthy",
        enabled=True,
        last_heartbeat_at=datetime.now(UTC),
    )
    backup_relay_1 = RelayNode(
        node_name="backup-relay-1",
        node_type="central",
        status="down",  # Unhealthy
        enabled=True,
        last_heartbeat_at=datetime.now(UTC),
    )
    backup_relay_2 = RelayNode(
        node_name="backup-relay-2",
        node_type="central",
        status="healthy",
        enabled=True,
        last_heartbeat_at=datetime.now(UTC),
    )
    session.add_all([primary_relay, backup_relay_1, backup_relay_2])
    await session.commit()

    scope_id = uuid.uuid4()
    config = FailoverConfig(
        scope_id=scope_id,
        primary_relay_id=primary_relay.id,
        backup_relay_ids=[str(backup_relay_1.id), str(backup_relay_2.id)],
        failover_threshold_seconds=60,
        auto_failover_enabled=True,
        manual_approval_required=False,
    )
    session.add(config)
    await session.commit()

    # Should skip unhealthy backup_relay_1 and select backup_relay_2
    backup = await get_backup_relay(session, config)

    assert backup is not None
    assert backup.id == backup_relay_2.id


@pytest.mark.asyncio
async def test_trigger_and_execute_failover(session):
    """Test triggering and executing a failover."""
    primary_relay = RelayNode(
        node_name="primary-relay-3",
        node_type="central",
        status="down",
        enabled=True,
        last_heartbeat_at=datetime.now(UTC) - timedelta(seconds=120),
    )
    backup_relay = RelayNode(
        node_name="backup-relay-3",
        node_type="central",
        status="healthy",
        enabled=True,
        last_heartbeat_at=datetime.now(UTC),
    )
    session.add_all([primary_relay, backup_relay])
    await session.commit()

    scope_id = uuid.uuid4()
    config = FailoverConfig(
        scope_id=scope_id,
        primary_relay_id=primary_relay.id,
        backup_relay_ids=[str(backup_relay.id)],
        failover_threshold_seconds=60,
        auto_failover_enabled=True,
        manual_approval_required=False,
    )
    session.add(config)
    await session.commit()

    # Trigger failover
    event = await trigger_failover(
        session,
        config_id=config.id,
        trigger_reason="Primary relay down",
        auto_triggered=True,
    )
    await session.commit()

    assert event.status == "pending"
    assert event.from_relay_id == primary_relay.id
    assert event.to_relay_id == backup_relay.id

    # Execute failover
    event = await execute_failover(session, event.id)
    await session.commit()

    assert event.status == "completed"
    assert event.completed_at is not None


@pytest.mark.asyncio
async def test_rollback_failover(session):
    """Test rolling back a completed failover."""
    primary_relay = RelayNode(
        node_name="primary-relay-4",
        node_type="central",
        status="healthy",
        enabled=True,
        last_heartbeat_at=datetime.now(UTC),
    )
    backup_relay = RelayNode(
        node_name="backup-relay-4",
        node_type="central",
        status="healthy",
        enabled=True,
        last_heartbeat_at=datetime.now(UTC),
    )
    session.add_all([primary_relay, backup_relay])
    await session.commit()

    scope_id = uuid.uuid4()
    config = FailoverConfig(
        scope_id=scope_id,
        primary_relay_id=primary_relay.id,
        backup_relay_ids=[str(backup_relay.id)],
        failover_threshold_seconds=60,
        auto_failover_enabled=True,
        manual_approval_required=False,
    )
    session.add(config)
    await session.commit()

    # Create completed failover event
    event = FailoverEvent(
        config_id=config.id,
        event_time=datetime.now(UTC),
        trigger_reason="Test failover",
        from_relay_id=primary_relay.id,
        to_relay_id=backup_relay.id,
        auto_triggered=True,
        status="completed",
        completed_at=datetime.now(UTC),
    )
    session.add(event)
    await session.commit()

    # Rollback
    event = await rollback_failover(session, event.id)
    await session.commit()

    assert event.status == "rolled_back"
    assert event.rollback_at is not None


@pytest.mark.asyncio
async def test_auto_failover_trigger(session):
    """Test automatic failover triggering."""
    primary_relay = RelayNode(
        node_name="primary-relay-5",
        node_type="central",
        status="down",
        enabled=True,
        last_heartbeat_at=datetime.now(UTC) - timedelta(seconds=120),
    )
    backup_relay = RelayNode(
        node_name="backup-relay-5",
        node_type="central",
        status="healthy",
        enabled=True,
        last_heartbeat_at=datetime.now(UTC),
    )
    session.add_all([primary_relay, backup_relay])
    await session.commit()

    scope_id = uuid.uuid4()
    config = FailoverConfig(
        scope_id=scope_id,
        primary_relay_id=primary_relay.id,
        backup_relay_ids=[str(backup_relay.id)],
        failover_threshold_seconds=60,
        auto_failover_enabled=True,
        manual_approval_required=False,
    )
    session.add(config)
    await session.commit()

    # Check and trigger auto-failover
    triggered_events = await check_and_trigger_auto_failover(session)

    assert len(triggered_events) > 0
    event = triggered_events[0]
    assert event.auto_triggered is True
    assert event.status == "completed"  # Should be executed immediately


@pytest.mark.asyncio
async def test_manual_approval_required(session):
    """Test failover with manual approval requirement."""
    primary_relay = RelayNode(
        node_name="primary-relay-6",
        node_type="central",
        status="down",
        enabled=True,
        last_heartbeat_at=datetime.now(UTC) - timedelta(seconds=120),
    )
    backup_relay = RelayNode(
        node_name="backup-relay-6",
        node_type="central",
        status="healthy",
        enabled=True,
        last_heartbeat_at=datetime.now(UTC),
    )
    session.add_all([primary_relay, backup_relay])
    await session.commit()

    scope_id = uuid.uuid4()
    config = FailoverConfig(
        scope_id=scope_id,
        primary_relay_id=primary_relay.id,
        backup_relay_ids=[str(backup_relay.id)],
        failover_threshold_seconds=60,
        auto_failover_enabled=True,
        manual_approval_required=True,  # Requires approval
    )
    session.add(config)
    await session.commit()

    # Check and trigger auto-failover
    triggered_events = await check_and_trigger_auto_failover(session)

    # Should NOT trigger because manual approval is required
    # The auto-failover worker will skip configs that require manual approval
    assert len(triggered_events) == 0


@pytest.mark.asyncio
async def test_failover_migrates_active_tasks(session):
    """Test that failover actually migrates active tasks to backup relay."""
    from app.models.agent import Agent
    from app.models.route_decision import RouteDecision
    from app.models.user import User

    # Create user and agents
    user = User(username="test-user-migration")
    session.add(user)
    await session.flush()

    agent1 = Agent(owner_id=user.id, name="agent1", agent_number="1001", runtime="test")
    agent2 = Agent(owner_id=user.id, name="agent2", agent_number="1002", runtime="test")
    session.add_all([agent1, agent2])
    await session.flush()

    # Create relay nodes
    primary_relay = RelayNode(
        node_name="primary-relay-migration",
        node_type="central",
        status="down",
        enabled=True,
        last_heartbeat_at=datetime.now(UTC) - timedelta(seconds=120),
    )
    backup_relay = RelayNode(
        node_name="backup-relay-migration",
        node_type="central",
        status="healthy",
        enabled=True,
        last_heartbeat_at=datetime.now(UTC),
    )
    session.add_all([primary_relay, backup_relay])
    await session.commit()

    # Create tasks with different statuses
    from app.models.task import Task

    task_delivered = Task(
        created_by=agent1.id,
        assigned_to=agent2.id,
        status="delivered",
        message_id="msg-delivered",
    )
    task_accepted = Task(
        created_by=agent1.id,
        assigned_to=agent2.id,
        status="accepted",
        message_id="msg-accepted",
    )
    task_running = Task(
        created_by=agent1.id,
        assigned_to=agent2.id,
        status="running",
        message_id="msg-running",
    )
    task_completed = Task(
        created_by=agent1.id,
        assigned_to=agent2.id,
        status="completed",
        message_id="msg-completed",
    )
    session.add_all([task_delivered, task_accepted, task_running, task_completed])
    await session.flush()

    # Create route decisions pointing to primary relay
    route1 = RouteDecision(
        task_id=task_delivered.id,
        message_id="msg-delivered",
        selected_route_type="relay",
        selected_relay_node_id=primary_relay.id,
    )
    route2 = RouteDecision(
        task_id=task_accepted.id,
        message_id="msg-accepted",
        selected_route_type="relay",
        selected_relay_node_id=primary_relay.id,
    )
    route3 = RouteDecision(
        task_id=task_running.id,
        message_id="msg-running",
        selected_route_type="relay",
        selected_relay_node_id=primary_relay.id,
    )
    route4 = RouteDecision(
        task_id=task_completed.id,
        message_id="msg-completed",
        selected_route_type="relay",
        selected_relay_node_id=primary_relay.id,
    )
    session.add_all([route1, route2, route3, route4])
    await session.commit()

    # Create failover config
    scope_id = uuid.uuid4()
    config = FailoverConfig(
        scope_id=scope_id,
        primary_relay_id=primary_relay.id,
        backup_relay_ids=[str(backup_relay.id)],
        failover_threshold_seconds=60,
        auto_failover_enabled=True,
        manual_approval_required=False,
    )
    session.add(config)
    await session.commit()

    # Trigger and execute failover
    event = await trigger_failover(
        session,
        config_id=config.id,
        trigger_reason="Test migration",
        auto_triggered=True,
    )
    await session.commit()

    event = await execute_failover(session, event.id)
    await session.commit()

    # Verify failover completed
    assert event.status == "completed"
    assert event.affected_task_count == 3  # delivered, accepted, running (not completed)

    # Verify route decisions were updated
    await session.refresh(route1)
    await session.refresh(route2)
    await session.refresh(route3)
    await session.refresh(route4)

    assert route1.selected_relay_node_id == backup_relay.id
    assert route2.selected_relay_node_id == backup_relay.id
    assert route3.selected_relay_node_id == backup_relay.id
    assert route4.selected_relay_node_id == primary_relay.id  # Completed task not migrated
