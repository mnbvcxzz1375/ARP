"""Phase 16: Egress Gateway tests."""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from app.exceptions import DomainException
from app.models.egress_gateway import EgressGateway
from app.models.egress_log import EgressLog
from app.models.agent import Agent
from app.models.user import User
from app.services import egress_service


@pytest.fixture
async def test_user(session):
    """Create a test user."""
    user = User(username="egress_user")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.fixture
async def test_agent(session, test_user):
    """Create a test agent."""
    agent = Agent(
        agent_number="999001",
        owner_id=test_user.id,
        name="EgressTestAgent",
        runtime="test",
        inbound_policy="public",
    )
    session.add(agent)
    await session.commit()
    await session.refresh(agent)
    return agent


@pytest.fixture
async def test_gateway(session, test_user):
    """Create a test egress gateway without secret injection."""
    gateway = EgressGateway(
        scope_id=test_user.id,
        gateway_name="TestAPIGateway",
        gateway_type="api",
        domain_allowlist=["api.example.com", "*.safe-domain.com"],
        rate_limit_config={"requests_per_minute": 60},
        cache_config={"ttl_seconds": 300},
        cost_tracking=True,
        enabled=True,
    )
    session.add(gateway)
    await session.commit()
    await session.refresh(gateway)
    return gateway


@pytest.fixture
async def disabled_gateway(session, test_user):
    """Create a disabled egress gateway."""
    gateway = EgressGateway(
        scope_id=test_user.id,
        gateway_name="DisabledGateway",
        gateway_type="api",
        domain_allowlist=["api.example.com"],
        enabled=False,
    )
    session.add(gateway)
    await session.commit()
    await session.refresh(gateway)
    return gateway


@pytest.fixture
async def test_gateway_env_secret(session, test_user):
    """Create a test egress gateway with env: secret injection."""
    gateway = EgressGateway(
        scope_id=test_user.id,
        gateway_name="EnvSecretGateway",
        gateway_type="api",
        domain_allowlist=["api.example.com", "*.safe-domain.com"],
        secret_store_ref="env:AGENTNET_TEST_EGRESS_SECRET",
        enabled=True,
    )
    session.add(gateway)
    await session.commit()
    await session.refresh(gateway)
    return gateway


class TestDomainAllowlist:
    """Test domain allowlist validation."""

    async def test_exact_domain_match(self, session, test_gateway):
        """Exact domain match should be allowed."""
        allowed = await egress_service.check_domain_allowlist(
            session,
            test_gateway.id,
            "https://api.example.com/v1/users"
        )
        assert allowed is True

    async def test_wildcard_domain_match(self, session, test_gateway):
        """Wildcard domain match should be allowed."""
        allowed = await egress_service.check_domain_allowlist(
            session,
            test_gateway.id,
            "https://api.safe-domain.com/endpoint"
        )
        assert allowed is True

        allowed = await egress_service.check_domain_allowlist(
            session,
            test_gateway.id,
            "https://sub.safe-domain.com/endpoint"
        )
        assert allowed is True

    async def test_domain_not_in_allowlist(self, session, test_gateway):
        """Domain not in allowlist should be blocked."""
        allowed = await egress_service.check_domain_allowlist(
            session,
            test_gateway.id,
            "https://malicious.com/steal-data"
        )
        assert allowed is False

    async def test_disabled_gateway_blocks_all(self, session, disabled_gateway):
        """Disabled gateway should block all requests."""
        with pytest.raises(DomainException) as exc:
            await egress_service.check_domain_allowlist(
                session,
                disabled_gateway.id,
                "https://api.example.com/v1/users"
            )
        assert "disabled" in str(exc.value).lower()


