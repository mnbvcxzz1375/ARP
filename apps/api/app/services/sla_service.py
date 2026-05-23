"""SLA service: monitor SLA targets, detect violations, calculate metrics."""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DomainException
from app.models.route_metric import RouteMetric
from app.models.sla_target import SLATarget
from app.models.sla_violation import SLAViolation
from app.protocol.constants import ErrorCode

logger = logging.getLogger(__name__)


async def create_sla_target(
    session: AsyncSession,
    scope_id: str,
    target_name: str,
    metric_type: str,
    target_value: float,
    warning_threshold: float = 0.9,
    critical_threshold: float = 0.8,
    measurement_window_seconds: int = 300,
    enabled: bool = True,
) -> SLATarget:
    """Create a new SLA target.

    Args:
        scope_id: Scope identifier (e.g., "global", "zone:us-west", "relay:node-1")
        target_name: Human-readable target name
        metric_type: One of: latency_p99, latency_p95, success_rate, availability, throughput
        target_value: Target value (e.g., 500 for 500ms, 0.999 for 99.9%)
        warning_threshold: Warn when metric exceeds this fraction of target (default 0.9)
        critical_threshold: Critical when metric exceeds this fraction of target (default 0.8)
        measurement_window_seconds: Time window for metric calculation (default 300s)
        enabled: Whether this target is active
    """
    valid_metric_types = ["latency_p99", "latency_p95", "success_rate", "availability", "throughput"]
    if metric_type not in valid_metric_types:
        raise DomainException(
            ErrorCode.INVALID_REQUEST,
            f"Invalid metric_type. Must be one of: {valid_metric_types}",
            status_code=400,
        )

    target = SLATarget(
        scope_id=scope_id,
        target_name=target_name,
        metric_type=metric_type,
        target_value=target_value,
        warning_threshold=warning_threshold,
        critical_threshold=critical_threshold,
        measurement_window_seconds=measurement_window_seconds,
        enabled=enabled,
    )
    session.add(target)
    await session.flush()
    logger.info("Created SLA target %s: %s=%s for scope=%s", target.id, metric_type, target_value, scope_id)
    return target


async def calculate_metrics(
    session: AsyncSession,
    scope_id: str,
    metric_type: str,
    window_seconds: int,
) -> float | None:
    """Calculate aggregated metric for a scope and time window.

    Returns:
        Calculated metric value, or None if insufficient data.
    """
    now = datetime.now(UTC)
    window_start = now - timedelta(seconds=window_seconds)

    # Build base query for the scope
    query = select(RouteMetric).where(RouteMetric.metric_time >= window_start)

    # Apply scope filter
    if scope_id == "global":
        pass  # No filter, all metrics
    elif scope_id.startswith("zone:"):
        zone_id = scope_id.split(":", 1)[1]
        query = query.where(RouteMetric.zone_id == zone_id)
    elif scope_id.startswith("relay:"):
        relay_node_name = scope_id.split(":", 1)[1]
        # Need to join with relay_nodes to filter by name
        from app.models.relay_node import RelayNode
        query = query.join(RelayNode, RouteMetric.relay_node_id == RelayNode.id).where(
            RelayNode.node_name == relay_node_name
        )
    else:
        logger.warning("Unknown scope_id format: %s", scope_id)
        return None

    result = await session.execute(query)
    metrics = result.scalars().all()

    if not metrics:
        return None

    # Calculate metric based on type
    if metric_type == "latency_p99":
        latencies = sorted([m.latency_ms for m in metrics])
        idx = int(len(latencies) * 0.99)
        return float(latencies[idx]) if latencies else None

    elif metric_type == "latency_p95":
        latencies = sorted([m.latency_ms for m in metrics])
        idx = int(len(latencies) * 0.95)
        return float(latencies[idx]) if latencies else None

    elif metric_type == "success_rate":
        total = len(metrics)
        successful = sum(1 for m in metrics if m.success)
        return successful / total if total > 0 else None

    elif metric_type == "availability":
        # Availability: percentage of time with at least one successful delivery
        # Group by minute and check if any success in that minute
        from collections import defaultdict
        minute_buckets = defaultdict(list)
        for m in metrics:
            minute_key = m.metric_time.replace(second=0, microsecond=0)
            minute_buckets[minute_key].append(m.success)

        total_minutes = len(minute_buckets)
        available_minutes = sum(1 for successes in minute_buckets.values() if any(successes))
        return available_minutes / total_minutes if total_minutes > 0 else None

    elif metric_type == "throughput":
        # Throughput: messages per second
        total_messages = len(metrics)
        return total_messages / window_seconds if window_seconds > 0 else None

    return None


