"""Path Optimizer service: route selection for routing runtime.

This service implements the routing runtime. It performs route selection
based on connection policies, relay health, timeliness requirements, and
scoring dimensions.

Phase 12: Shadow mode - records decisions without changing delivery
Phase 13: Enforced mode - controls actual delivery path
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DomainException
from app.models.agent import Agent
from app.models.connection import Connection
from app.models.relay_node import RelayNode
from app.models.route_decision import RouteDecision
from app.models.task import Task
from app.protocol.constants import ErrorCode, InboundPolicy
from app.services.edge_discovery import check_local_network_match

logger = logging.getLogger(__name__)


def _raise_if_approval_required(
    route_type: str,
    policy_result: "PolicyEvaluationResult",
) -> None:
    """Raise DomainException if the policy requires approval (fail closed).

    Any candidate whose route policy sets require_approval=True must be blocked
    from selection. This ensures approval cannot be bypassed regardless of
    route type.

    Args:
        route_type: The candidate route type (for error message)
        policy_result: The policy evaluation result to check

    Raises:
        DomainException: With ErrorCode.APPROVAL_REQUIRED if require_approval is True
    """
    if policy_result.require_approval:
        logger.error(
            "Route policy requires approval for %s (policy=%s) - blocking route (fail closed)",
            route_type,
            policy_result.policy_id,
        )
        raise DomainException(
            ErrorCode.APPROVAL_REQUIRED,
            f"Route {route_type} requires approval (policy={policy_result.policy_id})",
        )


class RouteCandidate:
    """A candidate route with scoring dimensions."""

    def __init__(
        self,
        route_type: str,
        relay_node_id: uuid.UUID | None = None,
        relay_node: RelayNode | None = None,
    ):
        self.route_type = route_type
        self.relay_node_id = relay_node_id
        self.relay_node = relay_node

        # Scoring dimensions (lower is better for most)
        self.latency_ms: float = 0.0
        self.relay_load: float = 0.0
        self.queue_depth: int = 0
        self.delivery_success_rate: float = 1.0
        self.failure_rate: float = 0.0
        self.locality_score: float = 0.0
        self.cost_score: float = 0.0
        self.security_score: float = 0.0

    def compute_final_score(self, timeliness_mode: str) -> float:
        """Compute final score based on timeliness mode.

        Lower score is better. Timeliness mode adjusts weights.
        """
        # Base weights
        latency_weight = 1.0
        load_weight = 0.5
        queue_weight = 0.3
        success_weight = 2.0
        failure_weight = 2.0
        locality_weight = 0.2
        cost_weight = 0.1
        security_weight = 0.5

        # Adjust weights based on timeliness mode
        if timeliness_mode == "realtime":
            latency_weight = 3.0
            queue_weight = 2.0
        elif timeliness_mode == "interactive":
            latency_weight = 2.0
            queue_weight = 1.0
        elif timeliness_mode == "batch":
            cost_weight = 1.0
            latency_weight = 0.3
        elif timeliness_mode == "durable":
            success_weight = 3.0
            failure_weight = 3.0

        score = (
            latency_weight * self.latency_ms / 100.0
            + load_weight * self.relay_load
            + queue_weight * self.queue_depth / 10.0
            + success_weight * (1.0 - self.delivery_success_rate)
            + failure_weight * self.failure_rate
            + locality_weight * self.locality_score
            + cost_weight * self.cost_score
            + security_weight * (1.0 - self.security_score)
        )
        return score

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON storage."""
        return {
            "route_type": self.route_type,
            "relay_node_id": str(self.relay_node_id) if self.relay_node_id else None,
            "latency_ms": self.latency_ms,
            "relay_load": self.relay_load,
            "queue_depth": self.queue_depth,
            "delivery_success_rate": self.delivery_success_rate,
            "failure_rate": self.failure_rate,
            "locality_score": self.locality_score,
            "cost_score": self.cost_score,
            "security_score": self.security_score,
        }


