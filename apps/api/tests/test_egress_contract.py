"""Egress contract tests: prove adapters cannot bypass egress policy.

These tests verify the AdapterContext.external_request() contract:
- External requests go through the egress gateway callback.
- Missing gateway raises RuntimeError (fail closed).
- Denied/rate-limited/approval-required exceptions propagate from proxy.
- Request body and headers are forwarded correctly.
- Metadata task_uuid/agent_uuid are validated before proxy call.
- _log_egress no longer commits; caller must commit.
- Adapter service fails closed when no config.
- _get_adapter converts dict config to AdapterConfig; invalid config returns DomainException.
- _registry_key supports both dict and Pydantic BaseModel.
- start_adapter/stop_adapter require explicit adapter_config.
- create_approval commits after write_audit so approval + audit are atomic.
"""

import httpx
import inspect

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from agentnet_adapter.interface import AdapterContext


class TestEgressContract:
    """Contract tests for egress enforcement at the adapter layer."""

    def _make_context(
        self,
        egress_gateway_id: str | None = "gw-001",
        make_external_request=None,
        metadata=None,
    ) -> AdapterContext:
        default_metadata = {
            "task_uuid": "00000000-0000-0000-0000-000000000001",
            "agent_uuid": "00000000-0000-0000-0000-000000000002",
        }
        return AdapterContext(
            task_id="task-1",
            agent_number="AN-001",
            metadata=metadata or default_metadata,
            egress_gateway_id=egress_gateway_id,
            make_external_request=make_external_request,
        )

    @pytest.mark.asyncio
    async def test_external_request_routes_through_gateway(self):
        """External requests must be forwarded to the egress proxy callback."""
        proxy_fn = AsyncMock(return_value={"status": "ok", "data": "response"})
        ctx = self._make_context(make_external_request=proxy_fn)

        result = await ctx.external_request(
            request_type="GET",
            target_url="https://api.example.com/v1/models",
        )

        proxy_fn.assert_awaited_once_with(
            gateway_id="gw-001",
            task_id="00000000-0000-0000-0000-000000000001",
            agent_id="00000000-0000-0000-0000-000000000002",
            request_type="GET",
            target_url="https://api.example.com/v1/models",
            request_body=None,
            headers=None,
        )
        assert result == {"status": "ok", "data": "response"}

    @pytest.mark.asyncio
    async def test_no_gateway_fails_closed(self):
        """If no egress gateway is configured, external requests must fail."""
        ctx = self._make_context(egress_gateway_id=None, make_external_request=None)

        with pytest.raises(RuntimeError, match="no egress gateway configured"):
            await ctx.external_request(
                request_type="GET",
                target_url="https://api.example.com/v1/models",
            )

    @pytest.mark.asyncio
    async def test_no_proxy_fn_fails_closed(self):
        """If egress_gateway_id is set but proxy_fn is missing, fail closed."""
        ctx = self._make_context(egress_gateway_id="gw-001", make_external_request=None)

        with pytest.raises(RuntimeError, match="no egress gateway configured"):
            await ctx.external_request(
                request_type="POST",
                target_url="https://evil.example.com/steal",
            )

    @pytest.mark.asyncio
    async def test_egress_denial_propagates(self):
        """If the egress proxy raises, the exception must propagate."""
        proxy_fn = AsyncMock(side_effect=PermissionError("Domain not in allowlist"))
        ctx = self._make_context(make_external_request=proxy_fn)

        with pytest.raises(PermissionError, match="Domain not in allowlist"):
            await ctx.external_request(
                request_type="GET",
                target_url="https://denied.example.com/api",
            )

    @pytest.mark.asyncio
    async def test_rate_limit_propagates(self):
        """If the egress proxy rate-limits, the exception must propagate."""
        proxy_fn = AsyncMock(side_effect=ConnectionRefusedError("Rate limit exceeded"))
        ctx = self._make_context(make_external_request=proxy_fn)

        with pytest.raises(ConnectionRefusedError, match="Rate limit exceeded"):
            await ctx.external_request(
                request_type="GET",
                target_url="https://api.example.com/v1/models",
            )

    @pytest.mark.asyncio
    async def test_high_risk_approval_required_propagates(self):
        """If high-risk operation requires approval, the exception propagates."""
        proxy_fn = AsyncMock(
            side_effect=PermissionError("High-risk operation requires approval")
        )
        ctx = self._make_context(make_external_request=proxy_fn)

        with pytest.raises(PermissionError, match="High-risk"):
            await ctx.external_request(
                request_type="DELETE",
                target_url="https://api.example.com/v1/deploy/production",
            )

    @pytest.mark.asyncio
    async def test_request_body_and_headers_forwarded(self):
        """Request body and custom headers must be forwarded to egress proxy."""
        proxy_fn = AsyncMock(return_value={"id": "obj-1"})
        ctx = self._make_context(make_external_request=proxy_fn)

        await ctx.external_request(
            request_type="POST",
            target_url="https://api.example.com/v1/objects",
            request_body={"name": "test"},
            headers={"X-Custom": "value"},
        )

        proxy_fn.assert_awaited_once_with(
            gateway_id="gw-001",
            task_id="00000000-0000-0000-0000-000000000001",
            agent_id="00000000-0000-0000-0000-000000000002",
            request_type="POST",
            target_url="https://api.example.com/v1/objects",
            request_body={"name": "test"},
            headers={"X-Custom": "value"},
        )


