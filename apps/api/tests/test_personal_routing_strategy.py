"""0033: personal routing strategy (backend).

Covers:
1. PATCH /v1/personal/scope persists routing_strategy and echoes it back
2. Invalid strategy values are rejected with 422 (Pydantic Literal)
3. GET /v1/personal/scope returns the new field (auto-create default)
4. compute_final_score: 'normal' is an identity transform for all five
   timeliness modes (regression anchor vs the pre-0033 formula)
5. 'fast' ranks candidates purely by latency (7 non-latency weights,
   including security_score, are zeroed)
6. 'reliable' favors delivery success (success/failure x1.5, latency x0.5)
7. select_route with 'reliable' excludes 'degraded' relays from
   candidacy and fails closed when no candidate survives
8. Hot-path wiring: task_service reads the PersonalScope row once and
   passes routing_strategy to select_route (D2)
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DomainException
from app.models.agent import Agent
from app.models.personal_scope import PersonalScope
from app.models.relay_node import RelayNode
from app.models.task import Task
from app.models.user import User
from app.protocol.constants import ErrorCode
from app.services.auth import create_api_key_for_user
from app.services.path_optimizer import RouteCandidate, select_route
from app.services.personal_scope_service import (
    get_personal_scope,
    get_routing_strategy,
)

TIMELINESS_MODES = ("realtime", "interactive", "normal", "batch", "durable")


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


async def _make_user_with_key(session: AsyncSession) -> tuple[User, str]:
    """Create a user + plain API key directly (no register endpoint)."""
    user = User(username=f"prs-{uuid.uuid4().hex[:8]}")
    session.add(user)
    await session.flush()
    raw_key = await create_api_key_for_user(user, "prs-test", session)
    await session.commit()  # conftest patch: commit() -> flush()
    await session.refresh(user)
    return user, raw_key


@pytest.fixture
async def test_user(session: AsyncSession) -> User:
    user = User(username=f"prsuser-{uuid.uuid4().hex[:8]}", role="user")
    session.add(user)
    await session.flush()
    return user


@pytest.fixture
async def agent_pair(session: AsyncSession, test_user: User) -> tuple[Agent, Agent]:
    """Two public, zone-less agents (same-zone/personal_edge not exercised)."""
    agent_a = Agent(
        owner_id=test_user.id,
        agent_number=f"AN-{uuid.uuid4().hex[:12].upper()}",
        name="Agent A",
        runtime="python",
        inbound_policy="public",
    )
    agent_b = Agent(
        owner_id=test_user.id,
        agent_number=f"AN-{uuid.uuid4().hex[:12].upper()}",
        name="Agent B",
        runtime="python",
        inbound_policy="public",
    )
    session.add_all([agent_a, agent_b])
    await session.flush()
    return agent_a, agent_b


def _make_relay(
    name: str,
    *,
    status: str = "healthy",
    node_type: str = "central",
    load: float = 0.3,
    latency_ms: float = 50.0,
    success_rate: float = 0.95,
) -> RelayNode:
    return RelayNode(
        node_name=name,
        node_type=node_type,
        status=status,
        current_load=load,
        queue_depth=5,
        avg_latency_ms=latency_ms,
        success_rate=success_rate,
        capabilities=["websocket", "task_delivery"],
        max_capacity=10000,
        enabled=True,
        last_heartbeat_at=datetime.now(UTC),
    )


async def _isolate_central_relays(session: AsyncSession, *keep: RelayNode) -> None:
    """Disable every other enabled central relay for this (rolled-back) session.

    The test database is shared, so healthy central relays left behind by
    other suites would otherwise interfere with candidate assertions.
    This mutation lives inside the conftest session fixture and is rolled
    back at the end of the test.
    """
    keep_ids = {r.id for r in keep}
    result = await session.execute(
        select(RelayNode).where(
            RelayNode.node_type == "central",
            RelayNode.enabled == True,  # noqa: E712
        )
    )
    for relay in result.scalars():
        if relay.id not in keep_ids:
            relay.enabled = False
    await session.flush()


async def _make_task(session: AsyncSession, agent_a: Agent, agent_b: Agent) -> Task:
    task = Task(
        created_by=agent_a.id,
        assigned_to=agent_b.id,
        status="created",
    )
    session.add(task)
    await session.flush()
    return task


def _full_candidate() -> RouteCandidate:
    """A candidate with every scoring dimension populated."""
    c = RouteCandidate("central_relay")
    c.latency_ms = 120.0
    c.relay_load = 0.4
    c.queue_depth = 7
    c.delivery_success_rate = 0.9
    c.failure_rate = 0.1
    c.locality_score = 0.3
    c.cost_score = 0.2
    c.security_score = 0.7
    return c


def _legacy_score(c: RouteCandidate, timeliness_mode: str) -> float:
    """The pre-0033 scoring formula, verbatim (regression anchor)."""
    latency_weight = 1.0
    load_weight = 0.5
    queue_weight = 0.3
    success_weight = 2.0
    failure_weight = 2.0
    locality_weight = 0.2
    cost_weight = 0.1
    security_weight = 0.5

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

    return (
        latency_weight * c.latency_ms / 100.0
        + load_weight * c.relay_load
        + queue_weight * c.queue_depth / 10.0
        + success_weight * (1.0 - c.delivery_success_rate)
        + failure_weight * c.failure_rate
        + locality_weight * c.locality_score
        + cost_weight * c.cost_score
        + security_weight * (1.0 - c.security_score)
    )


# ---------------------------------------------------------------------------
# 1-3: REST API (routing_strategy persistence / validation / echo)
# ---------------------------------------------------------------------------


class TestRoutingStrategyAPI:
    async def test_get_scope_returns_routing_strategy_default(self, client, session):
        _, raw_key = await _make_user_with_key(session)
        resp = await client.get(
            "/v1/personal/scope", headers={"X-API-Key": raw_key}
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["routing_strategy"] == "normal"

    async def test_patch_routing_strategy_persists_and_echo(self, client, session):
        _, raw_key = await _make_user_with_key(session)
        headers = {"X-API-Key": raw_key}

        for strategy in ("fast", "reliable", "normal"):
            resp = await client.patch(
                "/v1/personal/scope",
                json={"routing_strategy": strategy},
                headers=headers,
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["routing_strategy"] == strategy

            # Persisted: a fresh GET reflects the stored value
            resp = await client.get("/v1/personal/scope", headers=headers)
            assert resp.status_code == 200, resp.text
            assert resp.json()["routing_strategy"] == strategy

    async def test_patch_invalid_routing_strategy_rejected_422(self, client, session):
        _, raw_key = await _make_user_with_key(session)
        resp = await client.patch(
            "/v1/personal/scope",
            json={"routing_strategy": "turbo"},
            headers={"X-API-Key": raw_key},
        )
        assert resp.status_code == 422, resp.text

        # Unchanged / still the default (nothing partially written)
        resp = await client.get("/v1/personal/scope", headers={"X-API-Key": raw_key})
        assert resp.json()["routing_strategy"] == "normal"


# ---------------------------------------------------------------------------
# 4-6: compute_final_score strategy override
# ---------------------------------------------------------------------------


class TestComputeFinalScoreStrategy:
    def test_normal_is_identity_for_all_timeliness_modes(self):
        """'normal' must reproduce the pre-0033 formula byte-for-byte."""
        candidate = _full_candidate()
        for mode in TIMELINESS_MODES:
            legacy = _legacy_score(candidate, mode)
            assert candidate.compute_final_score(mode) == legacy, mode
            assert candidate.compute_final_score(mode, "normal") == legacy, mode
            # Unknown values also fall back to identity behavior
            assert candidate.compute_final_score(mode, "bogus") == legacy, mode

    def test_fast_only_contains_latency_term(self):
        candidate = _full_candidate()
        mode = "normal"
        # Base latency weight for 'normal' is 1.0; fast raises it to max(1.0, 3.0)
        expected = 3.0 * candidate.latency_ms / 100.0
        assert candidate.compute_final_score(mode, "fast") == expected

        # The 7 non-latency dimensions (incl. security_score) do not
        # influence the fast score at all.
        for dim, value in [
            ("relay_load", 0.99),
            ("queue_depth", 500),
            ("delivery_success_rate", 0.01),
            ("failure_rate", 1.0),
            ("locality_score", 1.0),
            ("cost_score", 1.0),
            ("security_score", 0.0),
        ]:
            tuned = _full_candidate()
            setattr(tuned, dim, value)
            assert tuned.compute_final_score(mode, "fast") == expected

        # 'realtime' already sets latency_weight=3.0 -> fast keeps 3.0
        realtime_expected = 3.0 * candidate.latency_ms / 100.0
        assert candidate.compute_final_score("realtime", "fast") == realtime_expected

    def test_reliable_favors_success_rate(self):
        candidate = _full_candidate()
        mode = "normal"
        # reliable: success/failure x1.5, latency x0.5, other weights intact
        expected = (
            0.5 * 1.0 * candidate.latency_ms / 100.0
            + 0.5 * candidate.relay_load
            + 0.3 * candidate.queue_depth / 10.0
            + 1.5 * 2.0 * (1.0 - candidate.delivery_success_rate)
            + 1.5 * 2.0 * candidate.failure_rate
            + 0.2 * candidate.locality_score
            + 0.1 * candidate.cost_score
            + 0.5 * (1.0 - candidate.security_score)
        )
        assert candidate.compute_final_score(mode, "reliable") == expected

        # Two candidates differing only in success rate + latency:
        # 'normal' picks the low-latency one, 'reliable' flips the order
        # toward the high-success one.
        fast_and_risky = RouteCandidate("central_relay")
        fast_and_risky.latency_ms = 50.0
        fast_and_risky.delivery_success_rate = 0.80
        fast_and_risky.failure_rate = 0.20
        slow_and_steady = RouteCandidate("central_relay")
        slow_and_steady.latency_ms = 150.0
        slow_and_steady.delivery_success_rate = 0.99
        slow_and_steady.failure_rate = 0.01

        scores_normal = {
            "fast_and_risky": fast_and_risky.compute_final_score("normal"),
            "slow_and_steady": slow_and_steady.compute_final_score("normal"),
        }
        scores_reliable = {
            "fast_and_risky": fast_and_risky.compute_final_score("normal", "reliable"),
            "slow_and_steady": slow_and_steady.compute_final_score(
                "normal", "reliable"
            ),
        }
        assert scores_normal["fast_and_risky"] < scores_normal["slow_and_steady"]
        assert scores_reliable["slow_and_steady"] < scores_reliable["fast_and_risky"]


# ---------------------------------------------------------------------------
# 7: select_route 'reliable' degraded health gate
# ---------------------------------------------------------------------------


class TestSelectRouteReliableStrategy:
    async def test_reliable_excludes_degraded_relay(
        self, session, agent_pair, test_user
    ):
        agent_a, agent_b = agent_pair
        healthy = _make_relay("prs-healthy", load=0.2, latency_ms=100.0)
        degraded = _make_relay(
            "prs-degraded", status="degraded", load=0.1, latency_ms=10.0
        )
        session.add_all([healthy, degraded])
        await session.flush()
        await _isolate_central_relays(session, healthy, degraded)

        task = await _make_task(session, agent_a, agent_b)

        # Sanity: with 'normal', the lower-load degraded relay becomes the
        # single central candidate and is selected.
        decision_normal = await select_route(
            session,
            task=task,
            from_agent=agent_a,
            to_agent=agent_b,
            message_id="prs-normal-1",
        )
        assert decision_normal.selected_relay_node_id == degraded.id

        # 'reliable': the degraded relay is excluded from candidacy; the
        # healthy relay is selected instead.
        task2 = await _make_task(session, agent_a, agent_b)
        decision_reliable = await select_route(
            session,
            task=task2,
            from_agent=agent_a,
            to_agent=agent_b,
            message_id="prs-reliable-1",
            routing_strategy="reliable",
        )
        candidate_ids = [c["relay_node_id"] for c in decision_reliable.candidate_routes]
        assert str(degraded.id) not in candidate_ids
        assert decision_reliable.selected_relay_node_id == healthy.id

    async def test_reliable_fails_closed_without_candidates(
        self, session, agent_pair, test_user
    ):
        agent_a, agent_b = agent_pair
        degraded = _make_relay("prs-only-degraded", status="degraded", load=0.1)
        session.add(degraded)
        await session.flush()
        await _isolate_central_relays(session, degraded)

        task = await _make_task(session, agent_a, agent_b)
        with pytest.raises(DomainException) as exc_info:
            await select_route(
                session,
                task=task,
                from_agent=agent_a,
                to_agent=agent_b,
                message_id="prs-reliable-2",
                routing_strategy="reliable",
            )
        # Fail-closed outcome: either the no-relay refusal (INVALID_REQUEST)
        # or a policy denial — never a silent degraded fallback.
        assert exc_info.value.code in (
            ErrorCode.INVALID_REQUEST.value,
            ErrorCode.ROUTE_POLICY_DENIED.value,
        )


# ---------------------------------------------------------------------------
# 8: hot-path wiring (single read; strategy passed to select_route)
# ---------------------------------------------------------------------------


class TestPersonalScopeServiceAndWiring:
    async def test_get_personal_scope_and_routing_strategy(self, session, test_user):
        assert await get_personal_scope(session, None) is None
        assert get_routing_strategy(None) == "normal"

        scope = PersonalScope(
            user_id=test_user.id, routing_strategy="fast", enable_edge_relay=True
        )
        session.add(scope)
        await session.flush()

        found = await get_personal_scope(session, test_user.id)
        assert found is not None
        assert found.id == scope.id
        assert get_routing_strategy(found) == "fast"

        # Defensive: a value outside the allowed set falls back to 'normal'
        found.routing_strategy = "turbo"
        assert get_routing_strategy(found) == "normal"

    async def test_create_task_passes_strategy_to_select_route(
        self, session, agent_pair, test_user
    ):
        from unittest.mock import AsyncMock, patch
        from types import SimpleNamespace

        from app.services.task_service import create_task

        agent_a, agent_b = agent_pair

        # A PersonalScope row with a non-default strategy
        scope = PersonalScope(
            user_id=test_user.id, routing_strategy="reliable", enable_edge_relay=True
        )
        session.add(scope)
        await session.flush()

        captured: dict = {}

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
                from_agent=agent_a,
                to_agent_number=agent_b.agent_number,
                idempotency_key=f"prs-{uuid.uuid4().hex[:8]}",
                payload={"hello": "world"},
            )

        assert captured.get("routing_strategy") == "reliable"
        assert captured.get("enable_edge_relay") is True

    async def test_create_task_defaults_strategy_when_scope_missing(
        self, session, agent_pair, test_user
    ):
        from unittest.mock import AsyncMock, patch
        from types import SimpleNamespace

        from app.services.task_service import create_task

        agent_a, agent_b = agent_pair
        # No PersonalScope row for test_user

        captured: dict = {}

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
                from_agent=agent_a,
                to_agent_number=agent_b.agent_number,
                idempotency_key=f"prs-{uuid.uuid4().hex[:8]}",
                payload={"hello": "world"},
            )

        assert captured.get("routing_strategy") == "normal"
        assert captured.get("enable_edge_relay") is False