async def select_route(
    session: AsyncSession,
    *,
    task: Task,
    from_agent: Agent,
    to_agent: Agent,
    message_id: str,
    timeliness_mode: str = "normal",
    trace_id: str | None = None,
    client_network_info: dict | None = None,
    scope_id: uuid.UUID | None = None,
    source_zone_id: uuid.UUID | None = None,
    target_zone_id: uuid.UUID | None = None,
) -> RouteDecision:
    """Select the best route for a task in ENFORCED MODE (Phase 13+).

    This function performs full route selection logic and the decision
    CONTROLS the actual delivery path.

    Hard filtering order:
    1. Authentication (already done by caller)
    2. Agent exists and not disabled (already done by caller)
    3. Connection policy
    4. Route policy (Phase 15)
    5. Risk level and approval status (Phase 15+)
    6. Data boundary and egress rules (Phase 16+)
    7. Route lease (Phase 13+)
    8. Relay health

    Phase 15 additions:
    - Scope/zone-aware routing
    - Route policy evaluation per candidate
    - Regional relay support for cross-zone routing

    Args:
        session: Database session
        task: Task being routed
        from_agent: Source agent
        to_agent: Target agent
        message_id: Message ID for tracking
        timeliness_mode: Timeliness mode (realtime, interactive, normal, batch, durable)
        trace_id: Trace ID for distributed tracing
        client_network_info: Client network information for local-first routing
        scope_id: Network scope ID (from agent or task)
        source_zone_id: Source zone ID (from from_agent)
        target_zone_id: Target zone ID (from to_agent)

    Returns:
        RouteDecision record (persisted to database)

    Raises:
        DomainException: If no valid route can be found or policy denies routing
    """
    start_time = datetime.now(UTC)
    rejection_reasons: dict[str, str] = {}
    candidates: list[RouteCandidate] = []
    applied_policy_id: uuid.UUID | None = None

    if trace_id is None:
        trace_id = str(uuid.uuid4())

    # Extract scope/zone from agents if not provided
    if scope_id is None:
        scope_id = from_agent.scope_id or to_agent.scope_id
    if source_zone_id is None:
        source_zone_id = from_agent.zone_id
    if target_zone_id is None:
        target_zone_id = to_agent.zone_id

    # Hard filter 3: Connection policy
    connection_allowed, connection_reason = await _check_connection_policy(
        session, from_agent, to_agent
    )
    if not connection_allowed:
        # In enforced mode, policy denial fails the task
        logger.warning(
            "Route selection failed: connection policy denied for task=%s from=%s to=%s reason=%s",
            task.id,
            from_agent.agent_number,
            to_agent.agent_number,
            connection_reason,
        )
        raise DomainException(
            ErrorCode.INVALID_REQUEST,
            f"Connection not allowed: {connection_reason}",
        )

    # Hard filter 4: Route policy (Phase 15)
    # Route policies are evaluated per-candidate in the candidate building phase
    # to allow different policies for different route types.
    # Scope/zone-based filtering is applied per-candidate below via
    # _evaluate_route_policy_for_candidate(), which checks policies against
    # scope_id, source_zone_id, and target_zone_id.

    # Hard filter 8: Get healthy relays
    healthy_relays = await _get_healthy_relays(session)

    # Build candidate routes
    # Phase 14: Support personal_edge (local-first routing)
    # Phase 15: Add route policy evaluation per candidate + regional_relay
    # Phase 17: Add dedicated_channel as highest priority

    # Try dedicated channel first if available (Phase 17)
    from app.services.dedicated_channel_service import select_dedicated_channel

    dedicated_channel = None
    try:
        # Use a savepoint to isolate this query
        async with session.begin_nested():
            dedicated_channel = await select_dedicated_channel(
                session, source_agent_id=from_agent.id, target_agent_id=to_agent.id
            )
    except DomainException:
        # Infrastructure error from dedicated channel service - must not silently fall back
        logger.error(
            "Dedicated channel infrastructure failure for task=%s from=%s to=%s, propagating error",
            task.id,
            from_agent.agent_number,
            to_agent.agent_number,
        )
        raise
    except Exception as e:
        # Unexpected error - wrap and propagate as INTERNAL_ERROR
        logger.error(
            "Unexpected error querying dedicated channel for task=%s from=%s to=%s: %s",
            task.id,
            from_agent.agent_number,
            to_agent.agent_number,
            e,
            exc_info=True,
        )
        raise DomainException(
            ErrorCode.INTERNAL_ERROR,
            f"Unexpected error querying dedicated channel: {e}",
            status_code=503,
        )

    if dedicated_channel:
        # Phase 15: Evaluate route policy for dedicated channel
        policy_result = await _evaluate_route_policy_for_candidate(
            session,
            from_agent=from_agent,
            to_agent=to_agent,
            route_type="dedicated_channel",
            task=task,
            scope_id=scope_id,
            source_zone_id=source_zone_id,
            target_zone_id=target_zone_id,
        )

        if policy_result.allowed:
            _raise_if_approval_required("dedicated_channel", policy_result)
            candidate = RouteCandidate("dedicated_channel", None, None)
            # Dedicated channels have best performance
            candidate.latency_ms = dedicated_channel.latency_target_ms or 5.0
            candidate.relay_load = 0.0  # No relay load
            candidate.queue_depth = 0  # Direct connection
            candidate.delivery_success_rate = 0.99  # Very high reliability
            candidate.failure_rate = 0.01
            candidate.security_score = 1.0  # Highest security (dedicated + encrypted)
            candidate.locality_score = 0.0  # Best locality (direct)
            candidate.cost_score = 0.5  # Higher cost but worth it
            candidates.append(candidate)
            logger.info(
                "Added dedicated_channel candidate for task=%s channel=%s",
                task.id,
                dedicated_channel.id,
            )

            # Track applied policy
            if policy_result.policy_id and applied_policy_id is None:
                applied_policy_id = policy_result.policy_id
        else:
            rejection_reasons["dedicated_channel_policy"] = policy_result.reason
            logger.warning(
                "Route policy denied dedicated_channel for task=%s: %s (policy=%s)",
                task.id,
                policy_result.reason,
                policy_result.policy_id,
            )

    # Try personal edge first if available (Phase 14 local-first routing)
    personal_edge_relays = [r for r in healthy_relays if r.node_type == "personal_edge"]
    for edge_relay in personal_edge_relays:
        # Phase 15: Evaluate route policy for this candidate
        policy_result = await _evaluate_route_policy_for_candidate(
            session,
            from_agent=from_agent,
            to_agent=to_agent,
            route_type="personal_edge",
            task=task,
            scope_id=scope_id,
            source_zone_id=source_zone_id,
            target_zone_id=target_zone_id,
        )

        if not policy_result.allowed:
            rejection_reasons["personal_edge_policy"] = policy_result.reason
            logger.warning(
                "Route policy denied personal_edge for task=%s: %s (policy=%s)",
                task.id,
                policy_result.reason,
                policy_result.policy_id,
            )
            # Policy denial is explicit failure - do not add this candidate
            continue

        _raise_if_approval_required("personal_edge", policy_result)

        # Check if on same local network
        is_local = False
        if client_network_info:
            is_local = await check_local_network_match(client_network_info, edge_relay)

        candidate = RouteCandidate("personal_edge", edge_relay.id, edge_relay)
        candidate.latency_ms = edge_relay.avg_latency_ms or 10.0
        candidate.relay_load = edge_relay.current_load or 0.1
        candidate.queue_depth = edge_relay.queue_depth or 0
        candidate.delivery_success_rate = edge_relay.success_rate or 0.90
        candidate.failure_rate = 1.0 - candidate.delivery_success_rate
        candidate.security_score = 0.9
        candidate.locality_score = 0.0 if is_local else 0.5
        candidates.append(candidate)

        # Track applied policy
        if policy_result.policy_id and applied_policy_id is None:
            applied_policy_id = policy_result.policy_id

    # Add regional relay for cross-zone routing (Phase 15)
    if source_zone_id and target_zone_id and source_zone_id != target_zone_id:
        regional_relays = [r for r in healthy_relays if r.node_type == "regional"]
        for regional_relay in regional_relays:
            # Evaluate route policy for regional relay
            policy_result = await _evaluate_route_policy_for_candidate(
                session,
                from_agent=from_agent,
                to_agent=to_agent,
                route_type="regional_relay",
                task=task,
                scope_id=scope_id,
                source_zone_id=source_zone_id,
                target_zone_id=target_zone_id,
            )

            if not policy_result.allowed:
                rejection_reasons["regional_relay_policy"] = policy_result.reason
                logger.warning(
                    "Route policy denied regional_relay for task=%s: %s (policy=%s)",
                    task.id,
                    policy_result.reason,
                    policy_result.policy_id,
                )
                continue

            _raise_if_approval_required("regional_relay", policy_result)

            candidate = RouteCandidate("regional_relay", regional_relay.id, regional_relay)
            candidate.latency_ms = regional_relay.avg_latency_ms or 80.0  # Cross-zone has higher latency
            candidate.relay_load = regional_relay.current_load or 0.1
            candidate.queue_depth = regional_relay.queue_depth or 0
            candidate.delivery_success_rate = regional_relay.success_rate or 0.92
            candidate.failure_rate = 1.0 - candidate.delivery_success_rate
            candidate.security_score = 0.85
            candidate.locality_score = 0.7  # Cross-zone penalty
            candidate.cost_score = 0.3  # Regional routing has cost
            candidates.append(candidate)

            if policy_result.policy_id and applied_policy_id is None:
                applied_policy_id = policy_result.policy_id

    # Add central relay as fallback
    central_relays = [r for r in healthy_relays if r.node_type == "central"]
    if central_relays:
        # Phase 15: Evaluate route policy for central relay
        policy_result = await _evaluate_route_policy_for_candidate(
            session,
            from_agent=from_agent,
            to_agent=to_agent,
            route_type="central_relay",
            task=task,
            scope_id=scope_id,
            source_zone_id=source_zone_id,
            target_zone_id=target_zone_id,
        )

        if policy_result.allowed:
            _raise_if_approval_required("central_relay", policy_result)
            # Use the best central relay
            best_central = min(central_relays, key=lambda r: r.current_load or 0.0)
            candidate = RouteCandidate("central_relay", best_central.id, best_central)
            candidate.latency_ms = best_central.avg_latency_ms or 50.0
            candidate.relay_load = best_central.current_load or 0.1
            candidate.queue_depth = best_central.queue_depth or 0
            candidate.delivery_success_rate = best_central.success_rate or 0.95
            candidate.failure_rate = 1.0 - candidate.delivery_success_rate
            candidate.security_score = 0.8
            candidates.append(candidate)

            if policy_result.policy_id and applied_policy_id is None:
                applied_policy_id = policy_result.policy_id
        else:
            rejection_reasons["central_relay_policy"] = policy_result.reason
            logger.warning(
                "Route policy denied central_relay for task=%s: %s (policy=%s)",
                task.id,
                policy_result.reason,
                policy_result.policy_id,
            )

    # Enforced mode: Must have at least one candidate
    if not candidates:
        # Check if all routes were denied by policy
        policy_denials = [k for k in rejection_reasons.keys() if "policy" in k]
        if policy_denials:
            # Policy denial is explicit failure - no fallback allowed
            logger.error(
                "Enforced mode: All routes denied by policy for task=%s reasons=%s",
                task.id,
                rejection_reasons,
            )
            raise DomainException(
                ErrorCode.ROUTE_POLICY_DENIED,
                f"All routes denied by policy: {', '.join(rejection_reasons.values())}",
            )

        rejection_reasons["no_relay"] = "No healthy relay available (personal_edge, regional, or central)"
        logger.error("Enforced mode: No healthy relay available for task=%s", task.id)
        raise DomainException(
            ErrorCode.INVALID_REQUEST,
            "No healthy relay available for routing",
        )

    # Score candidates
    for candidate in candidates:
        candidate.final_score = candidate.compute_final_score(timeliness_mode)

    # Sort by score (lower is better)
    candidates.sort(key=lambda c: c.final_score)
    selected = candidates[0]

    # Compute decision time
    decision_time_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)

    # Create RouteDecision record
    decision = RouteDecision(
        task_id=task.id,
        message_id=message_id,
        trace_id=trace_id,
        selected_route_type=selected.route_type,
        selected_relay_node_id=selected.relay_node_id,
        candidate_routes=[c.to_dict() for c in candidates],
        rejection_reasons=rejection_reasons,
        timeliness_mode=timeliness_mode,
        final_score=selected.final_score,
        decision_time_ms=decision_time_ms,
        shadow_mode=False,  # Phase 13: enforced mode
        # Phase 15: Topology and policy tracking
        scope_id=scope_id,
        source_zone_id=source_zone_id,
        target_zone_id=target_zone_id,
        policy_id=applied_policy_id,
    )
    session.add(decision)
    await session.flush()

    # Issue route lease for this decision
    from app.services.lease_service import issue_route_lease

    lease = await issue_route_lease(
        session,
        source_agent_id=from_agent.id,
        target_agent_id=to_agent.id,
        route_type=selected.route_type,
        duration_seconds=3600,  # 1 hour default
        max_messages=None,  # Unlimited for now
        max_bytes=None,  # Unlimited for now
        allowed_task_types=None,  # All task types allowed
    )
    decision.lease_id = lease.id
    await session.flush()

    logger.info(
        "Enforced route decision: task=%s route=%s relay=%s score=%.2f time=%dms lease=%s scope=%s source_zone=%s target_zone=%s policy=%s",
        task.id,
        selected.route_type,
        selected.relay_node_id,
        selected.final_score,
        decision_time_ms,
        lease.id,
        scope_id,
        source_zone_id,
        target_zone_id,
        applied_policy_id,
    )

    return decision