async def check_sla_compliance(session: AsyncSession) -> int:
    """Check all enabled SLA targets for compliance.

    Returns:
        Number of new violations detected.
    """
    result = await session.execute(
        select(SLATarget).where(SLATarget.enabled == True)
    )
    targets = result.scalars().all()

    violations_detected = 0

    for target in targets:
        metric_value = await calculate_metrics(
            session,
            target.scope_id,
            target.metric_type,
            target.measurement_window_seconds,
        )

        if metric_value is None:
            continue

        # Determine if violation occurred
        severity = None

        # For latency metrics, higher is worse
        if target.metric_type in ["latency_p99", "latency_p95"]:
            if metric_value > target.target_value / target.critical_threshold:
                severity = "critical"
            elif metric_value > target.target_value / target.warning_threshold:
                severity = "warning"

        # For success_rate and availability, lower is worse
        elif target.metric_type in ["success_rate", "availability"]:
            if metric_value < target.target_value * target.critical_threshold:
                severity = "critical"
            elif metric_value < target.target_value * target.warning_threshold:
                severity = "warning"

        # For throughput, lower is worse
        elif target.metric_type == "throughput":
            if metric_value < target.target_value * target.critical_threshold:
                severity = "critical"
            elif metric_value < target.target_value * target.warning_threshold:
                severity = "warning"

        if severity:
            # Check if there's an ongoing violation
            ongoing_result = await session.execute(
                select(SLAViolation).where(
                    SLAViolation.target_id == target.id,
                    SLAViolation.resolved_at.is_(None),
                ).order_by(SLAViolation.violation_time.desc()).limit(1)
            )
            ongoing = ongoing_result.scalar_one_or_none()

            if ongoing:
                # Update duration
                duration = int((datetime.now(UTC) - ongoing.violation_time).total_seconds())
                ongoing.duration_seconds = duration
                ongoing.metric_value = metric_value
                ongoing.severity = severity
            else:
                # Record new violation
                await record_violation(
                    session,
                    target_id=target.id,
                    metric_value=metric_value,
                    severity=severity,
                )
                violations_detected += 1
        else:
            # No violation, resolve any ongoing violations
            ongoing_result = await session.execute(
                select(SLAViolation).where(
                    SLAViolation.target_id == target.id,
                    SLAViolation.resolved_at.is_(None),
                )
            )
            ongoing_violations = ongoing_result.scalars().all()
            for v in ongoing_violations:
                v.resolved_at = datetime.now(UTC)
                v.resolution_note = "Metric returned to acceptable range"

    await session.commit()
    return violations_detected


async def record_violation(
    session: AsyncSession,
    target_id: uuid.UUID,
    metric_value: float,
    severity: str,
) -> SLAViolation:
    """Record a new SLA violation."""
    violation = SLAViolation(
        target_id=target_id,
        violation_time=datetime.now(UTC),
        metric_value=metric_value,
        severity=severity,
        duration_seconds=0,
    )
    session.add(violation)
    await session.flush()
    logger.warning(
        "SLA violation detected: target=%s severity=%s metric_value=%s",
        target_id,
        severity,
        metric_value,
    )
    return violation


async def generate_sla_report(
    session: AsyncSession,
    scope_id: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> dict:
    """Generate SLA compliance report.

    Args:
        scope_id: Optional scope filter
        start_time: Report start time (default: 24 hours ago)
        end_time: Report end time (default: now)

    Returns:
        Report dictionary with targets, violations, and compliance metrics.
    """
    if start_time is None:
        start_time = datetime.now(UTC) - timedelta(hours=24)
    if end_time is None:
        end_time = datetime.now(UTC)

    # Get targets
    query = select(SLATarget)
    if scope_id:
        query = query.where(SLATarget.scope_id == scope_id)
    result = await session.execute(query)
    targets = result.scalars().all()

    # Get violations in time range
    violations_query = select(SLAViolation).where(
        SLAViolation.violation_time >= start_time,
        SLAViolation.violation_time <= end_time,
    )
    if scope_id:
        violations_query = violations_query.join(SLATarget).where(SLATarget.scope_id == scope_id)

    violations_result = await session.execute(violations_query)
    violations = violations_result.scalars().all()

    # Calculate compliance metrics
    total_targets = len(targets)
    targets_with_violations = len(set(v.target_id for v in violations))
    compliance_rate = (total_targets - targets_with_violations) / total_targets if total_targets > 0 else 1.0

    # Group violations by severity
    critical_violations = [v for v in violations if v.severity == "critical"]
    warning_violations = [v for v in violations if v.severity == "warning"]

    # Calculate average violation duration
    resolved_violations = [v for v in violations if v.resolved_at is not None]
    avg_resolution_time = (
        sum(v.duration_seconds for v in resolved_violations) / len(resolved_violations)
        if resolved_violations else 0
    )

    return {
        "report_period": {
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
        },
        "scope_id": scope_id or "all",
        "summary": {
            "total_targets": total_targets,
            "targets_with_violations": targets_with_violations,
            "compliance_rate": compliance_rate,
            "total_violations": len(violations),
            "critical_violations": len(critical_violations),
            "warning_violations": len(warning_violations),
            "avg_resolution_time_seconds": avg_resolution_time,
        },
        "targets": [
            {
                "id": str(t.id),
                "name": t.target_name,
                "scope_id": t.scope_id,
                "metric_type": t.metric_type,
                "target_value": t.target_value,
                "enabled": t.enabled,
            }
            for t in targets
        ],
        "violations": [
            {
                "id": str(v.id),
                "target_id": str(v.target_id),
                "violation_time": v.violation_time.isoformat(),
                "metric_value": v.metric_value,
                "severity": v.severity,
                "duration_seconds": v.duration_seconds,
                "resolved": v.resolved_at is not None,
                "resolved_at": v.resolved_at.isoformat() if v.resolved_at else None,
            }
            for v in violations
        ],
    }
