"""Tests for the cleanup workers (expired leases + stale edge relays).

Covers:
- P1: cleanup_expired_leases batch rate limiting (500 rows/batch, ≤10
  batches/cycle, deterministic id ordering, remaining rows deferred).
- M1: single-cycle functions (lease_cleanup_cycle / stale_relay_cleanup_cycle)
  are directly testable with an injected session; loop wrappers follow the
  retry_worker pattern (per-cycle lock, graceful CancelledError, isolated
  per-cycle exceptions).
- service-level coverage for edge_discovery.cleanup_stale_edge_relays, which
  previously had zero tests.
- lifespan worker registration, verified by reading main.py's lifespan source
  (the suite has no established pattern for driving a real lifespan context).
"""

import asyncio
import inspect
import re
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update

from app.models.agent import Agent
from app.models.relay_node import RelayNode
from app.models.route_lease import RouteLease
from app.services import lease_service
from app.services.edge_discovery import cleanup_stale_edge_relays
from app.workers import cleanup_worker

# ---------------------------------------------------------------- fixtures


@pytest.fixture
async def two_agents(session, sample_user) -> tuple[Agent, Agent]:
    """A (source, target) agent pair for seeding RouteLease rows."""
    agents = []
    for number, name in (("910001", "LeaseSource"), ("910002", "LeaseTarget")):
        agent = Agent(
            agent_number=number,
            owner_id=sample_user.id,
            name=name,
            runtime="test",
            inbound_policy="public",
        )
        session.add(agent)
        agents.append(agent)
    await session.commit()
    return agents[0], agents[1]


async def _seed_leases(
    session,
    source: Agent,
    target: Agent,
    count: int,
    *,
    expired: bool,
) -> list[RouteLease]:
    """Seed `count` RouteLease rows, all expired or all active."""
    expires_at = (
        datetime.now(UTC) - timedelta(hours=1)
        if expired
        else datetime.now(UTC) + timedelta(hours=1)
    )
    leases = [
        RouteLease(
            source_agent_id=source.id,
            target_agent_id=target.id,
            route_type="direct",
            expires_at=expires_at,
            messages_sent=0,
            bytes_sent=0,
        )
        for _ in range(count)
    ]
    session.add_all(leases)
    await session.flush()
    return leases


def _revoked_count(leases: list[RouteLease]) -> int:
    """How many of the seeded leases are revoked.

    Counted on the ORM objects themselves: cleanup_expired_leases loads the
    same rows from the session identity map, so its updates are visible on
    the seeded objects without re-querying. This scopes every assertion to
    exactly the rows the test seeded — the shared test database also has a
    live concurrent writer committing leases, so table-wide counts are not
    stable.
    """
    return sum(1 for lease in leases if lease.revoked_at is not None)


async def _neutralize_leftover_rows(session) -> None:
    """Neutralize pre-existing committed rows so every count in this file
    reflects only the rows seeded by the current test.

    The shared test database carries committed leftovers (expired AND still
    active leases, plus stale edge relays) from earlier e2e/server runs that
    commit for real. Every pre-existing lease is marked revoked here (expiry
    state is irrelevant: seeded rows are created afterwards, so the pending
    set reflects only them). This runs inside the caller's (rolled-back)
    test transaction, so it never persists or leaks into other tests.
    """
    now = datetime.now(UTC)
    await session.execute(
        update(RouteLease)
        .where(RouteLease.revoked_at.is_(None))
        .values(revoked_at=now, revoke_reason="test-neutralized")
    )
    await session.execute(
        update(RelayNode)
        .where(
            RelayNode.node_type == "personal_edge",
            RelayNode.status.in_(["healthy", "degraded"]),
        )
        .values(last_heartbeat_at=now)
    )
    await session.flush()


def _make_relay(
    name: str,
    *,
    node_type: str = "personal_edge",
    status: str = "healthy",
    heartbeat_age_minutes: float | None = 1.0,
) -> RelayNode:
    return RelayNode(
        node_name=name,
        node_type=node_type,
        status=status,
        last_heartbeat_at=(
            datetime.now(UTC) - timedelta(minutes=heartbeat_age_minutes)
            if heartbeat_age_minutes is not None
            else None
        ),
    )


# ------------------------------------------------- P1: batch rate limiting