async def select_route_shadow(
    session: AsyncSession,
    *,
    task: Task,
    from_agent: Agent,
    to_agent: Agent,
    message_id: str,
    timeliness_mode: str = "normal",
    trace_id: str | None = None,
    client_network_info: dict | None = None,
) -> RouteDecision:
    """Select the best route for a task in SHADOW MODE.

    This function performs full route selection logic but does NOT change
    the actual delivery path. It only records the decision for analysis.

    Shadow mode preserves Phase 12 behavior and does NOT enforce later runtime
    controls. Phase 15+ features (route policy evaluation, risk/approval checks,
    data boundary/egress rules, route lease enforcement) exist in the enforced
    mode function select_route() but are deliberately absent here so shadow mode
    decisions remain comparable to the original Phase 12 baseline.

    Hard filtering order (shadow mode):
    1. Authentication (already done by caller)
    2. Agent exists and not disabled (already done by caller)
    3. Connection policy
    4. Relay health

    Phase 14 additions:
    - Support personal_edge relay type
    - Local network priority (same subnet preferred)
    - Timeliness-aware scoring

    Returns:
        RouteDecision record (persisted to database)
    """
    start_time = datetime.now(UTC)
    rejection_reasons: dict[str, str] = {}
    candidates: list[RouteCandidate] = []

    # Hard filter 3: Connection policy
    # Check if connection is allowed
    connection_allowed, connection_reason = await _check_connection_policy(
        session, from_agent, to_agent
    )
    if not connection_allowed:
        rejection_reasons["connection_policy"] = connection_reason
        # In shadow mode, we still record the decision even if it would fail
        logger.info(
            "Shadow mode: Connection policy would reject %s -> %s: %s",
            from_agent.agent_number,
            to_agent.agent_number,
            connection_reason,
        )

    # Hard filter 8: Get healthy relay nodes
    healthy_relays = await _get_healthy_relays(session)

    # Build candidate routes (shadow mode only uses Phase 12/14 relay types;
    # Phase 15+ regional_relay and egress types are handled in enforced mode)

    # Try personal edge first if available and on same network
    personal_edge_relays = [r for r in healthy_relays if r.node_type == "personal_edge"]
    for edge_relay in personal_edge_relays:
        # Check if on same local network
        is_local = False
        if client_network_info:
            is_local = await check_local_network_match(client_network_info, edge_relay)

        candidate = RouteCandidate("personal_edge", edge_relay.id, edge_relay)
        candidate.latency_ms = edge_relay.avg_latency_ms or 10.0  # Edge is typically faster
        candidate.relay_load = edge_relay.current_load
        candidate.queue_depth = edge_relay.queue_depth
        candidate.delivery_success_rate = edge_relay.success_rate or 0.90
        candidate.failure_rate = 1.0 - candidate.delivery_success_rate
        candidate.security_score = 0.9  # Personal edge has good security (local network)
        candidate.locality_score = 0.0 if is_local else 0.5  # Lower is better, local is best
        candidates.append(candidate)

    # Add central relay as fallback
    central_relay = next((r for r in healthy_relays if r.node_type == "central"), None)

    if central_relay:
        candidate = RouteCandidate("central_relay", central_relay.id, central_relay)
        candidate.latency_ms = central_relay.avg_latency_ms or 50.0
        candidate.relay_load = central_relay.current_load
        candidate.queue_depth = central_relay.queue_depth
        candidate.delivery_success_rate = central_relay.success_rate or 0.95
        candidate.failure_rate = 1.0 - candidate.delivery_success_rate
        candidate.security_score = 0.8  # Central relay has good security
        candidates.append(candidate)
    else:
        # No central relay available
        rejection_reasons["central_relay"] = "No healthy central relay available"
        logger.warning("Shadow mode: No healthy central relay available")

    # Score candidates
    if candidates:
        for candidate in candidates:
            candidate.final_score = candidate.compute_final_score(timeliness_mode)
        # Sort by score (lower is better)
        candidates.sort(key=lambda c: candidate.compute_final_score(timeliness_mode))
        selected = candidates[0]
    else:
        # No candidates available - create a fallback decision
        selected = RouteCandidate("central_relay")
        selected.final_score = 999.0
        rejection_reasons["no_candidates"] = "No route candidates available"

    # Compute decision time
    decision_time_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)

    # Create RouteDecision record
    decision = RouteDecision(
        task_id=task.id,
        message_id=message_id,
        trace_id=trace_id,
        selected_route_type=selected.route_type,
        selected_relay_node_id=selected.relay_node_id,
        candidate_routes=[c.to_dict() for c in candidates],
        rejection_reasons=rejection_reasons,
        timeliness_mode=timeliness_mode,
        final_score=selected.final_score,
        decision_time_ms=decision_time_ms,
        shadow_mode=True,  # Phase 12: shadow mode
    )
    session.add(decision)
    await session.flush()

    logger.info(
        "Shadow route decision: task=%s route=%s relay=%s score=%.2f time=%dms shadow=True",
        task.id,
        selected.route_type,
        selected.relay_node_id,
        selected.final_score or 0.0,
        decision_time_ms,
    )

    return decision