class TestMetadataValidation:
    """Verify external_request fails closed when metadata lacks task_uuid or agent_uuid."""

    def _make_context(self, metadata, egress_gateway_id="gw-001", make_external_request=None):
        return AdapterContext(
            task_id="task-1",
            agent_number="AN-001",
            metadata=metadata,
            egress_gateway_id=egress_gateway_id,
            make_external_request=make_external_request,
        )

    @pytest.mark.asyncio
    async def test_missing_task_uuid_fails_closed(self):
        """external_request must raise RuntimeError when metadata has no task_uuid."""
        proxy_fn = AsyncMock(return_value={"status": "ok"})
        ctx = self._make_context(
            make_external_request=proxy_fn,
            metadata={"agent_uuid": "00000000-0000-0000-0000-000000000002"},
        )

        with pytest.raises(RuntimeError, match="task_uuid"):
            await ctx.external_request(
                request_type="GET",
                target_url="https://api.example.com/v1/models",
            )
        proxy_fn.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_missing_agent_uuid_fails_closed(self):
        """external_request must raise RuntimeError when metadata has no agent_uuid."""
        proxy_fn = AsyncMock(return_value={"status": "ok"})
        ctx = self._make_context(
            make_external_request=proxy_fn,
            metadata={"task_uuid": "00000000-0000-0000-0000-000000000001"},
        )

        with pytest.raises(RuntimeError, match="agent_uuid"):
            await ctx.external_request(
                request_type="GET",
                target_url="https://api.example.com/v1/models",
            )
        proxy_fn.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_none_task_uuid_fails_closed(self):
        """external_request must raise RuntimeError when task_uuid is explicitly None."""
        proxy_fn = AsyncMock(return_value={"status": "ok"})
        ctx = self._make_context(
            make_external_request=proxy_fn,
            metadata={"task_uuid": None, "agent_uuid": "some-uuid"},
        )

        with pytest.raises(RuntimeError, match="task_uuid"):
            await ctx.external_request(
                request_type="GET",
                target_url="https://api.example.com/test",
            )
        proxy_fn.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_none_agent_uuid_fails_closed(self):
        """external_request must raise RuntimeError when agent_uuid is explicitly None."""
        proxy_fn = AsyncMock(return_value={"status": "ok"})
        ctx = self._make_context(
            make_external_request=proxy_fn,
            metadata={"task_uuid": "some-uuid", "agent_uuid": None},
        )

        with pytest.raises(RuntimeError, match="agent_uuid"):
            await ctx.external_request(
                request_type="GET",
                target_url="https://api.example.com/test",
            )
        proxy_fn.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_empty_task_uuid_fails_closed(self):
        """external_request must raise RuntimeError when task_uuid is empty string."""
        proxy_fn = AsyncMock(return_value={"status": "ok"})
        ctx = self._make_context(
            make_external_request=proxy_fn,
            metadata={"task_uuid": "", "agent_uuid": "some-uuid"},
        )

        with pytest.raises(RuntimeError, match="task_uuid"):
            await ctx.external_request(
                request_type="GET",
                target_url="https://api.example.com/test",
            )
        proxy_fn.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_valid_metadata_calls_proxy(self):
        """When both task_uuid and agent_uuid are present, proxy is called."""
        proxy_fn = AsyncMock(return_value={"status": "ok"})
        ctx = self._make_context(
            metadata={
                "task_uuid": "00000000-0000-0000-0000-000000000001",
                "agent_uuid": "00000000-0000-0000-0000-000000000002",
            },
            make_external_request=proxy_fn,
        )

        await ctx.external_request(
            request_type="GET",
            target_url="https://api.example.com/v1/models",
        )
        proxy_fn.assert_awaited_once()


