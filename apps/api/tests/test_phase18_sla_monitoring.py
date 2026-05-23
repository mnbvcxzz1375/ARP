"""Phase 18: SLA monitoring and metrics tests."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.relay_node import RelayNode
from app.models.route_decision import RouteDecision
from app.models.route_metric import RouteMetric
from app.models.sla_target import SLATarget
from app.models.sla_violation import SLAViolation
from app.models.task import Task
from app.services import sla_service


@pytest.mark.asyncio
async def test_create_sla_target(session):
    """Test creating an SLA target."""
    target = await sla_service.create_sla_target(
        session,
        scope_id="global",
        target_name="Global P99 Latency",
        metric_type="latency_p99",
        target_value=500.0,
        warning_threshold=0.9,
        critical_threshold=0.8,
        measurement_window_seconds=300,
    )
    await session.commit()

    assert target.id is not None
    assert target.scope_id == "global"
    assert target.target_name == "Global P99 Latency"
    assert target.metric_type == "latency_p99"
    assert target.target_value == 500.0
    assert target.enabled is True


@pytest.mark.asyncio
async def test_create_sla_target_invalid_metric_type(session):
    """Test creating an SLA target with invalid metric type."""
    from app.exceptions import DomainException

    with pytest.raises(DomainException) as exc_info:
        await sla_service.create_sla_target(
            session,
            scope_id="global",
            target_name="Invalid Metric",
            metric_type="invalid_metric",
            target_value=100.0,
        )

    assert "Invalid metric_type" in str(exc_info.value)


@pytest.mark.asyncio
async def test_calculate_latency_p99_metric(session, sample_user, sample_agent):
    """Test calculating P99 latency metric."""
    # Create a task and route decision
    task = Task(
        created_by=sample_agent.id,
        assigned_to=sample_agent.id,        status="pending",
    )
    session.add(task)
    await session.flush()

    route_decision = RouteDecision(
        task_id=task.id,
        message_id="msg-test",
        selected_route_type="direct",
    )
    session.add(route_decision)
    await session.flush()

    # Create 100 route metrics with varying latencies
    for i in range(100):
        metric = RouteMetric(
            route_decision_id=route_decision.id,
            metric_time=datetime.now(UTC),
            latency_ms=i * 10,  # 0ms to 990ms
            success=True,
        )
        session.add(metric)
    await session.commit()

    # Calculate P99 (should be around 990ms)
    p99 = await sla_service.calculate_metrics(
        session,
        scope_id="global",
        metric_type="latency_p99",
        window_seconds=300,
    )

    assert p99 is not None
    assert p99 >= 980.0  # P99 should be close to 990ms


@pytest.mark.asyncio
async def test_calculate_success_rate_metric(session, sample_user, sample_agent):
    """Test calculating success rate metric."""
    task = Task(
        created_by=sample_agent.id,
        assigned_to=sample_agent.id,        status="pending",
    )
    session.add(task)
    await session.flush()

    route_decision = RouteDecision(
        task_id=task.id,
        message_id="msg-test",
        selected_route_type="direct",
    )
    session.add(route_decision)
    await session.flush()

    # Create 100 metrics: 95 successful, 5 failed
    for i in range(100):
        metric = RouteMetric(
            route_decision_id=route_decision.id,
            metric_time=datetime.now(UTC),
            latency_ms=100,
            success=(i < 95),  # First 95 are successful
            error_code="TEST_ERROR" if i >= 95 else None,
        )
        session.add(metric)
    await session.commit()

    success_rate = await sla_service.calculate_metrics(
        session,
        scope_id="global",
        metric_type="success_rate",
        window_seconds=300,
    )

    assert success_rate is not None
    assert success_rate == 0.95


@pytest.mark.asyncio
async def test_check_sla_compliance_no_violation(session, sample_user, sample_agent):
    """Test SLA compliance check when no violation occurs."""
    # Create SLA target: P99 < 500ms
    target = await sla_service.create_sla_target(
        session,
        scope_id="global",
        target_name="P99 Latency",
        metric_type="latency_p99",
        target_value=500.0,
        warning_threshold=0.9,
        critical_threshold=0.8,
    )
    await session.commit()

    # Create metrics with low latency (all under 500ms)
    task = Task(
        created_by=sample_agent.id,
        assigned_to=sample_agent.id,        status="pending",
    )
    session.add(task)
    await session.flush()

    route_decision = RouteDecision(
        task_id=task.id,
        message_id="msg-test",
        selected_route_type="direct",
    )
    session.add(route_decision)
    await session.flush()

    for i in range(100):
        metric = RouteMetric(
            route_decision_id=route_decision.id,
            metric_time=datetime.now(UTC),
            latency_ms=i * 4,  # 0ms to 396ms
            success=True,
        )
        session.add(metric)
    await session.commit()

    violations = await sla_service.check_sla_compliance(session)
    assert violations == 0

    # Verify no violations were created
    result = await session.execute(select(SLAViolation))
    assert len(result.scalars().all()) == 0


@pytest.mark.asyncio
async def test_check_sla_compliance_warning_violation(session, sample_user, sample_agent):
    """Test SLA compliance check when warning threshold is exceeded."""
    # Create SLA target: P99 < 500ms, warning at 90% (555ms)
    target = await sla_service.create_sla_target(
        session,
        scope_id="global",
        target_name="P99 Latency",
        metric_type="latency_p99",
        target_value=500.0,
        warning_threshold=0.9,
        critical_threshold=0.8,
    )
    await session.commit()

    # Create metrics with P99 around 600ms (exceeds warning)
    task = Task(
        created_by=sample_agent.id,
        assigned_to=sample_agent.id,        status="pending",
    )
    session.add(task)
    await session.flush()

    route_decision = RouteDecision(
        task_id=task.id,
        message_id="msg-test",
        selected_route_type="direct",
    )
    session.add(route_decision)
    await session.flush()

    for i in range(100):
        metric = RouteMetric(
            route_decision_id=route_decision.id,
            metric_time=datetime.now(UTC),
            latency_ms=i * 6,  # 0ms to 594ms, P99 ~594ms
            success=True,
        )
        session.add(metric)
    await session.commit()

    violations = await sla_service.check_sla_compliance(session)
    assert violations == 1

    # Verify warning violation was created
    result = await session.execute(
        select(SLAViolation).where(SLAViolation.target_id == target.id)
    )
    violation = result.scalar_one()
    assert violation.severity == "warning"
    assert violation.resolved_at is None


@pytest.mark.asyncio
async def test_check_sla_compliance_critical_violation(session, sample_user, sample_agent):
    """Test SLA compliance check when critical threshold is exceeded."""
    # Create SLA target: P99 < 500ms, critical at 80% (625ms)
    target = await sla_service.create_sla_target(
        session,
        scope_id="global",
        target_name="P99 Latency",
        metric_type="latency_p99",
        target_value=500.0,
        warning_threshold=0.9,
        critical_threshold=0.8,
    )
    await session.commit()

    # Create metrics with P99 around 700ms (exceeds critical)
    task = Task(
        created_by=sample_agent.id,
        assigned_to=sample_agent.id,        status="pending",
    )
    session.add(task)
    await session.flush()

    route_decision = RouteDecision(
        task_id=task.id,
        message_id="msg-test",
        selected_route_type="direct",
    )
    session.add(route_decision)
    await session.flush()

    for i in range(100):
        metric = RouteMetric(
            route_decision_id=route_decision.id,
            metric_time=datetime.now(UTC),
            latency_ms=i * 7,  # 0ms to 693ms, P99 ~693ms
            success=True,
        )
        session.add(metric)
    await session.commit()

    violations = await sla_service.check_sla_compliance(session)
    assert violations == 1

    # Verify critical violation was created
    result = await session.execute(
        select(SLAViolation).where(SLAViolation.target_id == target.id)
    )
    violation = result.scalar_one()
    assert violation.severity == "critical"


@pytest.mark.asyncio
async def test_sla_violation_resolution(session, sample_user, sample_agent):
    """Test that violations are resolved when metrics return to normal."""
    # Create SLA target
    target = await sla_service.create_sla_target(
        session,
        scope_id="global",
        target_name="P99 Latency",
        metric_type="latency_p99",
        target_value=500.0,
    )
    await session.commit()

    task = Task(
        created_by=sample_agent.id,
        assigned_to=sample_agent.id,        status="pending",
    )
    session.add(task)
    await session.flush()

    route_decision = RouteDecision(
        task_id=task.id,
        message_id="msg-test",
        selected_route_type="direct",
    )
    session.add(route_decision)
    await session.flush()

    # First: create high latency metrics (violation) - within window
    violation_time = datetime.now(UTC) - timedelta(seconds=150)
    for i in range(100):
        metric = RouteMetric(
            route_decision_id=route_decision.id,
            metric_time=violation_time,
            latency_ms=i * 7,  # High latency, P99 ~693ms
            success=True,
        )
        session.add(metric)
    await session.commit()

    violations = await sla_service.check_sla_compliance(session)
    assert violations == 1

    # Second: Add MANY more low latency metrics to dilute the high ones
    # Need enough so that P99 of combined set < 500ms
    # With 100 high (0-693ms) + 10000 low (0-99ms), P99 will be ~99ms
    resolution_time = datetime.now(UTC) - timedelta(seconds=5)
    for i in range(10000):
        metric = RouteMetric(
            route_decision_id=route_decision.id,
            metric_time=resolution_time,
            latency_ms=i % 100,  # Very low latency, cycling 0-99ms
            success=True,
        )
        session.add(metric)
    await session.commit()

    violations = await sla_service.check_sla_compliance(session)
    assert violations == 0

    # Verify violation was resolved
    result = await session.execute(
        select(SLAViolation).where(SLAViolation.target_id == target.id)
    )
    violation = result.scalar_one()
    assert violation.resolved_at is not None
    assert violation.resolution_note == "Metric returned to acceptable range"


@pytest.mark.asyncio
async def test_generate_sla_report(session, sample_user, sample_agent):
    """Test generating SLA compliance report."""
    # Create SLA target
    target = await sla_service.create_sla_target(
        session,
        scope_id="global",
        target_name="P99 Latency",
        metric_type="latency_p99",
        target_value=500.0,
    )
    await session.commit()

    # Create a violation
    violation = await sla_service.record_violation(
        session,
        target_id=target.id,
        metric_value=600.0,
        severity="warning",
    )
    await session.commit()

    # Generate report
    report = await sla_service.generate_sla_report(
        session,
        scope_id="global",
        start_time=datetime.now(UTC) - timedelta(hours=1),
        end_time=datetime.now(UTC),
    )

    assert report["scope_id"] == "global"
    assert report["summary"]["total_targets"] == 1
    assert report["summary"]["targets_with_violations"] == 1
    assert report["summary"]["total_violations"] == 1
    assert report["summary"]["warning_violations"] == 1
    assert report["summary"]["critical_violations"] == 0
    assert len(report["targets"]) == 1
    assert len(report["violations"]) == 1


@pytest.mark.asyncio
async def test_zone_scoped_metrics(session, sample_user, sample_agent):
    """Test calculating metrics scoped to a specific zone."""
    # Create relay nodes in different zones
    relay_us = RelayNode(
        node_name="relay-us-west",
        node_type="regional",
        zone="us-west",
    )
    relay_eu = RelayNode(
        node_name="relay-eu-central",
        node_type="regional",
        zone="eu-central",
    )
    session.add_all([relay_us, relay_eu])
    await session.flush()

    task = Task(
        created_by=sample_agent.id,
        assigned_to=sample_agent.id,        status="pending",
    )
    session.add(task)
    await session.flush()

    # Create route decisions and metrics for each zone
    for relay, latency_base in [(relay_us, 100), (relay_eu, 200)]:
        route_decision = RouteDecision(
            task_id=task.id,
            message_id=f"msg-{relay.zone}",
            selected_route_type="central_relay",
            selected_relay_node_id=relay.id,
        )
        session.add(route_decision)
        await session.flush()

        for i in range(50):
            metric = RouteMetric(
                route_decision_id=route_decision.id,
                metric_time=datetime.now(UTC),
                latency_ms=latency_base + i,
                success=True,
                relay_node_id=relay.id,
                zone_id=relay.zone,
            )
            session.add(metric)
    await session.commit()

    # Calculate P99 for US zone (should be around 100 + 49 = 149ms)
    us_p99 = await sla_service.calculate_metrics(
        session,
        scope_id="zone:us-west",
        metric_type="latency_p99",
        window_seconds=300,
    )
    assert us_p99 is not None
    assert 145 <= us_p99 <= 150

    # Calculate P99 for EU zone (should be around 200 + 49 = 249ms)
    eu_p99 = await sla_service.calculate_metrics(
        session,
        scope_id="zone:eu-central",
        metric_type="latency_p99",
        window_seconds=300,
    )
    assert eu_p99 is not None
    assert 245 <= eu_p99 <= 250