async def _check_connection_policy(
    session: AsyncSession,
    from_agent: Agent,
    to_agent: Agent,
) -> tuple[bool, str]:
    """Check if connection policy allows communication.

    Returns:
        (allowed, reason) tuple
    """
    policy = to_agent.inbound_policy

    if policy == InboundPolicy.PUBLIC.value:
        return True, ""

    if policy == InboundPolicy.PRIVATE.value:
        # Only allow if same owner
        if from_agent.owner_id == to_agent.owner_id:
            return True, ""
        return False, "Target agent has private inbound policy"

    if policy == InboundPolicy.CONTACTS_ONLY.value:
        # Same owner: always allow
        if from_agent.owner_id == to_agent.owner_id:
            return True, ""
        # Check if connection exists and is accepted
        result = await session.execute(
            select(Connection).where(
                Connection.from_agent_id == from_agent.id,
                Connection.to_agent_id == to_agent.id,
                Connection.status == "accepted",
            )
        )
        conn = result.scalar_one_or_none()
        if conn:
            return True, ""
        return False, "Target agent requires accepted connection (contacts_only)"

    if policy == InboundPolicy.REQUEST_APPROVAL.value:
        # Same owner: always allow
        if from_agent.owner_id == to_agent.owner_id:
            return True, ""
        # Check if connection exists and is accepted
        result = await session.execute(
            select(Connection).where(
                Connection.from_agent_id == from_agent.id,
                Connection.to_agent_id == to_agent.id,
                Connection.status == "accepted",
            )
        )
        conn = result.scalar_one_or_none()
        if conn:
            return True, ""
        return False, "Target agent requires approval for new connections"

    return False, f"Unknown inbound policy: {policy}"