class TestEgressServiceTransactionConsistency:
    """Verify _log_egress does NOT commit, and proxy_external_request commits after audit."""

    def test_log_egress_does_not_commit(self):
        """_log_egress should only session.add, not session.commit."""
        import inspect
        from app.services.egress_service import _log_egress
        source = inspect.getsource(_log_egress)
        assert "session.commit()" not in source, (
            "_log_egress must NOT commit — caller must commit after audit"
        )
        assert "session.add" in source, "_log_egress must add the log entry"

    def test_proxy_external_request_commits_after_audit(self):
        """proxy_external_request must commit after write_audit so egress log + audit
        are in the same transaction."""
        import inspect
        from app.services.egress_service import proxy_external_request
        source = inspect.getsource(proxy_external_request)
        # Find the main success path: step 9 log + step 10 audit + commit
        commit_positions = []
        pos = 0
        while True:
            idx = source.find("session.commit()", pos)
            if idx == -1:
                break
            commit_positions.append(idx)
            pos = idx + 1
        # Must have at least one commit in the main path (after audit)
        assert len(commit_positions) >= 1, (
            "proxy_external_request must commit after audit in success path"
        )
        # Verify audit appears before the last commit
        audit_pos = source.find("write_audit", source.find("# 10. Audit"))
        if audit_pos != -1:
            assert any(cp > audit_pos for cp in commit_positions), (
                "session.commit() must appear after write_audit in the success path"
            )

    def test_cached_response_commits_after_audit(self):
        """Cache-hit path must also commit after audit."""
        import inspect
        from app.services.egress_service import proxy_external_request
        source = inspect.getsource(proxy_external_request)
        # Find the cache-hit section
        cache_audit_pos = source.find('"cached": True')
        if cache_audit_pos == -1:
            cache_audit_pos = source.find('"cached": True')
        # After the cache audit, there must be a commit before return
        cache_return_pos = source.find("return cached_data")
        commit_in_cache_section = source.find("session.commit()", cache_audit_pos, cache_return_pos)
        assert commit_in_cache_section != -1, (
            "Cache-hit path must commit after audit before returning cached_data"
        )


