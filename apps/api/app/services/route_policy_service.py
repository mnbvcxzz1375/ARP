"""Route Policy service: evaluate routing policies for enterprise topology.

This service implements policy-based routing constraints. Policies are evaluated
in priority order (lower number = higher priority). A policy denial MUST fail
the route selection - no fallback is allowed.

Key principles:
1. Policy denial is explicit failure, not fallback
2. All policy decisions are auditable
3. Priority order determines evaluation sequence
4. Denied routes take precedence over allowed routes
"""

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.route_policy import RoutePolicy

logger = logging.getLogger(__name__)


class PolicyEvaluationResult:
    """Result of policy evaluation for a route."""

    def __init__(self, allowed: bool, reason: str = "", policy_id: uuid.UUID | None = None):
        self.allowed = allowed
        self.reason = reason
        self.policy_id = policy_id
        self.risk_level: str | None = None
        self.require_approval: bool = False


async def evaluate_route_policy(
    session: AsyncSession,
    *,
    from_agent: Agent,
    to_agent: Agent,
    route_type: str,
    scope_id: uuid.UUID | None = None,
    source_zone_id: uuid.UUID | None = None,
    target_zone_id: uuid.UUID | None = None,
    payload_bytes: int = 0,
    data_type: str | None = None,
) -> PolicyEvaluationResult:
    """Evaluate if a route is allowed by route policies.

    This function evaluates all applicable policies in priority order.
    If any policy denies the route, evaluation stops and returns denial.
    If a policy requires approval, that is recorded in the result.

    Args:
        session: Database session
        from_agent: Source agent
        to_agent: Target agent
        route_type: Route type (e.g., "central_relay", "personal_edge", "regional")
        scope_id: Network scope ID (optional, Phase 15 Task #1)
        source_zone_id: Source zone ID (optional, Phase 15 Task #1)
        target_zone_id: Target zone ID (optional, Phase 15 Task #1)
        payload_bytes: Payload size in bytes
        data_type: Data type (e.g., "text", "json", "binary")

    Returns:
        PolicyEvaluationResult with allowed/denied status and reason

    Raises:
        No exceptions - returns denial result instead
    """
    # Get applicable policies
    policies = await get_applicable_policies(
        session,
        scope_id=scope_id,
        source_zone_id=source_zone_id,
        target_zone_id=target_zone_id,
    )

    if not policies:
        # No policies configured - allow by default
        logger.debug(
            "No route policies found for scope=%s source_zone=%s target_zone=%s - allowing by default",
            scope_id,
            source_zone_id,
            target_zone_id,
        )
        return PolicyEvaluationResult(allowed=True, reason="No policies configured")

    # Evaluate policies in priority order
    last_allow_result = None
    for policy in policies:
        result = _evaluate_single_policy(
            policy,
            route_type=route_type,
            payload_bytes=payload_bytes,
            data_type=data_type,
        )

        if not result.allowed:
            # Policy denial - stop evaluation and return denial
            logger.warning(
                "Route policy %s (%s) denied route_type=%s from=%s to=%s reason=%s",
                policy.id,
                policy.policy_name,
                route_type,
                from_agent.agent_number,
                to_agent.agent_number,
                result.reason,
            )
            return result

        # Policy allows - track this result
        last_allow_result = result

        # If policy has constraints (approval or risk level), return immediately
        if result.require_approval or result.risk_level:
            logger.info(
                "Route policy %s (%s) allows route_type=%s with constraints: approval=%s risk=%s",
                policy.id,
                policy.policy_name,
                route_type,
                result.require_approval,
                result.risk_level,
            )
            return result

    # All policies allow - return the last policy's result (which includes policy_id)
    if last_allow_result:
        logger.debug(
            "All route policies allow route_type=%s from=%s to=%s (last_policy=%s)",
            route_type,
            from_agent.agent_number,
            to_agent.agent_number,
            last_allow_result.policy_id,
        )
        return last_allow_result

    # No policies evaluated (shouldn't happen, but handle gracefully)
    logger.debug(
        "All route policies allow route_type=%s from=%s to=%s",
        route_type,
        from_agent.agent_number,
        to_agent.agent_number,
    )
    return PolicyEvaluationResult(allowed=True, reason="All policies allow")