class TestCleanupExpiredLeasesBatching:
    """The P1 rewrite must cap writes per call and defer the remainder."""

    def test_rate_limit_constants(self):
        assert lease_service._EXPIRED_LEASE_BATCH_SIZE == 500
        assert lease_service._MAX_BATCHES_PER_CYCLE == 10
        # Per-cycle write-spike cap: 500 * 10 = 5000 row updates.
        assert (
            lease_service._EXPIRED_LEASE_BATCH_SIZE * lease_service._MAX_BATCHES_PER_CYCLE
        ) == 5000

    async def test_single_call_below_cap_clears_all_and_only_expired(
        self, session, two_agents
    ):
        source, target = two_agents
        await _neutralize_leftover_rows(session)
        expired = await _seed_leases(session, source, target, 1200, expired=True)
        active = await _seed_leases(session, source, target, 50, expired=False)

        returned = await lease_service.cleanup_expired_leases(session)

        # 1200 pending ≤ the 5000 per-cycle cap, so one call clears them all.
        assert returned == 1200
        assert returned <= 5000
        assert _revoked_count(expired) == 1200
        assert _revoked_count(active) == 0

    async def test_batch_size_cap_requires_multiple_calls(
        self, session, two_agents, monkeypatch
    ):
        """With the per-cycle batch cap binding, 1200 rows need 3 calls."""
        # Force the per-cycle cap to bind after one batch: one call may then
        # only mark _EXPIRED_LEASE_BATCH_SIZE rows, the rest wait for the
        # next cycle — exactly the "remaining rows picked up next cycle"
        # contract of the P1 rewrite.
        monkeypatch.setattr(lease_service, "_MAX_BATCHES_PER_CYCLE", 1)
        source, target = two_agents
        await _neutralize_leftover_rows(session)
        leases = await _seed_leases(session, source, target, 1200, expired=True)

        first = await lease_service.cleanup_expired_leases(session)
        assert first == 500  # one batch of _EXPIRED_LEASE_BATCH_SIZE
        assert _revoked_count(leases) == 500

        second = await lease_service.cleanup_expired_leases(session)
        assert second == 500
        assert _revoked_count(leases) == 1000

        third = await lease_service.cleanup_expired_leases(session)
        assert third == 200
        assert _revoked_count(leases) == 1200

        fourth = await lease_service.cleanup_expired_leases(session)
        assert fourth == 0
        assert _revoked_count(leases) == 1200

    async def test_production_constants_cap_single_call_at_5000(
        self, session, two_agents
    ):
        """Full-scale: with the real constants, 5200 rows overflow one call."""
        source, target = two_agents
        await _neutralize_leftover_rows(session)
        leases = await _seed_leases(session, source, target, 5200, expired=True)

        first = await lease_service.cleanup_expired_leases(session)
        assert first == 5000  # 10 batches × 500, the documented per-cycle cap
        assert _revoked_count(leases) == 5000

        second = await lease_service.cleanup_expired_leases(session)
        assert second == 200
        assert _revoked_count(leases) == 5200


# --------------------------- service-level: stale edge relay cleanup


class TestCleanupStaleEdgeRelays:
    """cleanup_stale_edge_relays had zero coverage before this suite."""

    async def test_marks_stale_personal_edge_down(self, session):
        await _neutralize_leftover_rows(session)
        relay = _make_relay("edge-stale-1", heartbeat_age_minutes=10)
        session.add(relay)
        await session.commit()

        count = await cleanup_stale_edge_relays(session)

        assert count == 1
        await session.refresh(relay)
        assert relay.status == "down"

    async def test_leaves_fresh_heartbeat_alone(self, session):
        await _neutralize_leftover_rows(session)
        relay = _make_relay("edge-fresh-1", heartbeat_age_minutes=1)
        session.add(relay)
        await session.commit()

        count = await cleanup_stale_edge_relays(session)

        assert count == 0
        await session.refresh(relay)
        assert relay.status == "healthy"

    async def test_ignores_non_edge_nodes_with_stale_heartbeat(self, session):
        await _neutralize_leftover_rows(session)
        relay = _make_relay(
            "central-stale", node_type="central", heartbeat_age_minutes=60
        )
        session.add(relay)
        await session.commit()

        count = await cleanup_stale_edge_relays(session)

        assert count == 0
        await session.refresh(relay)
        assert relay.status == "healthy"

    async def test_ignores_already_down_edges(self, session):
        await _neutralize_leftover_rows(session)
        relay = _make_relay("edge-down", status="down", heartbeat_age_minutes=60)
        session.add(relay)
        await session.commit()

        count = await cleanup_stale_edge_relays(session)

        assert count == 0

    async def test_custom_threshold(self, session):
        await _neutralize_leftover_rows(session)
        # 3 minutes old: stale only for a 2-minute threshold.
        relay = _make_relay("edge-thresh", heartbeat_age_minutes=3)
        session.add(relay)
        await session.commit()

        assert await cleanup_stale_edge_relays(session, stale_threshold_minutes=5) == 0
        await session.refresh(relay)
        assert relay.status == "healthy"

        assert await cleanup_stale_edge_relays(session, stale_threshold_minutes=2) == 1
        await session.refresh(relay)
        assert relay.status == "down"