class TestEgressFailurePathsPersistEvidence:
    """Verify allowlist-denied, timeout, and request-error paths persist
    egress log + audit + commit BEFORE raising DomainException."""

    @pytest.mark.asyncio
    async def test_allowlist_denied_persists_evidence(self):
        """Allowlist denied must call _log_egress, write_audit, commit, then raise."""
        from app.services.egress_service import proxy_external_request
        from app.exceptions import DomainException

        session = AsyncMock()
        session.commit = AsyncMock()
        session.execute = AsyncMock()
        session.add = MagicMock()

        gateway_id = uuid4()
        agent_id = uuid4()
        task_id = uuid4()

        # Mock gateway: enabled but empty allowlist → domain denied
        mock_gateway = MagicMock()
        mock_gateway.enabled = True
        mock_gateway.domain_allowlist = []
        mock_gateway.rate_limit_config = None
        mock_gateway.cache_config = None
        mock_gateway.secret_store_ref = None
        mock_gateway.cost_tracking = False

        gateway_result = MagicMock()
        gateway_result.scalar_one_or_none.return_value = mock_gateway
        session.execute.return_value = gateway_result

        call_order = []

        with patch("app.services.egress_service._log_egress", new_callable=AsyncMock) as mock_log, \
             patch("app.services.egress_service.write_audit", new_callable=AsyncMock) as mock_audit, \
             patch("app.services.egress_service._get_gateway", new_callable=AsyncMock) as mock_get_gw:

            mock_get_gw.return_value = mock_gateway
            mock_log.side_effect = lambda *a, **kw: call_order.append("log_egress")
            mock_audit.side_effect = lambda *a, **kw: call_order.append("write_audit")
            session.commit.side_effect = lambda: call_order.append("commit")

            with pytest.raises(DomainException) as exc_info:
                await proxy_external_request(
                    session,
                    gateway_id=gateway_id,
                    task_id=task_id,
                    agent_id=agent_id,
                    request_type="GET",
                    target_url="https://denied.example.com/api",
                )

            assert exc_info.value.status_code == 403
            assert call_order == ["log_egress", "write_audit", "commit"], (
                f"Expected log_egress->write_audit->commit, got {call_order}"
            )
            # Verify audit details contain required fields but no secrets
            audit_call = mock_audit.call_args
            details = audit_call.kwargs.get("details", {})
            assert details["request_type"] == "GET"
            assert "denied.example.com" in details["target_url"]
            assert details["status_code"] == 403
            assert "reason" in details
            # Must NOT contain secrets
            assert "request_body" not in details
            assert "Authorization" not in details

    @pytest.mark.asyncio
    async def test_timeout_persists_evidence(self):
        """Timeout path must call _log_egress, write_audit, commit, then raise."""
        from app.services.egress_service import proxy_external_request
        from app.exceptions import DomainException

        session = AsyncMock()
        session.commit = AsyncMock()
        session.execute = AsyncMock()
        session.add = MagicMock()

        gateway_id = uuid4()
        agent_id = uuid4()
        task_id = uuid4()

        mock_gateway = MagicMock()
        mock_gateway.enabled = True
        mock_gateway.domain_allowlist = ["*"]
        mock_gateway.rate_limit_config = None
        mock_gateway.cache_config = None
        mock_gateway.secret_store_ref = None
        mock_gateway.cost_tracking = False

        gateway_result = MagicMock()
        gateway_result.scalar_one_or_none.return_value = mock_gateway
        session.execute.return_value = gateway_result

        call_order = []

        with patch("app.services.egress_service._log_egress", new_callable=AsyncMock) as mock_log, \
             patch("app.services.egress_service.write_audit", new_callable=AsyncMock) as mock_audit, \
             patch("app.services.egress_service._get_gateway", new_callable=AsyncMock) as mock_get_gw, \
             patch("app.services.egress_service._inject_secrets", new_callable=AsyncMock) as mock_inject, \
             patch("app.services.egress_service._check_egress_rate_limit", new_callable=AsyncMock) as mock_rl, \
             patch("httpx.AsyncClient") as mock_client_cls:

            mock_get_gw.return_value = mock_gateway
            mock_inject.return_value = {}
            mock_rl.return_value = None
            mock_log.side_effect = lambda *a, **kw: call_order.append("log_egress")
            mock_audit.side_effect = lambda *a, **kw: call_order.append("write_audit")
            session.commit.side_effect = lambda: call_order.append("commit")

            # Make httpx raise TimeoutException
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(DomainException) as exc_info:
                await proxy_external_request(
                    session,
                    gateway_id=gateway_id,
                    task_id=task_id,
                    agent_id=agent_id,
                    request_type="GET",
                    target_url="https://slow.example.com/api",
                )

            assert exc_info.value.status_code == 504
            assert call_order == ["log_egress", "write_audit", "commit"], (
                f"Expected log_egress->write_audit->commit, got {call_order}"
            )
            audit_call = mock_audit.call_args
            details = audit_call.kwargs.get("details", {})
            assert details["status_code"] == 504
            assert details["latency_ms"] == 30000
            assert "reason" in details
            assert "request_body" not in details
            assert "Authorization" not in details

    @pytest.mark.asyncio
    async def test_request_error_persists_evidence(self):
        """RequestError path must call _log_egress, write_audit, commit, then raise."""
        from app.services.egress_service import proxy_external_request
        from app.exceptions import DomainException

        session = AsyncMock()
        session.commit = AsyncMock()
        session.execute = AsyncMock()
        session.add = MagicMock()

        gateway_id = uuid4()
        agent_id = uuid4()
        task_id = uuid4()

        mock_gateway = MagicMock()
        mock_gateway.enabled = True
        mock_gateway.domain_allowlist = ["*"]
        mock_gateway.rate_limit_config = None
        mock_gateway.cache_config = None
        mock_gateway.secret_store_ref = None
        mock_gateway.cost_tracking = False

        gateway_result = MagicMock()
        gateway_result.scalar_one_or_none.return_value = mock_gateway
        session.execute.return_value = gateway_result

        call_order = []

        with patch("app.services.egress_service._log_egress", new_callable=AsyncMock) as mock_log, \
             patch("app.services.egress_service.write_audit", new_callable=AsyncMock) as mock_audit, \
             patch("app.services.egress_service._get_gateway", new_callable=AsyncMock) as mock_get_gw, \
             patch("app.services.egress_service._inject_secrets", new_callable=AsyncMock) as mock_inject, \
             patch("app.services.egress_service._check_egress_rate_limit", new_callable=AsyncMock) as mock_rl, \
             patch("httpx.AsyncClient") as mock_client_cls:

            mock_get_gw.return_value = mock_gateway
            mock_inject.return_value = {}
            mock_rl.return_value = None
            mock_log.side_effect = lambda *a, **kw: call_order.append("log_egress")
            mock_audit.side_effect = lambda *a, **kw: call_order.append("write_audit")
            session.commit.side_effect = lambda: call_order.append("commit")

            # Make httpx raise RequestError
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(side_effect=httpx.RequestError("connection refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(DomainException) as exc_info:
                await proxy_external_request(
                    session,
                    gateway_id=gateway_id,
                    task_id=task_id,
                    agent_id=agent_id,
                    request_type="POST",
                    target_url="https://down.example.com/api",
                )

            assert exc_info.value.status_code == 502
            assert call_order == ["log_egress", "write_audit", "commit"], (
                f"Expected log_egress->write_audit->commit, got {call_order}"
            )
            audit_call = mock_audit.call_args
            details = audit_call.kwargs.get("details", {})
            assert details["status_code"] == 502
            assert "latency_ms" in details
            assert "reason" in details
            assert "request_body" not in details
            assert "Authorization" not in details

    @pytest.mark.asyncio
    async def test_persist_failure_evidence_commit_error_raises_internal(self):
        """If write_audit or commit fails, must raise DomainException(INTERNAL_ERROR), not swallow."""
        from app.services.egress_service import _persist_failure_evidence
        from app.exceptions import DomainException

        session = AsyncMock()
        session.commit = AsyncMock(side_effect=RuntimeError("DB connection lost"))

        with patch("app.services.egress_service.write_audit", new_callable=AsyncMock):
            with pytest.raises(DomainException) as exc_info:
                await _persist_failure_evidence(
                    session,
                    agent_id=uuid4(),
                    gateway_id=uuid4(),
                    task_id=None,
                    request_type="GET",
                    target_url="https://denied.example.com/api",
                    status_code=403,
                    latency_ms=None,
                    reason="Domain not in allowlist",
                )

            assert exc_info.value.code == "INTERNAL_ERROR"
            assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    async def test_persist_failure_evidence_write_audit_error_raises_internal(self):
        """If write_audit raises, must raise DomainException(INTERNAL_ERROR), not swallow."""
        from app.services.egress_service import _persist_failure_evidence
        from app.exceptions import DomainException

        session = AsyncMock()
        session.commit = AsyncMock()

        with patch("app.services.egress_service.write_audit", new_callable=AsyncMock) as mock_audit:
            mock_audit.side_effect =RuntimeError("audit table missing")
            with pytest.raises(DomainException) as exc_info:
                await _persist_failure_evidence(
                    session,
                    agent_id=uuid4(),
                    gateway_id=uuid4(),
                    task_id=None,
                    request_type="GET",
                    target_url="https://denied.example.com/api",
                    status_code=403,
                    latency_ms=None,
                    reason="Domain not in allowlist",
                )

            assert exc_info.value.code == "INTERNAL_ERROR"
            assert exc_info.value.status_code == 503


class TestAdapterServiceFailClosed:
    """Verify adapter_service fails closed when no config is provided."""

    def test_no_adapter_config_raises_domain_exception(self):
        """_get_adapter with config=None must raise DomainException, not construct defaults."""
        from app.services.adapter_service import _get_adapter
        from app.exceptions import DomainException

        with pytest.raises(DomainException) as exc_info:
            _get_adapter("openclaw", config=None)
        assert exc_info.value.code == "INVALID_REQUEST"
        assert "adapter_config" in exc_info.value.message.lower() or "explicit" in exc_info.value.message.lower()

    def test_registry_key_includes_config_hash(self):
        """Registry keys must differ for different configs to prevent cross-config pollution."""
        from app.services.adapter_service import _registry_key

        key_a = _registry_key("openclaw", {"working_dir": "/opt/a"})
        key_b = _registry_key("openclaw", {"working_dir": "/opt/b"})
        key_none = _registry_key("openclaw", None)

        assert key_a != key_b, "Different configs must produce different registry keys"
        assert key_a != key_none, "Config vs no-config must produce different registry keys"
        assert key_b != key_none

    def test_registry_key_same_config_produces_same_key(self):
        """Same config should produce same key for proper caching."""
        from app.services.adapter_service import _registry_key

        key1 = _registry_key("openclaw", {"working_dir": "/opt/a"})
        key2 = _registry_key("openclaw", {"working_dir": "/opt/a"})
        assert key1 == key2

    def test_dispatch_task_missing_task_uuid_fails(self):
        """dispatch_task must fail closed when metadata lacks task_uuid."""
        from app.services.adapter_service import dispatch_task
        from app.exceptions import DomainException
        import asyncio

        session = AsyncMock()
        with pytest.raises(DomainException) as exc_info:
            asyncio.get_event_loop().run_until_complete(
                dispatch_task(
                    session,
                    task_id="t1",
                    agent_id=str(uuid4()),
                    adapter_type="openclaw",
                    content=[],
                    metadata={"agent_uuid": str(uuid4())},
                    adapter_config={"working_dir": "/test"},
                )
            )
        assert "task_uuid" in exc_info.value.message

    def test_dispatch_task_missing_agent_uuid_fails(self):
        """dispatch_task must fail closed when metadata lacks agent_uuid."""
        from app.services.adapter_service import dispatch_task
        from app.exceptions import DomainException
        import asyncio
        from uuid import uuid4

        session = AsyncMock()
        with pytest.raises(DomainException) as exc_info:
            asyncio.get_event_loop().run_until_complete(
                dispatch_task(
                    session,
                    task_id="t1",
                    agent_id=str(uuid4()),
                    adapter_type="openclaw",
                    content=[],
                    metadata={"task_uuid": str(uuid4())},
                    adapter_config={"working_dir": "/test"},
                )
            )
        assert "agent_uuid" in exc_info.value.message

    def test_dispatch_task_empty_metadata_fails(self):
        """dispatch_task must fail closed when metadata is empty dict."""
        from app.services.adapter_service import dispatch_task
        from app.exceptions import DomainException
        import asyncio

        session = AsyncMock()
        with pytest.raises(DomainException):
            asyncio.get_event_loop().run_until_complete(
                dispatch_task(
                    session,
                    task_id="t1",
                    agent_id=str(uuid4()),
                    adapter_type="openclaw",
                    content=[],
                    metadata={},
                    adapter_config={"working_dir": "/test"},
                )
            )

    def test_dispatch_task_none_metadata_fails(self):
        """dispatch_task must fail closed when metadata is None."""
        from app.services.adapter_service import dispatch_task
        from app.exceptions import DomainException
        import asyncio

        session = AsyncMock()
        with pytest.raises(DomainException):
            asyncio.get_event_loop().run_until_complete(
                dispatch_task(
                    session,
                    task_id="t1",
                    agent_id=str(uuid4()),
                    adapter_type="openclaw",
                    content=[],
                    metadata=None,
                    adapter_config={"working_dir": "/test"},
                )
            )


class TestAdapterServiceAdapterCreation:
    """Verify _get_adapter correctly converts dict config and rejects invalid config."""

    def test_get_adapter_dict_config_creates_openclaw_with_adapter_config(self):
        """_get_adapter('openclaw', dict) must convert dict to AdapterConfig."""
        from app.services.adapter_service import _get_adapter, _ADAPTER_REGISTRY

        # Clear any cached entries from prior tests
        keys_to_remove = [k for k in _ADAPTER_REGISTRY if k.startswith("openclaw:")]
        for k in keys_to_remove:
            del _ADAPTER_REGISTRY[k]

        from agentnet_openclaw.config import AdapterConfig

        dict_config = {
            "agent": {"number": "AN-TEST", "runtime": "openclaw"},
            "openclaw": {"working_dir": "/tmp", "command": "echo"},
        }
        adapter = _get_adapter("openclaw", config=dict_config)
        assert isinstance(adapter._config, AdapterConfig), (
            f"Expected AdapterConfig, got {type(adapter._config)}"
        )
        assert adapter._config.openclaw.working_dir == "/tmp"
        assert adapter._config.agent.number == "AN-TEST"

    def test_get_adapter_invalid_config_returns_domain_exception(self):
        """Invalid dict config must raise DomainException, not leak AttributeError."""
        from app.services.adapter_service import _get_adapter, _ADAPTER_REGISTRY
        from app.exceptions import DomainException

        # Clear cached entries
        keys_to_remove = [k for k in _ADAPTER_REGISTRY if k.startswith("openclaw:")]
        for k in keys_to_remove:
            del _ADAPTER_REGISTRY[k]

        # Missing required 'openclaw.working_dir' field
        bad_config = {"agent": {"number": "AN-X"}}
        with pytest.raises(DomainException) as exc_info:
            _get_adapter("openclaw", config=bad_config)
        assert exc_info.value.status_code == 400
        assert "INVALID_REQUEST" in exc_info.value.code

    def test_get_adapter_empty_config_returns_domain_exception(self):
        """Empty dict must raise DomainException with validation error."""
        from app.services.adapter_service import _get_adapter, _ADAPTER_REGISTRY
        from app.exceptions import DomainException

        keys_to_remove = [k for k in _ADAPTER_REGISTRY if k.startswith("openclaw:")]
        for k in keys_to_remove:
            del _ADAPTER_REGISTRY[k]

        with pytest.raises(DomainException) as exc_info:
            _get_adapter("openclaw", config={})
        assert exc_info.value.status_code == 400

    def test_get_adapter_pydantic_config_passes_through(self):
        """_get_adapter with a Pydantic AdapterConfig should work directly."""
        from app.services.adapter_service import _get_adapter, _ADAPTER_REGISTRY
        from agentnet_openclaw.config import AdapterConfig, AgentConfig, OpenClawConfig

        keys_to_remove = [k for k in _ADAPTER_REGISTRY if k.startswith("openclaw:")]
        for k in keys_to_remove:
            del _ADAPTER_REGISTRY[k]

        pydantic_config = AdapterConfig(
            agent=AgentConfig(number="AN-PY"),
            openclaw=OpenClawConfig(working_dir="/opt/py"),
        )
        adapter = _get_adapter("openclaw", config=pydantic_config)
        assert adapter._config is pydantic_config


class TestRegistryKeyPydanticSupport:
    """Verify _registry_key supports both dict and Pydantic BaseModel objects."""

    def test_registry_key_with_dict(self):
        from app.services.adapter_service import _registry_key

        key = _registry_key("openclaw", {"working_dir": "/opt/a"})
        assert key.startswith("openclaw:")

    def test_registry_key_with_pydantic_model(self):
        from app.services.adapter_service import _registry_key
        from agentnet_openclaw.config import AdapterConfig, AgentConfig, OpenClawConfig

        config = AdapterConfig(
            agent=AgentConfig(number="AN-1"),
            openclaw=OpenClawConfig(working_dir="/opt/a"),
        )
        key = _registry_key("openclaw", config)
        assert key.startswith("openclaw:")
        assert ":no_config" not in key

    def test_registry_key_pydantic_same_config_same_key(self):
        from app.services.adapter_service import _registry_key
        from agentnet_openclaw.config import AdapterConfig, AgentConfig, OpenClawConfig

        c1 = AdapterConfig(
            agent=AgentConfig(number="AN-1"),
            openclaw=OpenClawConfig(working_dir="/opt/a"),
        )
        c2 = AdapterConfig(
            agent=AgentConfig(number="AN-1"),
            openclaw=OpenClawConfig(working_dir="/opt/a"),
        )
        assert _registry_key("openclaw", c1) == _registry_key("openclaw", c2)

    def test_registry_key_pydantic_vs_none_differs(self):
        from app.services.adapter_service import _registry_key
        from agentnet_openclaw.config import AdapterConfig, AgentConfig, OpenClawConfig

        config = AdapterConfig(
            agent=AgentConfig(number="AN-1"),
            openclaw=OpenClawConfig(working_dir="/opt/a"),
        )
        assert _registry_key("openclaw", config) != _registry_key("openclaw", None)


class TestStartStopAdapterRequireConfig:
    """Verify start_adapter/stop_adapter require explicit adapter_config."""

    @pytest.mark.asyncio
    async def test_start_adapter_with_config_succeeds(self):
        from app.services.adapter_service import start_adapter, _ADAPTER_REGISTRY

        keys_to_remove = [k for k in _ADAPTER_REGISTRY if k.startswith("openclaw:")]
        for k in keys_to_remove:
            del _ADAPTER_REGISTRY[k]

        config = {
            "agent": {"number": "AN-START"},
            "openclaw": {"working_dir": "/tmp"},
        }
        await start_adapter("openclaw", adapter_config=config)

    @pytest.mark.asyncio
    async def test_stop_adapter_with_config_succeeds(self):
        from app.services.adapter_service import stop_adapter, _get_adapter, _ADAPTER_REGISTRY

        keys_to_remove = [k for k in _ADAPTER_REGISTRY if k.startswith("openclaw:")]
        for k in keys_to_remove:
            del _ADAPTER_REGISTRY[k]

        config = {
            "agent": {"number": "AN-STOP"},
            "openclaw": {"working_dir": "/tmp"},
        }
        adapter = _get_adapter("openclaw", config=config)
        adapter._running = True  # simulate started
        await stop_adapter("openclaw", adapter_config=config)

    @pytest.mark.asyncio
    async def test_start_adapter_missing_config_raises(self):
        """Calling start_adapter without adapter_config must fail at the Python level
        (TypeError) because the parameter is required — no implicit default."""
        from app.services.adapter_service import start_adapter

        with pytest.raises(TypeError):
            await start_adapter("openclaw")

    @pytest.mark.asyncio
    async def test_stop_adapter_missing_config_raises(self):
        from app.services.adapter_service import stop_adapter

        with pytest.raises(TypeError):
            await stop_adapter("openclaw")


class TestApprovalCreateCommitsAfterAudit:
    """Verify create_approval writes audit in the same transaction as the approval row."""

    def test_create_approval_commits_after_audit(self):
        """create_approval must commit AFTER write_audit, not before."""
        from app.services.approval_service import create_approval
        source = inspect.getsource(create_approval)

        flush_pos = source.find("session.flush()")
        audit_pos = source.find("write_audit")
        commit_pos = source.find("session.commit()")

        assert flush_pos != -1, "create_approval must flush before audit"
        assert flush_pos < audit_pos, "flush must precede write_audit"
        assert audit_pos < commit_pos, (
            "session.commit() must appear after write_audit so approval + audit "
            "are in the same transaction"
        )

    def test_accept_approval_commits_after_audit(self):
        """accept_approval must commit AFTER write_audit, not before."""
        from app.services.approval_service import accept_approval
        source = inspect.getsource(accept_approval)

        audit_pos = source.find("write_audit")
        commit_pos = source.find("session.commit()")

        assert audit_pos != -1, "accept_approval must call write_audit"
        assert commit_pos != -1, "accept_approval must commit"
        assert audit_pos < commit_pos, (
            "session.commit() must appear after write_audit in accept_approval"
        )

    def test_reject_approval_commits_after_audit(self):
        """reject_approval must commit AFTER write_audit, not before."""
        from app.services.approval_service import reject_approval
        source = inspect.getsource(reject_approval)

        audit_pos = source.find("write_audit")
        commit_pos = source.find("session.commit()")

        assert audit_pos != -1, "reject_approval must call write_audit"
        assert commit_pos != -1, "reject_approval must commit"
        assert audit_pos < commit_pos, (
            "session.commit() must appear after write_audit in reject_approval"
        )

    @pytest.mark.asyncio
    async def test_create_approval_audit_and_approval_atomic(self):
        """Mock test: verify create_approval calls flush, write_audit, then commit
        in that order — never commit before audit."""
        from app.services.approval_service import create_approval

        session = AsyncMock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        call_order = []
        session.flush.side_effect = lambda: call_order.append("flush")
        session.commit.side_effect = lambda: call_order.append("commit")

        with patch("app.services.approval_service.write_audit", new_callable=AsyncMock) as mock_audit:
            mock_audit.side_effect = lambda *a, **kw: call_order.append("audit")

            await create_approval(
                session,
                task_id=uuid4(),
                agent_id=uuid4(),
                risk_level="high",
                action_kind="egress_delete",
            )

        assert call_order == ["flush", "audit", "commit"], (
            f"Expected flush->audit->commit, got {call_order}"
        )