async def _get_healthy_relays(session: AsyncSession) -> list[RelayNode]:
    """Get all healthy relay nodes.

    Phase 18: Filter out relays with open circuit breakers.

    Returns:
        List of healthy RelayNode objects
    """
    from app.models.circuit_breaker import CircuitBreaker

    result = await session.execute(
        select(RelayNode).where(
            RelayNode.enabled == True,  # noqa: E712
            RelayNode.status.in_(["healthy", "degraded"]),
        )
    )
    relays = list(result.scalars().all())

    # Get all circuit breakers
    breakers_by_relay = {}
    try:
        # Use a savepoint to isolate this query
        async with session.begin_nested():
            breaker_result = await session.execute(select(CircuitBreaker))
            breakers_by_relay = {b.relay_node_id: b for b in breaker_result.scalars().all()}
    except Exception as e:
        logger.error(
            "Database error querying circuit breakers: %s",
            e,
            exc_info=True,
        )
        raise DomainException(
            ErrorCode.INTERNAL_ERROR,
            f"Failed to query circuit breakers: {e}",
            status_code=503,
        )

    # Phase 18: Filter by circuit breaker state
    now = datetime.now(UTC)
    healthy = []
    for relay in relays:
        # Check circuit breaker state
        breaker = breakers_by_relay.get(relay.id)
        if breaker:
            if breaker.state == "open":
                # Check if circuit should transition to half_open
                if breaker.open_until and now < breaker.open_until:
                    logger.debug(
                        "Relay %s circuit breaker is open, skipping (open until %s)",
                        relay.id,
                        breaker.open_until,
                    )
                    continue
                # Circuit breaker timeout expired, allow (will transition to half_open on use)

        healthy.append(relay)

    return healthy