# --------------------------------------------- M1: single-cycle functions


class TestCleanupCycleFunctions:
    """The M2 commit placement: cycles commit; services only flush."""

    async def test_lease_cleanup_cycle_commits_and_returns_count(
        self, session, two_agents
    ):
        source, target = two_agents
        await _neutralize_leftover_rows(session)
        leases = await _seed_leases(session, source, target, 5, expired=True)
        commits = []
        real_commit = session.commit  # fixture maps commit() → flush()

        async def _spy_commit():
            commits.append(1)
            await real_commit()

        session.commit = _spy_commit

        count = await cleanup_worker.lease_cleanup_cycle(session)

        assert count == 5
        # Exactly one commit per cycle (M2: the cycle owns the transaction).
        assert commits == [1]
        assert _revoked_count(leases) == 5

    async def test_stale_relay_cleanup_cycle_commits_and_returns_count(self, session):
        await _neutralize_leftover_rows(session)
        relay = _make_relay("edge-stale-cycle", heartbeat_age_minutes=10)
        session.add(relay)
        await session.commit()
        commits = []
        real_commit = session.commit

        async def _spy_commit():
            commits.append(1)
            await real_commit()

        session.commit = _spy_commit

        count = await cleanup_worker.stale_relay_cleanup_cycle(session)

        assert count == 1
        assert commits == [1]
        await session.refresh(relay)
        assert relay.status == "down"


# ------------------------------------------------- M1: loop wrappers


class _FakeSession:
    async def __aenter__(self):
        return "fake-session"

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeSessionFactory:
    def __call__(self):
        return _FakeSession()


class TestLoopWrappers:
    """Loops follow retry_worker.py: lock per cycle, graceful cancel."""

    async def test_lease_cleanup_loop_runs_one_cycle_and_exits_cleanly(self, monkeypatch):
        seen = []

        async def _cycle(session):
            seen.append(session)
            return 0

        monkeypatch.setattr(cleanup_worker, "lease_cleanup_cycle", _cycle)
        monkeypatch.setattr(cleanup_worker, "SessionLocal", _FakeSessionFactory())

        task = asyncio.create_task(cleanup_worker.lease_cleanup_loop(interval_s=0.01))
        try:
            await asyncio.sleep(0.1)
        finally:
            task.cancel()
        await task  # CancelledError must be swallowed, not re-raised

        assert len(seen) >= 1
        assert seen[0] == "fake-session"

    async def test_stale_relay_loop_survives_cycle_exception(self, monkeypatch):
        calls = []

        async def _flaky_cycle(session):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("simulated cycle failure")
            return 0

        monkeypatch.setattr(cleanup_worker, "stale_relay_cleanup_cycle", _flaky_cycle)
        monkeypatch.setattr(cleanup_worker, "SessionLocal", _FakeSessionFactory())

        task = asyncio.create_task(cleanup_worker.stale_relay_cleanup_loop(interval_s=0.01))
        try:
            await asyncio.sleep(0.1)
        finally:
            task.cancel()
        await task

        # First cycle raised, second still ran: exception isolation works.
        assert len(calls) >= 2


# --------------------------------------------- lifespan registration (M3)


class TestLifespanRegistration:
    """Seven periodic workers must be registered and cancelled on shutdown.

    Verified by reading main.py's lifespan source plus importing app.main —
    the suite has no existing pattern for driving a real lifespan context
    (only helpers/ws_e2e.py passes lifespan="on" to a server).
    """

    def test_app_main_imports(self):
        import app.main  # noqa: F401

    def test_lifespan_starts_and_cancels_seven_workers(self):
        import app.main

        source = inspect.getsource(app.main.lifespan)

        # Both new workers are started inside lifespan.
        assert "lease_cleanup_loop(" in source
        assert "stale_relay_cleanup_loop(" in source

        # The shutdown cancel tuple must contain all seven worker tasks.
        match = re.search(r"for task in \(([^)]*)\)", source)
        assert match is not None, "cancel tuple not found in lifespan source"
        cancelled = [name.strip() for name in match.group(1).split(",") if name.strip()]
        assert cancelled == [
            "retry_task",
            "timeout_task",
            "sla_monitoring_task",
            "continuity_task",
            "offline_delivery_task",
            "lease_cleanup_task",
            "stale_relay_cleanup_task",
        ]

    def test_legacy_cleanup_task_module_removed(self):
        with pytest.raises(ModuleNotFoundError):
            import app.tasks.cleanup_leases  # noqa: F401
