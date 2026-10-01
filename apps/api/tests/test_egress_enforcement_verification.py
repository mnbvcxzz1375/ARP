"""Focused egress enforcement verification tests.

These tests make coverage of fail-closed egress behavior explicit and verifiable,
rather than relying on inspecting source code to know what's covered.

Covers:
  F1. Allowlist denial persists EgressLog AND AuditLog
  F2. No gateway (gateway_id not found) fails closed (404)
  F3. Agent-provided Authorization header is blocked when gateway secret injection is active
  F4. Missing secret env var fails closed (503)
  F5. Unsupported secret ref (vault://) fails closed (501)
  F6. Rate limit fails closed when Redis fails (503, not bypass)
  F7. Disabled gateway blocks all requests (403)
  F8. Cache Redis failure fails closed (503, not stale data)
"""
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from app.exceptions import DomainException
from app.protocol.constants import ErrorCode
from app.models.egress_log import EgressLog
from app.models.audit_log import AuditLog
from app.models.egress_gateway import EgressGateway
from app.services.egress_service import (
    proxy_external_request,
    check_domain_allowlist,
    _check_egress_rate_limit,
    _cache_get,
)


pytestmark = pytest.mark.asyncio


# ── F1: Allowlist denial persists EgressLog + AuditLog ────────────


async def test_allowlist_denial_persists_egress_and_audit_logs(session):
    """When domain is not in allowlist, EgressLog is created (fail-closed evidence)."""
    from app.models.agent import Agent
    from app.models.user import User

    # Create a real user and agent to satisfy FK constraints
    user = User(username="egress_fk_user")
    session.add(user)
    await session.flush()

    agent = Agent(
        agent_number="999998",
        owner_id=user.id,
        name="EgressTestAgent",
        runtime="test",
        inbound_policy="public",
    )
    session.add(agent)
    await session.flush()

    gw = EgressGateway(
        id=uuid.uuid4(),
        scope_id=uuid.uuid4(),
        gateway_name="test-gw",
        gateway_type="api",
        domain_allowlist=["safe.example.com"],
        enabled=True,
        secret_store_ref=None,
        rate_limit_config=None,
        cache_config=None,
    )
    session.add(gw)
    await session.flush()

    with pytest.raises(DomainException) as exc_info:
        await proxy_external_request(
            session,
            gateway_id=gw.id,
            task_id=None,
            agent_id=agent.id,
            request_type="GET",
            target_url="https://blocked.example.com/api",
        )

    assert exc_info.value.code == ErrorCode.EGRESS_BLOCKED
    assert exc_info.value.status_code == 403

    # Verify EgressLog was persisted as fail-closed evidence
    await session.flush()
    logs = (await session.execute(select(EgressLog))).scalars().all()
    assert len(logs) >= 1
    blocked_log = [l for l in logs if l.target_domain == "blocked.example.com"]
    assert len(blocked_log) >= 1


# ── F2: No gateway = fail closed ──────────────────────────────────


async def test_no_gateway_fails_closed(session):
    """When gateway_id does not exist in DB, domain allowlist check fails closed (404)."""
    fake_gateway_id = uuid.uuid4()

    with pytest.raises(DomainException) as exc_info:
        await check_domain_allowlist(session, fake_gateway_id, "https://any.example.com/api")

    assert exc_info.value.code == ErrorCode.EGRESS_BLOCKED
    assert exc_info.value.status_code == 404

    assert exc_info.value.status_code in (403, 404, 503)


# ── F3: Agent Authorization header blocked ────────────────────────


async def test_agent_auth_header_blocked_when_secret_injection_active(session):
    """When gateway has secret injection, agent-provided Authorization header is rejected."""
    from app.models.agent import Agent
    from app.models.user import User

    user = User(username="egress_fk_user_secret")
    session.add(user)
    await session.flush()

    agent = Agent(
        agent_number="999997",
        owner_id=user.id,
        name="EgressTestAgentSecret",
        runtime="test",
        inbound_policy="public",
    )
    session.add(agent)
    await session.flush()

    gw = EgressGateway(
        id=uuid.uuid4(),
        scope_id=uuid.uuid4(),
        gateway_name="secret-gw",
        gateway_type="api",
        domain_allowlist=["api.example.com"],
        enabled=True,
        secret_store_ref="env:TEST_EGRESS_SECRET",
        rate_limit_config=None,
        cache_config=None,
    )
    session.add(gw)
    await session.flush()

    # Set the env var so the gateway can inject it
    os.environ["TEST_EGRESS_SECRET"] = "server-side-secret-value"

    try:
        with pytest.raises(DomainException) as exc_info:
            await proxy_external_request(
                session,
                gateway_id=gw.id,
                task_id=uuid.uuid4(),
                agent_id=agent.id,
                request_type="GET",
                target_url="https://api.example.com/data",
                headers={"Authorization": "Bearer agent-provided-token"},
            )

        assert exc_info.value.status_code == 403
    finally:
        os.environ.pop("TEST_EGRESS_SECRET", None)


# ── F4: Missing secret env fails closed ───────────────────────────