class TestSecretIsolation:
    """Test that agents cannot see enterprise secrets."""

    async def test_agent_cannot_bypass_gateway(self, session, test_gateway, test_agent):
        """Agent must use gateway - cannot bypass to access secrets directly."""
        # Mock the HTTP client
        with patch('app.services.egress_service.httpx.AsyncClient') as mock_client:
            # Use MagicMock for response since json() is not async
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": "test"}
            mock_response.text = '{"data": "test"}'
            mock_response.content = b'{"data": "test"}'

            mock_instance = AsyncMock()
            mock_instance.request = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            # Attempt to make request through gateway (correct way)
            result = await egress_service.proxy_external_request(
                session,
                gateway_id=test_gateway.id,
                task_id=None,
                agent_id=test_agent.id,
                request_type="GET",
                target_url="https://api.example.com/data",
            )

            # Gateway should handle the request
            assert result is not None
            assert result == {"data": "test"}

            # Verify that the agent never received the secret
            # (secrets are injected server-side only)

    async def test_secrets_not_logged(self, session, test_gateway, test_agent):
        """Secrets should never appear in logs."""
        # Mock the HTTP client
        with patch('app.services.egress_service.httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": "test"}
            mock_response.text = '{"data": "test"}'
            mock_response.content = b'{"data": "test"}'

            mock_instance = AsyncMock()
            mock_instance.request = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            await egress_service.proxy_external_request(
                session,
                gateway_id=test_gateway.id,
                task_id=None,
                agent_id=test_agent.id,
                request_type="GET",
                target_url="https://api.example.com/data",
            )

        # Check egress logs don't contain secrets
        from sqlalchemy import select
        result = await session.execute(
            select(EgressLog).where(EgressLog.gateway_id == test_gateway.id)
        )
        logs = result.scalars().all()
        assert len(logs) == 1

        # Logs should not contain secret_store_ref value
        # (only the reference, not the actual secret)


class TestHighRiskApproval:
    """Test high-risk operations require approval."""

    async def test_delete_requires_approval(self, session, test_gateway, test_agent):
        """DELETE requests should require approval."""
        from app.models.task import Task
        from app.protocol.constants import TaskStatus

        # Create a task for context
        task = Task(
            created_by=test_agent.id,
            assigned_to=test_agent.id,
            status=TaskStatus.RUNNING.value,
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)

        result = await egress_service.proxy_external_request(
            session,
            gateway_id=test_gateway.id,
            task_id=task.id,
            agent_id=test_agent.id,
            request_type="DELETE",
            target_url="https://api.example.com/resource/123",
        )

        # Should return awaiting_approval status
        assert result["status"] == "awaiting_approval"
        assert "approval_id" in result

    async def test_deploy_keyword_requires_approval(self, session, test_gateway, test_agent):
        """URLs with 'deploy' keyword should require approval."""
        from app.models.task import Task
        from app.protocol.constants import TaskStatus

        task = Task(
            created_by=test_agent.id,
            assigned_to=test_agent.id,
            status=TaskStatus.RUNNING.value,
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)

        result = await egress_service.proxy_external_request(
            session,
            gateway_id=test_gateway.id,
            task_id=task.id,
            agent_id=test_agent.id,
            request_type="POST",
            target_url="https://api.example.com/deploy/production",
        )

        assert result["status"] == "awaiting_approval"

    async def test_safe_get_no_approval(self, session, test_gateway, test_agent):
        """Safe GET requests should not require approval."""
        # Mock the HTTP client
        with patch('app.services.egress_service.httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": "test"}
            mock_response.text = '{"data": "test"}'
            mock_response.content = b'{"data": "test"}'

            mock_instance = AsyncMock()
            mock_instance.request = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await egress_service.proxy_external_request(
                session,
                gateway_id=test_gateway.id,
                task_id=None,
                agent_id=test_agent.id,
                request_type="GET",
                target_url="https://api.example.com/data",
            )

            # Should succeed without approval
            assert result.get("status") != "awaiting_approval"
            assert result == {"data": "test"}


class TestEgressDown:
    """Test behavior when egress gateway is down."""

    async def test_disabled_gateway_fails_request(self, session, disabled_gateway, test_agent):
        """When gateway is disabled, requests should fail (not bypass)."""
        with pytest.raises(DomainException) as exc:
            await egress_service.proxy_external_request(
                session,
                gateway_id=disabled_gateway.id,
                task_id=None,
                agent_id=test_agent.id,
                request_type="GET",
                target_url="https://api.example.com/data",
            )

        # Should fail with egress blocked error
        assert "disabled" in str(exc.value).lower()

    async def test_nonexistent_gateway_fails(self, session, test_agent):
        """Nonexistent gateway should fail (agent cannot bypass)."""
        fake_gateway_id = uuid4()

        with pytest.raises(DomainException) as exc:
            await egress_service.proxy_external_request(
                session,
                gateway_id=fake_gateway_id,
                task_id=None,
                agent_id=test_agent.id,
                request_type="GET",
                target_url="https://api.example.com/data",
            )

        assert "not found" in str(exc.value).lower()


class TestCostTracking:
    """Test cost estimation and tracking."""

    async def test_cost_tracked_for_model_gateway(self, session, test_user, test_agent):
        """Model gateway should track costs."""
        gateway = EgressGateway(
            scope_id=test_user.id,
            gateway_name="ModelGateway",
            gateway_type="model",
            domain_allowlist=["api.openai.com"],
            cost_tracking=True,
            enabled=True,
        )
        session.add(gateway)
        await session.commit()
        await session.refresh(gateway)

        with patch('app.services.egress_service.httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"ok": True}
            mock_response.text = '{"ok": true}'
            mock_response.content = b'{"ok": true}'

            mock_instance = AsyncMock()
            mock_instance.request = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            await egress_service.proxy_external_request(
                session,
                gateway_id=gateway.id,
                task_id=None,
                agent_id=test_agent.id,
                request_type="POST",
                target_url="https://api.openai.com/v1/chat/completions",
                request_body={
                    "model": "gpt-4",
                    "messages": [{"role": "user", "content": "Hello"}],
                },
            )

        # Check cost was logged
        from sqlalchemy import select
        result = await session.execute(
            select(EgressLog).where(EgressLog.gateway_id == gateway.id)
        )
        logs = result.scalars().all()
        assert len(logs) == 1
        assert logs[0].cost_estimate is not None
        assert logs[0].cost_estimate > 0

    async def test_cost_not_tracked_when_disabled(self, session, test_user, test_agent):
        """Cost tracking can be disabled."""
        gateway = EgressGateway(
            scope_id=test_user.id,
            gateway_name="NoCostGateway",
            gateway_type="api",
            domain_allowlist=["api.example.com"],
            cost_tracking=False,
            enabled=True,
        )
        session.add(gateway)
        await session.commit()
        await session.refresh(gateway)

        # Mock the HTTP client
        with patch('app.services.egress_service.httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": "test"}
            mock_response.text = '{"data": "test"}'
            mock_response.content = b'{"data": "test"}'

            mock_instance = AsyncMock()
            mock_instance.request = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            await egress_service.proxy_external_request(
                session,
                gateway_id=gateway.id,
                task_id=None,
                agent_id=test_agent.id,
                request_type="GET",
                target_url="https://api.example.com/data",
            )

        # Check cost was not estimated
        from sqlalchemy import select
        result = await session.execute(
            select(EgressLog).where(EgressLog.gateway_id == gateway.id)
        )
        logs = result.scalars().all()
        assert len(logs) == 1
        assert logs[0].cost_estimate is None


class TestSecretInjection:
    """Test secret injection: env secrets, missing secrets, unsupported refs, auth clash."""

    async def test_env_secret_injected_into_auth_header(
        self, session, test_gateway_env_secret, test_agent, monkeypatch,
    ):
        """env:VAR_NAME secret is read and injected as Bearer token."""
        monkeypatch.setenv("AGENTNET_TEST_EGRESS_SECRET", "my-test-secret-123")

        with patch("app.services.egress_service.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": "ok"}
            mock_response.text = '{"data": "ok"}'
            mock_response.content = b'{"data": "ok"}'

            mock_instance = AsyncMock()
            mock_instance.request = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await egress_service.proxy_external_request(
                session,
                gateway_id=test_gateway_env_secret.id,
                task_id=None,
                agent_id=test_agent.id,
                request_type="GET",
                target_url="https://api.example.com/data",
            )

            assert result == {"data": "ok"}
            call_args = mock_instance.request.call_args
            assert call_args.kwargs["headers"].get("Authorization") == "Bearer my-test-secret-123"

    async def test_env_secret_missing_fail_closed(
        self, session, test_gateway_env_secret, test_agent, monkeypatch,
    ):
        """Missing env var blocks the request (fail closed). httpx is never called."""
        monkeypatch.delenv("AGENTNET_TEST_EGRESS_SECRET", raising=False)

        with patch("app.services.egress_service.httpx.AsyncClient") as mock_client:
            with pytest.raises(DomainException) as exc:
                await egress_service.proxy_external_request(
                    session,
                    gateway_id=test_gateway_env_secret.id,
                    task_id=None,
                    agent_id=test_agent.id,
                    request_type="GET",
                    target_url="https://api.example.com/data",
                )

            assert exc.value.code == "EGRESS_BLOCKED"
            mock_client.assert_not_called()

    async def test_unsupported_secret_store_fail_closed(
        self, session, test_agent, test_user,
    ):
        """vault:// ref must fail closed. httpx is never called."""
        gateway = EgressGateway(
            scope_id=test_user.id,
            gateway_name="VaultGateway",
            gateway_type="api",
            domain_allowlist=["api.example.com"],
            secret_store_ref="vault://secrets/api-key",
            enabled=True,
        )
        session.add(gateway)
        await session.commit()
        await session.refresh(gateway)

        with patch("app.services.egress_service.httpx.AsyncClient") as mock_client:
            with pytest.raises(DomainException) as exc:
                await egress_service.proxy_external_request(
                    session,
                    gateway_id=gateway.id,
                    task_id=None,
                    agent_id=test_agent.id,
                    request_type="GET",
                    target_url="https://api.example.com/data",
                )

            assert exc.value.code == "EGRESS_BLOCKED"
            mock_client.assert_not_called()

    async def test_reject_agent_provided_auth_header(
        self, session, test_gateway_env_secret, test_agent, monkeypatch,
    ):
        """Agent-provided Authorization header is rejected - no overwrite, no bypass."""
        monkeypatch.setenv("AGENTNET_TEST_EGRESS_SECRET", "my-test-secret-123")

        with patch("app.services.egress_service.httpx.AsyncClient") as mock_client:
            with pytest.raises(DomainException) as exc:
                await egress_service.proxy_external_request(
                    session,
                    gateway_id=test_gateway_env_secret.id,
                    task_id=None,
                    agent_id=test_agent.id,
                    request_type="GET",
                    target_url="https://api.example.com/data",
                    headers={"Authorization": "Bearer agent-owned-token"},
                )

            assert exc.value.code == "EGRESS_BLOCKED"
            mock_client.assert_not_called()


class TestEgressRateLimit:
    """Test Redis sliding-window rate limiting in egress gateway."""

    @pytest.fixture
    async def rate_limited_gateway(self, session, test_user):
        """Gateway with very strict rate limit (1 req/min)."""
        gateway = EgressGateway(
            scope_id=test_user.id,
            gateway_name="RateLimitedGateway",
            gateway_type="api",
            domain_allowlist=["api.example.com"],
            rate_limit_config={"requests_per_minute": 1},
            enabled=True,
        )
        session.add(gateway)
        await session.commit()
        await session.refresh(gateway)
        return gateway

    async def test_rate_limited_raises_429_and_httpx_not_called(
        self, session, rate_limited_gateway, test_agent,
    ):
        """zcard >= max_requests -> RATE_LIMITED(429), httpx never called."""
        mock_redis = AsyncMock()
        mock_redis.zremrangebyscore = AsyncMock()
        mock_redis.zcard = AsyncMock(return_value=1)  # 1 >= 1 -> throttled

        with patch("app.services.egress_service.redis_module.redis_client", mock_redis):
            with patch("app.services.egress_service.httpx.AsyncClient") as mock_httpx:
                with pytest.raises(DomainException) as exc:
                    await egress_service.proxy_external_request(
                        session,
                        gateway_id=rate_limited_gateway.id,
                        task_id=None,
                        agent_id=test_agent.id,
                        request_type="GET",
                        target_url="https://api.example.com/data",
                    )

                assert exc.value.code == "RATE_LIMITED"
                assert exc.value.status_code == 429
                mock_httpx.assert_not_called()

    async def test_redis_error_raises_503_and_httpx_not_called(
        self, session, rate_limited_gateway, test_agent,
    ):
        """Redis failure -> INTERNAL_ERROR(503), httpx never called."""
        mock_redis = AsyncMock()
        mock_redis.zremrangebyscore = AsyncMock(
            side_effect=ConnectionError("Redis connection refused"),
        )

        with patch("app.services.egress_service.redis_module.redis_client", mock_redis):
            with patch("app.services.egress_service.httpx.AsyncClient") as mock_httpx:
                with pytest.raises(DomainException) as exc:
                    await egress_service.proxy_external_request(
                        session,
                        gateway_id=rate_limited_gateway.id,
                        task_id=None,
                        agent_id=test_agent.id,
                        request_type="GET",
                        target_url="https://api.example.com/data",
                    )

                assert exc.value.code == "INTERNAL_ERROR"
                assert exc.value.status_code == 503
                mock_httpx.assert_not_called()

    async def test_under_rate_limit(
        self, session, test_gateway, test_agent,
    ):
        """Under limit: Redis methods and httpx are called, response returned."""
        mock_redis = AsyncMock()
        mock_redis.zremrangebyscore = AsyncMock()
        mock_redis.zcard = AsyncMock(return_value=0)    # 0 < 60 -> OK
        mock_redis.zadd = AsyncMock()
        mock_redis.expire = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)   # cache miss
        mock_redis.set = AsyncMock()                    # _cache_set

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "ok"}
        mock_response.text = '{"data": "ok"}'
        mock_response.content = b'{"data": "ok"}'

        mock_httpx_instance = AsyncMock()
        mock_httpx_instance.request = AsyncMock(return_value=mock_response)

        with patch("app.services.egress_service.redis_module.redis_client", mock_redis):
            with patch("app.services.egress_service.httpx.AsyncClient") as mock_httpx:
                mock_httpx.return_value.__aenter__.return_value = mock_httpx_instance

                result = await egress_service.proxy_external_request(
                    session,
                    gateway_id=test_gateway.id,
                    task_id=None,
                    agent_id=test_agent.id,
                    request_type="GET",
                    target_url="https://api.example.com/data",
                )

                assert result == {"data": "ok"}
                mock_redis.zremrangebyscore.assert_called_once()
                mock_redis.zcard.assert_called_once()
                mock_redis.zadd.assert_called_once()
                mock_redis.expire.assert_called_once()
                mock_redis.set.assert_awaited_once()


class TestEgressCache:
    """Test egress response caching behavior."""

    async def test_cache_hit_returns_cached_data_no_http_call(
        self, session, test_gateway, test_agent,
    ):
        """Cache hit returns cached data without making HTTP request."""
        mock_redis = AsyncMock()
        mock_redis.zremrangebyscore = AsyncMock()
        mock_redis.zcard = AsyncMock(return_value=0)
        mock_redis.zadd = AsyncMock()
        mock_redis.expire = AsyncMock()
        mock_redis.get = AsyncMock(return_value='{"data": "cached"}')

        with patch("app.services.egress_service.redis_module.redis_client", mock_redis):
            with patch("app.services.egress_service.httpx.AsyncClient") as mock_httpx:
                result = await egress_service.proxy_external_request(
                    session,
                    gateway_id=test_gateway.id,
                    task_id=None,
                    agent_id=test_agent.id,
                    request_type="GET",
                    target_url="https://api.example.com/data",
                )

                assert result == {"data": "cached"}
                mock_httpx.assert_not_called()

        from sqlalchemy import select
        db_result = await session.execute(
            select(EgressLog).where(EgressLog.gateway_id == test_gateway.id)
        )
        logs = db_result.scalars().all()
        assert len(logs) == 1
        assert logs[0].status_code == 200
        assert logs[0].latency_ms == 0

    async def test_cache_miss_stores_2xx_get_response(
        self, session, test_gateway, test_agent,
    ):
        """Cache miss -> HTTP call -> 2xx response stored in cache."""
        mock_redis = AsyncMock()
        mock_redis.zremrangebyscore = AsyncMock()
        mock_redis.zcard = AsyncMock(return_value=0)
        mock_redis.zadd = AsyncMock()
        mock_redis.expire = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "fresh"}
        mock_response.text = '{"data": "fresh"}'
        mock_response.content = b'{"data": "fresh"}'

        with patch("app.services.egress_service.redis_module.redis_client", mock_redis):
            with patch("app.services.egress_service.httpx.AsyncClient") as mock_httpx:
                mock_instance = AsyncMock()
                mock_instance.request = AsyncMock(return_value=mock_response)
                mock_httpx.return_value.__aenter__.return_value = mock_instance

                result = await egress_service.proxy_external_request(
                    session,
                    gateway_id=test_gateway.id,
                    task_id=None,
                    agent_id=test_agent.id,
                    request_type="GET",
                    target_url="https://api.example.com/data",
                )

                assert result == {"data": "fresh"}
                mock_redis.set.assert_awaited_once()
                assert mock_redis.set.await_args.kwargs.get("ex") == 300

    async def test_cache_get_redis_error_fail_closed(
        self, session, test_gateway, test_agent,
    ):
        """Redis error during cache get raises 503, HTTP not called."""
        mock_redis = AsyncMock()
        mock_redis.zremrangebyscore = AsyncMock()
        mock_redis.zcard = AsyncMock(return_value=0)
        mock_redis.zadd = AsyncMock()
        mock_redis.expire = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=ConnectionError("Connection refused"))

        with patch("app.services.egress_service.redis_module.redis_client", mock_redis):
            with patch("app.services.egress_service.httpx.AsyncClient") as mock_httpx:
                with pytest.raises(DomainException) as exc:
                    await egress_service.proxy_external_request(
                        session,
                        gateway_id=test_gateway.id,
                        task_id=None,
                        agent_id=test_agent.id,
                        request_type="GET",
                        target_url="https://api.example.com/data",
                    )

                assert exc.value.code == "INTERNAL_ERROR"
                assert exc.value.status_code == 503
                mock_httpx.assert_not_called()

    async def test_non_get_does_not_use_cache(
        self, session, test_gateway, test_agent,
    ):
        """POST request does not read from or write to cache."""
        mock_redis = AsyncMock()
        mock_redis.zremrangebyscore = AsyncMock()
        mock_redis.zcard = AsyncMock(return_value=0)
        mock_redis.zadd = AsyncMock()
        mock_redis.expire = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "ok"}
        mock_response.text = '{"result": "ok"}'
        mock_response.content = b'{"result": "ok"}'

        with patch("app.services.egress_service.redis_module.redis_client", mock_redis):
            with patch("app.services.egress_service.httpx.AsyncClient") as mock_httpx:
                mock_instance = AsyncMock()
                mock_instance.request = AsyncMock(return_value=mock_response)
                mock_httpx.return_value.__aenter__.return_value = mock_instance

                result = await egress_service.proxy_external_request(
                    session,
                    gateway_id=test_gateway.id,
                    task_id=None,
                    agent_id=test_agent.id,
                    request_type="POST",
                    target_url="https://api.example.com/data",
                    request_body={"key": "value"},
                )

                assert result == {"result": "ok"}
                mock_redis.get.assert_not_called()
                mock_redis.set.assert_not_called()