async def get_applicable_policies(
    session: AsyncSession,
    *,
    scope_id: uuid.UUID | None = None,
    source_zone_id: uuid.UUID | None = None,
    target_zone_id: uuid.UUID | None = None,
) -> list[RoutePolicy]:
    """Get applicable route policies for a scope/zone pair.

    Policies are returned in priority order (lower number = higher priority).

    Args:
        session: Database session
        scope_id: Network scope ID (optional)
        source_zone_id: Source zone ID (optional)
        target_zone_id: Target zone ID (optional)

    Returns:
        List of RoutePolicy objects sorted by priority
    """
    query = select(RoutePolicy).where(RoutePolicy.enabled == True)  # noqa: E712

    # Filter by scope if provided
    if scope_id is not None:
        query = query.where(
            (RoutePolicy.scope_id == scope_id) | (RoutePolicy.scope_id.is_(None))
        )

    # Filter by zones if provided
    if source_zone_id is not None:
        query = query.where(
            (RoutePolicy.source_zone_id == source_zone_id)
            | (RoutePolicy.source_zone_id.is_(None))
        )

    if target_zone_id is not None:
        query = query.where(
            (RoutePolicy.target_zone_id == target_zone_id)
            | (RoutePolicy.target_zone_id.is_(None))
        )

    # Sort by priority (lower number = higher priority)
    query = query.order_by(RoutePolicy.priority.asc())

    result = await session.execute(query)
    policies = list(result.scalars().all())

    logger.debug(
        "Found %d applicable route policies for scope=%s source_zone=%s target_zone=%s",
        len(policies),
        scope_id,
        source_zone_id,
        target_zone_id,
    )

    return policies


def _evaluate_single_policy(
    policy: RoutePolicy,
    *,
    route_type: str,
    payload_bytes: int,
    data_type: str | None,
) -> PolicyEvaluationResult:
    """Evaluate a single policy against a route.

    Args:
        policy: RoutePolicy to evaluate
        route_type: Route type to check
        payload_bytes: Payload size in bytes
        data_type: Data type (optional)

    Returns:
        PolicyEvaluationResult with allowed/denied status
    """
    # Check denied routes first (blacklist takes precedence)
    if policy.denied_route_types and route_type in policy.denied_route_types:
        return PolicyEvaluationResult(
            allowed=False,
            reason=f"Route type '{route_type}' is explicitly denied by policy '{policy.policy_name}'",
            policy_id=policy.id,
        )

    # Check allowed routes (whitelist)
    if policy.allowed_route_types and route_type not in policy.allowed_route_types:
        return PolicyEvaluationResult(
            allowed=False,
            reason=f"Route type '{route_type}' is not in allowed list for policy '{policy.policy_name}'",
            policy_id=policy.id,
        )

    # Check data boundary rules
    if policy.data_boundary_rules:
        boundary_result = check_data_boundary(
            policy.data_boundary_rules,
            payload_bytes=payload_bytes,
            data_type=data_type,
        )
        if not boundary_result.allowed:
            return PolicyEvaluationResult(
                allowed=False,
                reason=f"Data boundary violation: {boundary_result.reason}",
                policy_id=policy.id,
            )

    # Policy allows - set constraints
    result = PolicyEvaluationResult(
        allowed=True,
        reason=f"Allowed by policy '{policy.policy_name}'",
        policy_id=policy.id,
    )
    result.require_approval = policy.require_approval
    result.risk_level = policy.risk_level

    return result


def check_data_boundary(
    rules: dict[str, Any],
    *,
    payload_bytes: int,
    data_type: str | None,
) -> PolicyEvaluationResult:
    """Check if data meets boundary rules.

    Supported rules:
    - max_payload_bytes: Maximum payload size in bytes
    - allowed_data_types: List of allowed data types
    - deny_pii: Boolean flag to deny PII data (not implemented yet)

    Args:
        rules: Data boundary rules dictionary
        payload_bytes: Payload size in bytes
        data_type: Data type (optional)

    Returns:
        PolicyEvaluationResult with allowed/denied status
    """
    # Check max payload size
    max_bytes = rules.get("max_payload_bytes")
    if max_bytes is not None and payload_bytes > max_bytes:
        return PolicyEvaluationResult(
            allowed=False,
            reason=f"Payload size {payload_bytes} exceeds limit {max_bytes}",
        )

    # Check allowed data types
    allowed_types = rules.get("allowed_data_types")
    if allowed_types is not None and data_type is not None:
        if data_type not in allowed_types:
            return PolicyEvaluationResult(
                allowed=False,
                reason=f"Data type '{data_type}' not in allowed types {allowed_types}",
            )

    # PII detection not implemented yet - fail closed for safety
    deny_pii = rules.get("deny_pii", False)
    if deny_pii:
        logger.warning("PII detection requested but not implemented - failing closed")
        return PolicyEvaluationResult(
            allowed=False,
            reason="PII detection not implemented, fail closed for safety",
        )

    return PolicyEvaluationResult(allowed=True, reason="Data boundary rules satisfied")