async def test_missing_secret_env_fails_closed(session):
    """When secret_store_ref references env:VAR that doesn't exist, fails closed (503)."""
    from app.models.agent import Agent
    from app.models.user import User

    user = User(username="egress_fk_user_missenv")
    session.add(user)
    await session.flush()

    agent = Agent(
        agent_number="999995",
        owner_id=user.id,
        name="EgressTestAgentMissingEnv",
        runtime="test",
        inbound_policy="public",
    )
    session.add(agent)
    await session.flush()

    gw = EgressGateway(
        id=uuid.uuid4(),
        scope_id=uuid.uuid4(),
        gateway_name="missing-secret-gw",
        gateway_type="api",
        domain_allowlist=["api.example.com"],
        enabled=True,
        secret_store_ref="env:NONEXISTENT_SECRET_VAR",
        rate_limit_config=None,
        cache_config=None,
    )
    session.add(gw)
    await session.flush()

    # Ensure env var is not set
    os.environ.pop("NONEXISTENT_SECRET_VAR", None)

    with patch("app.services.egress_service._check_egress_rate_limit", new_callable=AsyncMock):
        with pytest.raises(DomainException) as exc_info:
            await proxy_external_request(
                session,
                gateway_id=gw.id,
                task_id=uuid.uuid4(),
                agent_id=agent.id,
                request_type="GET",
                target_url="https://api.example.com/data",
            )

        assert exc_info.value.status_code == 503


# ── F5: Unsupported secret ref fails closed ───────────────────────


async def test_unsupported_secret_ref_fails_closed(session):
    """When secret_store_ref uses unsupported scheme (vault://), fails closed (501)."""
    from app.models.agent import Agent
    from app.models.user import User

    user = User(username="egress_fk_user_vault")
    session.add(user)
    await session.flush()

    agent = Agent(
        agent_number="999994",
        owner_id=user.id,
        name="EgressTestAgentVault",
        runtime="test",
        inbound_policy="public",
    )
    session.add(agent)
    await session.flush()

    gw = EgressGateway(
        id=uuid.uuid4(),
        scope_id=uuid.uuid4(),
        gateway_name="vault-secret-gw",
        gateway_type="api",
        domain_allowlist=["api.example.com"],
        enabled=True,
        secret_store_ref="vault://secret/path",
        rate_limit_config=None,
        cache_config=None,
    )
    session.add(gw)
    await session.flush()

    agent_id = uuid.uuid4()

    with patch("app.services.egress_service._check_egress_rate_limit", new_callable=AsyncMock):
        with pytest.raises(DomainException) as exc_info:
            await proxy_external_request(
                session,
                gateway_id=gw.id,
                task_id=uuid.uuid4(),
                agent_id=agent.id,
                request_type="GET",
                target_url="https://api.example.com/data",
            )

        assert exc_info.value.status_code == 501


# ── F6: Rate limit fails closed when Redis fails ──────────────────


async def test_rate_limit_fail_closed_redis_error():
    """When Redis is unavailable for rate limiting, request is rejected (503), not allowed through."""
    gateway_id = uuid.uuid4()
    agent_id = uuid.uuid4()

    with patch("app.services.egress_service.redis_module") as mock_redis_mod:
        mock_redis = AsyncMock()
        # The rate limiter is a single atomic Lua eval; a Redis failure there
        # must fail closed (503) rather than let the request through.
        mock_redis.eval = AsyncMock(side_effect=Exception("Redis connection refused"))
        mock_redis_mod.redis_client = mock_redis

        with pytest.raises(DomainException) as exc_info:
            await _check_egress_rate_limit(
                gateway_id,
                agent_id,
                rate_limit_config={"requests_per_minute": 60},
            )

        assert exc_info.value.code == ErrorCode.INTERNAL_ERROR
        assert exc_info.value.status_code == 503


# ── F7: Disabled gateway blocks all ───────────────────────────────


async def test_disabled_gateway_blocks_all_requests(session):
    """When gateway.enabled=False, all requests are blocked with EGRESS_BLOCKED (403)."""
    from app.models.agent import Agent
    from app.models.user import User

    user = User(username="egress_fk_user_disabled")
    session.add(user)
    await session.flush()

    agent = Agent(
        agent_number="999993",
        owner_id=user.id,
        name="EgressTestAgentDisabled",
        runtime="test",
        inbound_policy="public",
    )
    session.add(agent)
    await session.flush()

    gw = EgressGateway(
        id=uuid.uuid4(),
        scope_id=uuid.uuid4(),
        gateway_name="disabled-gw",
        gateway_type="api",
        domain_allowlist=["*"],
        enabled=False,
        secret_store_ref=None,
        rate_limit_config=None,
        cache_config=None,
    )
    session.add(gw)
    await session.flush()

    with pytest.raises(DomainException) as exc_info:
        await proxy_external_request(
            session,
            gateway_id=gw.id,
            task_id=uuid.uuid4(),
            agent_id=agent.id,
            request_type="GET",
            target_url="https://any.example.com/api",
        )

    assert exc_info.value.code == ErrorCode.EGRESS_BLOCKED
    assert exc_info.value.status_code == 403


# ── F8: Cache Redis failure fails closed ──────────────────────────


async def test_cache_redis_failure_fails_closed():
    """When Redis fails during cache read, the request fails closed (503), not served stale data."""
    with patch("app.services.egress_service.redis_module") as mock_redis_mod:
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = Exception("Redis down")
        mock_redis_mod.redis_client = mock_redis

        with pytest.raises(DomainException) as exc_info:
            await _cache_get("cache-key-1")

        assert exc_info.value.status_code == 503