async def _evaluate_route_policy_for_candidate(
    session: AsyncSession,
    *,
    from_agent: Agent,
    to_agent: Agent,
    route_type: str,
    task: Task,
    scope_id: uuid.UUID | None = None,
    source_zone_id: uuid.UUID | None = None,
    target_zone_id: uuid.UUID | None = None,
) -> "PolicyEvaluationResult":
    """Evaluate route policy for a specific candidate route.

    Phase 15: This function evaluates route policies for a candidate with
    full scope/zone awareness.

    Args:
        session: Database session
        from_agent: Source agent
        to_agent: Target agent
        route_type: Route type to evaluate
        task: Task being routed
        scope_id: Network scope ID
        source_zone_id: Source zone ID
        target_zone_id: Target zone ID

    Returns:
        PolicyEvaluationResult with allowed/denied status
    """
    from app.services.route_policy_service import evaluate_route_policy

    # Calculate payload size (estimate from task)
    payload_bytes = 0
    if task.result:
        import json
        payload_bytes = len(json.dumps(task.result).encode('utf-8'))

    # Determine data type from task
    data_type = "json"  # Default for task payloads

    result = await evaluate_route_policy(
        session,
        from_agent=from_agent,
        to_agent=to_agent,
        route_type=route_type,
        scope_id=scope_id,
        source_zone_id=source_zone_id,
        target_zone_id=target_zone_id,
        payload_bytes=payload_bytes,
        data_type=data_type,
    )

    return result


async def ensure_default_relay_node(session: AsyncSession) -> RelayNode:
    """Ensure a default central relay node exists.

    This is a bootstrap function for Phase 12. In production, relay nodes
    would be registered via the relay node registration API.

    Returns:
        The default central relay node
    """
    result = await session.execute(
        select(RelayNode).where(RelayNode.node_name == "default-central-relay")
    )
    relay = result.scalar_one_or_none()

    if relay is None:
        relay = RelayNode(
            node_name="default-central-relay",
            node_type="central",
            status="healthy",
            current_load=0.1,
            queue_depth=0,
            avg_latency_ms=50.0,
            success_rate=0.95,
            capabilities=["websocket", "task_delivery", "message_routing"],
            max_capacity=10000,
            enabled=True,
            last_heartbeat_at=datetime.now(UTC),
        )
        session.add(relay)
        await session.flush()
        logger.info("Created default central relay node: %s", relay.id)

    return relay
