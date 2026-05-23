"""Unit tests for Route Policy service (Phase 15 Task #2).

Tests policy evaluation logic, priority ordering, policy denial blocking routes,
and data boundary checks.
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.route_policy import RoutePolicy
from app.models.user import User
from app.services.route_policy_service import (
    PolicyEvaluationResult,
    check_data_boundary,
    evaluate_route_policy,
    get_applicable_policies,
)


@pytest.fixture
async def test_user(session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        username=f"testuser_{uuid.uuid4().hex[:8]}",
    )
    session.add(user)
    await session.flush()
    return user


@pytest.fixture
async def test_agents(session: AsyncSession, test_user: User) -> tuple[Agent, Agent]:
    """Create two test agents."""
    agent1 = Agent(
        agent_number=f"AN-{uuid.uuid4().hex[:8].upper()}",
        owner_id=test_user.id,
        name="Agent 1",
        runtime="test",
        inbound_policy="public",
    )
    agent2 = Agent(
        agent_number=f"AN-{uuid.uuid4().hex[:8].upper()}",
        owner_id=test_user.id,
        name="Agent 2",
        runtime="test",
        inbound_policy="public",
    )
    session.add(agent1)
    session.add(agent2)
    await session.flush()
    return agent1, agent2


@pytest.mark.asyncio
async def test_no_policies_allows_by_default(
    session: AsyncSession,
    test_agents: tuple[Agent, Agent],
):
    """Test that routes are allowed when no policies are configured."""
    agent1, agent2 = test_agents

    result = await evaluate_route_policy(
        session,
        from_agent=agent1,
        to_agent=agent2,
        route_type="central_relay",
    )

    assert result.allowed is True
    assert "No policies configured" in result.reason


@pytest.mark.asyncio
async def test_policy_denies_route_type(
    session: AsyncSession,
    test_agents: tuple[Agent, Agent],
):
    """Test that a policy can deny a specific route type."""
    agent1, agent2 = test_agents

    # Create a policy that denies personal_edge
    policy = RoutePolicy(
        policy_name="Deny Personal Edge",
        priority=10,
        denied_route_types=["personal_edge"],
        enabled=True,
    )
    session.add(policy)
    await session.flush()

    # personal_edge should be denied
    result = await evaluate_route_policy(
        session,
        from_agent=agent1,
        to_agent=agent2,
        route_type="personal_edge",
    )

    assert result.allowed is False
    assert "explicitly denied" in result.reason
    assert result.policy_id == policy.id

    # central_relay should be allowed
    result = await evaluate_route_policy(
        session,
        from_agent=agent1,
        to_agent=agent2,
        route_type="central_relay",
    )

    assert result.allowed is True


@pytest.mark.asyncio
async def test_policy_allows_only_specific_routes(
    session: AsyncSession,
    test_agents: tuple[Agent, Agent],
):
    """Test that a policy can whitelist specific route types."""
    agent1, agent2 = test_agents

    # Create a policy that only allows central_relay
    policy = RoutePolicy(
        policy_name="Only Central Relay",
        priority=10,
        allowed_route_types=["central_relay"],
        enabled=True,
    )
    session.add(policy)
    await session.flush()

    # central_relay should be allowed
    result = await evaluate_route_policy(
        session,
        from_agent=agent1,
        to_agent=agent2,
        route_type="central_relay",
    )

    assert result.allowed is True

    # personal_edge should be denied (not in whitelist)
    result = await evaluate_route_policy(
        session,
        from_agent=agent1,
        to_agent=agent2,
        route_type="personal_edge",
    )

    assert result.allowed is False
    assert "not in allowed list" in result.reason


@pytest.mark.asyncio
async def test_denied_takes_precedence_over_allowed(
    session: AsyncSession,
    test_agents: tuple[Agent, Agent],
):
    """Test that denied_route_types takes precedence over allowed_route_types."""
    agent1, agent2 = test_agents

    # Create a policy that allows central_relay but also denies it
    policy = RoutePolicy(
        policy_name="Conflicting Policy",
        priority=10,
        allowed_route_types=["central_relay", "personal_edge"],
        denied_route_types=["central_relay"],
        enabled=True,
    )
    session.add(policy)
    await session.flush()

    # central_relay should be denied (blacklist takes precedence)
    result = await evaluate_route_policy(
        session,
        from_agent=agent1,
        to_agent=agent2,
        route_type="central_relay",
    )

    assert result.allowed is False
    assert "explicitly denied" in result.reason


@pytest.mark.asyncio
async def test_policy_priority_ordering(
    session: AsyncSession,
    test_agents: tuple[Agent, Agent],
):
    """Test that policies are evaluated in priority order (lower number first)."""
    agent1, agent2 = test_agents

    # Create two policies with different priorities
    high_priority_policy = RoutePolicy(
        policy_name="High Priority Deny",
        priority=10,
        denied_route_types=["central_relay"],
        enabled=True,
    )
    low_priority_policy = RoutePolicy(
        policy_name="Low Priority Allow",
        priority=100,
        allowed_route_types=["central_relay"],
        enabled=True,
    )
    session.add(high_priority_policy)
    session.add(low_priority_policy)
    await session.flush()

    # High priority policy should deny first
    result = await evaluate_route_policy(
        session,
        from_agent=agent1,
        to_agent=agent2,
        route_type="central_relay",
    )

    assert result.allowed is False
    assert result.policy_id == high_priority_policy.id


@pytest.mark.asyncio
async def test_policy_requires_approval(
    session: AsyncSession,
    test_agents: tuple[Agent, Agent],
):
    """Test that a policy can require approval for a route."""
    agent1, agent2 = test_agents

    # Create a policy that requires approval
    policy = RoutePolicy(
        policy_name="Require Approval",
        priority=10,
        require_approval=True,
        enabled=True,
    )
    session.add(policy)
    await session.flush()

    result = await evaluate_route_policy(
        session,
        from_agent=agent1,
        to_agent=agent2,
        route_type="central_relay",
    )

    assert result.allowed is True
    assert result.require_approval is True
    assert result.policy_id == policy.id


@pytest.mark.asyncio
async def test_policy_sets_risk_level(
    session: AsyncSession,
    test_agents: tuple[Agent, Agent],
):
    """Test that a policy can set a risk level for a route."""
    agent1, agent2 = test_agents

    # Create a policy with high risk level
    policy = RoutePolicy(
        policy_name="High Risk Route",
        priority=10,
        risk_level="high",
        enabled=True,
    )
    session.add(policy)
    await session.flush()

    result = await evaluate_route_policy(
        session,
        from_agent=agent1,
        to_agent=agent2,
        route_type="central_relay",
    )

    assert result.allowed is True
    assert result.risk_level == "high"


@pytest.mark.asyncio
async def test_disabled_policy_is_ignored(
    session: AsyncSession,
    test_agents: tuple[Agent, Agent],
):
    """Test that disabled policies are not evaluated."""
    agent1, agent2 = test_agents

    # Create a disabled policy that would deny
    policy = RoutePolicy(
        policy_name="Disabled Deny",
        priority=10,
        denied_route_types=["central_relay"],
        enabled=False,
    )
    session.add(policy)
    await session.flush()

    # Route should be allowed because policy is disabled
    result = await evaluate_route_policy(
        session,
        from_agent=agent1,
        to_agent=agent2,
        route_type="central_relay",
    )

    assert result.allowed is True


@pytest.mark.asyncio
async def test_data_boundary_max_payload_bytes(
    session: AsyncSession,
    test_agents: tuple[Agent, Agent],
):
    """Test that data boundary rules can limit payload size."""
    agent1, agent2 = test_agents

    # Create a policy with max payload size
    policy = RoutePolicy(
        policy_name="Limit Payload Size",
        priority=10,
        data_boundary_rules={"max_payload_bytes": 1024},
        enabled=True,
    )
    session.add(policy)
    await session.flush()

    # Small payload should be allowed
    result = await evaluate_route_policy(
        session,
        from_agent=agent1,
        to_agent=agent2,
        route_type="central_relay",
        payload_bytes=512,
    )

    assert result.allowed is True

    # Large payload should be denied
    result = await evaluate_route_policy(
        session,
        from_agent=agent1,
        to_agent=agent2,
        route_type="central_relay",
        payload_bytes=2048,
    )

    assert result.allowed is False
    assert "exceeds limit" in result.reason


@pytest.mark.asyncio
async def test_data_boundary_allowed_data_types(
    session: AsyncSession,
    test_agents: tuple[Agent, Agent],
):
    """Test that data boundary rules can restrict data types."""
    agent1, agent2 = test_agents

    # Create a policy that only allows text and json
    policy = RoutePolicy(
        policy_name="Restrict Data Types",
        priority=10,
        data_boundary_rules={"allowed_data_types": ["text", "json"]},
        enabled=True,
    )
    session.add(policy)
    await session.flush()

    # text should be allowed
    result = await evaluate_route_policy(
        session,
        from_agent=agent1,
        to_agent=agent2,
        route_type="central_relay",
        data_type="text",
    )

    assert result.allowed is True

    # binary should be denied
    result = await evaluate_route_policy(
        session,
        from_agent=agent1,
        to_agent=agent2,
        route_type="central_relay",
        data_type="binary",
    )

    assert result.allowed is False
    assert "not in allowed types" in result.reason


def test_check_data_boundary_max_bytes():
    """Test data boundary check for max payload bytes."""
    rules = {"max_payload_bytes": 1000}

    # Within limit
    result = check_data_boundary(rules, payload_bytes=500, data_type=None)
    assert result.allowed is True

    # Exceeds limit
    result = check_data_boundary(rules, payload_bytes=1500, data_type=None)
    assert result.allowed is False
    assert "exceeds limit" in result.reason


def test_check_data_boundary_allowed_types():
    """Test data boundary check for allowed data types."""
    rules = {"allowed_data_types": ["text", "json"]}

    # Allowed type
    result = check_data_boundary(rules, payload_bytes=0, data_type="text")
    assert result.allowed is True

    # Disallowed type
    result = check_data_boundary(rules, payload_bytes=0, data_type="binary")
    assert result.allowed is False
    assert "not in allowed types" in result.reason


@pytest.mark.asyncio
async def test_get_applicable_policies_ordering(session: AsyncSession):
    """Test that get_applicable_policies returns policies in priority order."""
    # Create policies with different priorities
    policy1 = RoutePolicy(policy_name="P1", priority=100, enabled=True)
    policy2 = RoutePolicy(policy_name="P2", priority=10, enabled=True)
    policy3 = RoutePolicy(policy_name="P3", priority=50, enabled=True)

    session.add(policy1)
    session.add(policy2)
    session.add(policy3)
    await session.flush()

    policies = await get_applicable_policies(session)

    # Should be ordered by priority (lower number first)
    assert len(policies) == 3
    assert policies[0].priority == 10
    assert policies[1].priority == 50
    assert policies[2].priority == 100
