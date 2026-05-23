"""Tests for route lease service with allowed_task_types enforcement."""

import pytest

from app.models.agent import Agent
from app.models.route_lease import RouteLease
from app.models.task import Task
from app.services.lease_service import issue_route_lease, verify_route_lease


@pytest.fixture
async def source_agent(session, sample_user) -> Agent:
    agent = Agent(
        agent_number="900001",
        owner_id=sample_user.id,
        name="SourceAgent",
        runtime="test",
        inbound_policy="public",
    )
    session.add(agent)
    await session.commit()
    await session.refresh(agent)
    return agent


@pytest.fixture
async def target_agent(session, sample_user) -> Agent:
    agent = Agent(
        agent_number="900002",
        owner_id=sample_user.id,
        name="TargetAgent",
        runtime="test",
        inbound_policy="public",
    )
    session.add(agent)
    await session.commit()
    await session.refresh(agent)
    return agent


@pytest.fixture
async def lease_with_types(session, source_agent, target_agent) -> RouteLease:
    """RouteLease with allowed_task_types restricted."""
    return await issue_route_lease(
        session,
        source_agent_id=source_agent.id,
        target_agent_id=target_agent.id,
        route_type="direct",
        duration_seconds=3600,
        allowed_task_types=["data_processing", "inference"],
    )


@pytest.fixture
async def lease_without_types(session, source_agent, target_agent) -> RouteLease:
    """RouteLease with allowed_task_types=None (unrestricted)."""
    return await issue_route_lease(
        session,
        source_agent_id=source_agent.id,
        target_agent_id=target_agent.id,
        route_type="direct",
        duration_seconds=3600,
        allowed_task_types=None,
    )


def _make_task(session, route_policy_hint: str | None) -> Task:
    task = Task(
        idempotency_key="test-lease-key",
        created_by=None,
        assigned_to=None,
        status="created",
        route_policy_hint=route_policy_hint,
    )
    session.add(task)
    return task


class TestAllowedTaskTypesNone:
    """allowed_task_types=None should allow any task through."""

    async def test_passes_task_with_hint(self, session, source_agent, target_agent, lease_without_types):
        task = _make_task(session, "data_processing")
        result = await verify_route_lease(
            session,
            source_agent_id=source_agent.id,
            target_agent_id=target_agent.id,
            route_type="direct",
            task=task,
            message_size_bytes=100,
        )
        assert result is lease_without_types

    async def test_passes_task_without_hint(self, session, source_agent, target_agent, lease_without_types):
        task = _make_task(session, None)
        result = await verify_route_lease(
            session,
            source_agent_id=source_agent.id,
            target_agent_id=target_agent.id,
            route_type="direct",
            task=task,
            message_size_bytes=100,
        )
        assert result is lease_without_types


class TestAllowedTaskTypesRestricted:
    """allowed_task_types set should enforce route_policy_hint matching."""

    async def test_passes_when_hint_matches(self, session, source_agent, target_agent, lease_with_types):
        task = _make_task(session, "data_processing")
        result = await verify_route_lease(
            session,
            source_agent_id=source_agent.id,
            target_agent_id=target_agent.id,
            route_type="direct",
            task=task,
            message_size_bytes=100,
        )
        assert result is lease_with_types

    async def test_fails_closed_when_hint_is_none(self, session, source_agent, target_agent, lease_with_types):
        task = _make_task(session, None)
        result = await verify_route_lease(
            session,
            source_agent_id=source_agent.id,
            target_agent_id=target_agent.id,
            route_type="direct",
            task=task,
            message_size_bytes=100,
        )
        assert result is None

    async def test_fails_when_hint_not_in_allowed(self, session, source_agent, target_agent, lease_with_types):
        task = _make_task(session, "image_generation")
        result = await verify_route_lease(
            session,
            source_agent_id=source_agent.id,
            target_agent_id=target_agent.id,
            route_type="direct",
            task=task,
            message_size_bytes=100,
        )
        assert result is None

    async def test_fails_closed_when_hint_is_empty_string(self, session, source_agent, target_agent, lease_with_types):
        task = _make_task(session, "")
        result = await verify_route_lease(
            session,
            source_agent_id=source_agent.id,
            target_agent_id=target_agent.id,
            route_type="direct",
            task=task,
            message_size_bytes=100,
        )
        assert result is None


class TestMultipleActiveLeases:
    """Multiple active leases for the same agent pair must not cause MultipleResultsFound."""

    async def test_verify_with_lease_id_returns_correct_lease(
        self, session, source_agent, target_agent,
    ):
        """Passing lease_id must return that specific lease, not raise."""
        lease1 = await issue_route_lease(
            session,
            source_agent_id=source_agent.id,
            target_agent_id=target_agent.id,
            route_type="direct",
            duration_seconds=3600,
        )
        lease2 = await issue_route_lease(
            session,
            source_agent_id=source_agent.id,
            target_agent_id=target_agent.id,
            route_type="direct",
            duration_seconds=3600,
        )
        task = _make_task(session, None)

        # Should return lease2, not raise MultipleResultsFound
        result = await verify_route_lease(
            session,
            source_agent_id=source_agent.id,
            target_agent_id=target_agent.id,
            route_type="direct",
            task=task,
            message_size_bytes=100,
            lease_id=lease2.id,
        )
        assert result is not None
        assert result.id == lease2.id

    async def test_verify_without_lease_id_returns_latest(
        self, session, source_agent, target_agent,
    ):
        """Without lease_id, the latest active lease should be returned."""
        lease1 = await issue_route_lease(
            session,
            source_agent_id=source_agent.id,
            target_agent_id=target_agent.id,
            route_type="direct",
            duration_seconds=3600,
        )
        lease2 = await issue_route_lease(
            session,
            source_agent_id=source_agent.id,
            target_agent_id=target_agent.id,
            route_type="direct",
            duration_seconds=3600,
        )
        task = _make_task(session, None)

        # Should return the latest lease without raising
        result = await verify_route_lease(
            session,
            source_agent_id=source_agent.id,
            target_agent_id=target_agent.id,
            route_type="direct",
            task=task,
            message_size_bytes=100,
        )
        assert result is not None
        assert result.id == lease2.id
