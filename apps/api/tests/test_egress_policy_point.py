"""M4 egress policy decision point + default-deny guard tests.

Scope of this round (honest marking):
- proxy_external_request is the ONLY permitted outbound valve; the
  policy point inserted before the allowlist denies non-http(s)
  schemes and internal targets (loopback/private/reserved/link-local,
  or IPs inside the gateway scope's network_cidr) with persisted
  evidence, unless the gateway was registered with
  allow_internal_egress=True (audited as egress.internal_allowed).
- The host-validation utilities (validate_host_not_internal etc.) are
  exposed for M5's MCP adapter to validate HTTP-type MCP server
  addresses — this round's only live consumer of the host policy.
- dispatch_task has zero live callers in the request path; its test
  here is a single-test-scope direct call (wiring proof only).
- NOT covered (documented gaps): direct httpx imports and stdio child
  processes bypass the valve — network-layer defence in depth is a
  post-milestone item; DNS names are never resolved.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from app.exceptions import DomainException
from app.models.agent import Agent
from app.models.api_key import ApiKey
from app.models.audit_log import AuditLog
from app.models.egress_gateway import EgressGateway
from app.models.egress_log import EgressLog
from app.models.network_scope import NetworkScope
from app.models.user import User
from app.services import egress_service
from app.services.auth import generate_api_key

# asyncio_mode=auto collects the async tests; no module-level asyncio
# mark (it would warn on the pure-function host-utility classes).


# ── Shared fixtures ────────────────────────────────────────────────


async def _make_user(session, role: str = "user") -> tuple[User, str]:
    user = User(username=f"m4-{role}-{uuid.uuid4().hex[:6]}", role=role)
    session.add(user)
    await session.flush()
    raw_key, key_hash, key_prefix = generate_api_key()
    session.add(ApiKey(user_id=user.id, key_hash=key_hash, key_prefix=key_prefix, name="test"))
    await session.flush()
    return user, raw_key


async def _make_agent(session, owner: User) -> Agent:
    agent = Agent(
        agent_number=f"AN-M4-{uuid.uuid4().hex[:8]}",
        owner_id=owner.id,
        name="M4PolicyAgent",
        runtime="test",
        inbound_policy="public",
    )
    session.add(agent)
    await session.flush()
    return agent


async def _make_task(session, agent: Agent):
    # egress_logs.task_id has an FK to tasks: dispatch tests must carry a
    # real task id in metadata, otherwise the evidence write fails on the
    # FK instead of exercising the policy path under test.
    from app.models.task import Task
    from app.protocol.constants import TaskStatus

    task = Task(
        created_by=agent.id,
        assigned_to=agent.id,
        status=TaskStatus.RUNNING.value,
    )
    session.add(task)
    await session.flush()
    return task


async def _make_scope(session, user: User, network_cidr: str | None = None) -> NetworkScope:
    scope = NetworkScope(
        scope_name=f"m4-scope-{uuid.uuid4().hex[:6]}",
        scope_type="personal",
        user_id=user.id,
        network_cidr=network_cidr,
    )
    session.add(scope)
    await session.flush()
    return scope


async def _make_gateway(
    session,
    scope: NetworkScope,
    *,
    allowlist: list[str] | None = None,
    allow_internal: bool = False,
    enabled: bool = True,
) -> EgressGateway:
    gateway = EgressGateway(
        scope_id=scope.id,
        gateway_name=f"m4-gw-{uuid.uuid4().hex[:6]}",
        gateway_type="api",
        domain_allowlist=allowlist if allowlist is not None else ["*"],
        allow_internal_egress=allow_internal,
        enabled=enabled,
    )
    session.add(gateway)
    await session.flush()
    return gateway


def _csrf_headers(client) -> dict:
    csrf = client.cookies.get("agentnet_csrf")
    return {"X-CSRF-Token": csrf} if csrf else {}


async def _login_super_admin(client, session) -> tuple[User, str]:
    user, raw_key = await _make_user(session, role="super_admin")
    await session.commit()
    resp = await client.post(
        "/v1/dashboard/auth/login",
        json={"username": user.username, "api_key": raw_key},
    )
    assert resp.status_code == 200, resp.text
    step_up = await client.post(
        "/v1/dashboard/auth/step-up",
        json={"api_key": raw_key},
        headers=_csrf_headers(client),
    )
    assert step_up.status_code == 200, step_up.text
    return user, raw_key


def _mock_httpx_response():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": "ok"}
    mock_response.text = '{"data": "ok"}'
    mock_response.content = b'{"data": "ok"}'
    mock_instance = AsyncMock()
    mock_instance.request = AsyncMock(return_value=mock_response)
    return mock_instance


# ── Host validation utilities (pure functions) ─────────────────────


class TestHostUtilities:
    def test_normalize_target_host_strips_port_userinfo_case_and_dot(self):
        assert egress_service.normalize_target_host("API.Example.com:8443") == "api.example.com"
        assert egress_service.normalize_target_host("user:pass@api.example.com") == "api.example.com"
        assert egress_service.normalize_target_host("api.example.com.") == "api.example.com"
        assert egress_service.normalize_target_host("[::1]:8080") == "::1"
        assert egress_service.normalize_target_host("::1") == "::1"
        assert egress_service.normalize_target_host("") == ""
        assert egress_service.normalize_target_host("api.example.com:notaport") == ""

    def test_is_internal_host_ip_literals(self):
        internal = ["127.0.0.1", "10.0.0.1", "192.168.1.1", "172.16.0.1", "169.254.169.254",
                    "0.0.0.0", "::1", "fc00::1", "fe80::1", "224.0.0.1", "240.0.0.1"]
        for host in internal:
            assert egress_service.is_internal_host(host) is True, host

    def test_is_internal_host_public_ip_and_dns(self):
        public = ["93.184.216.34", "8.8.8.8", "api.example.com", "sub.safe-domain.com"]
        for host in public:
            assert egress_service.is_internal_host(host) is False, host

    def test_is_internal_host_localhost_names(self):
        assert egress_service.is_internal_host("localhost") is True
        assert egress_service.is_internal_host("LOCALHOST") is True
        assert egress_service.is_internal_host("svc.localhost") is True
        assert egress_service.is_internal_host("") is True  # empty host denies

    def test_host_matches_cidr(self):
        assert egress_service.host_matches_cidr("10.1.2.3", "10.0.0.0/8") is True
        assert egress_service.host_matches_cidr("11.0.0.1", "10.0.0.0/8") is False
        assert egress_service.host_matches_cidr("2001:db8::1", "2001:db8::/32") is True
        assert egress_service.host_matches_cidr("api.example.com", "10.0.0.0/8") is False
        assert egress_service.host_matches_cidr("10.1.2.3", "not-a-cidr") is False

    def test_validate_host_not_internal_rejects_internal(self):
        for host in ["127.0.0.1", "localhost", "10.0.0.1", "169.254.169.254", "::1"]:
            with pytest.raises(DomainException) as exc_info:
                egress_service.validate_host_not_internal(host)
            assert exc_info.value.status_code == 403
            assert exc_info.value.code == "EGRESS_BLOCKED"

    def test_validate_host_not_internal_accepts_public(self):
        egress_service.validate_host_not_internal("api.example.com")
        egress_service.validate_host_not_internal("93.184.216.34")


# ── Policy decision point (DB-backed) ──────────────────────────────


class TestPolicyDecisionPoint:
    async def test_internal_targets_denied_with_evidence(self, session):
        user, _ = await _make_user(session)
        scope = await _make_scope(session, user)
        gateway = await _make_gateway(session, scope)
        agent = await _make_agent(session, user)

        denied = [
            "http://127.0.0.1:8080/admin",
            "http://localhost/api",
            "http://10.0.0.1/api",
            "http://169.254.169.254/latest/meta-data/",
            "http://[::1]/api",
        ]
        for url in denied:
            with pytest.raises(DomainException) as exc_info:
                await egress_service.check_egress_target_policy(
                    session,
                    gateway=gateway,
                    target_url=url,
                    request_type="GET",
                    agent_id=agent.id,
                )
            assert exc_info.value.status_code == 403
            assert exc_info.value.code == "EGRESS_BLOCKED"
            assert "internal" in exc_info.value.message.lower()

        # Evidence persisted: one egress log per denied target, all 403.
        result = await session.execute(
            select(EgressLog).where(EgressLog.gateway_id == gateway.id)
        )
        logs = result.scalars().all()
        assert len(logs) == len(denied)
        assert all(log.status_code == 403 for log in logs)
        assert {log.target_domain for log in logs} == {
            "127.0.0.1", "localhost", "10.0.0.1", "169.254.169.254", "::1",
        }

    async def test_public_target_passes_without_log(self, session):
        user, _ = await _make_user(session)
        scope = await _make_scope(session, user)
        gateway = await _make_gateway(session, scope)
        agent = await _make_agent(session, user)

        # No exception, and no egress log written by the policy point.
        await egress_service.check_egress_target_policy(
            session,
            gateway=gateway,
            target_url="https://api.example.com/v1/models",
            request_type="GET",
            agent_id=agent.id,
        )
        result = await session.execute(
            select(EgressLog).where(EgressLog.gateway_id == gateway.id)
        )
        assert result.scalars().all() == []

    async def test_non_http_scheme_denied(self, session):
        user, _ = await _make_user(session)
        scope = await _make_scope(session, user)
        gateway = await _make_gateway(session, scope)
        agent = await _make_agent(session, user)

        for url in ["ftp://api.example.com/x", "file:///etc/passwd", "gopher://localhost:70"]:
            with pytest.raises(DomainException) as exc_info:
                await egress_service.check_egress_target_policy(
                    session,
                    gateway=gateway,
                    target_url=url,
                    request_type="GET",
                    agent_id=agent.id,
                )
            assert exc_info.value.status_code == 403
            assert "http" in exc_info.value.message.lower()

    async def test_scope_network_cidr_filters_public_ip(self, session):
        # A public IP range as the scope CIDR isolates the CIDR filter
        # from the loopback/private checks.
        user, _ = await _make_user(session)
        scope = await _make_scope(session, user, network_cidr="93.184.216.0/24")
        gateway = await _make_gateway(session, scope)
        agent = await _make_agent(session, user)

        with pytest.raises(DomainException) as exc_info:
            await egress_service.check_egress_target_policy(
                session,
                gateway=gateway,
                target_url="http://93.184.216.34/x",
                request_type="GET",
                agent_id=agent.id,
            )
        assert exc_info.value.status_code == 403
        assert "93.184.216.0/24" in exc_info.value.message

    async def test_allow_internal_egress_permits_and_audits(self, session):
        user, _ = await _make_user(session)
        scope = await _make_scope(session, user)
        gateway = await _make_gateway(session, scope, allow_internal=True)
        agent = await _make_agent(session, user)

        await egress_service.check_egress_target_policy(
            session,
            gateway=gateway,
            target_url="http://10.0.0.1/internal-model",
            request_type="POST",
            agent_id=agent.id,
        )
        await session.flush()

        result = await session.execute(
            select(AuditLog).where(
                AuditLog.action == "egress.internal_allowed",
                AuditLog.resource_id == str(gateway.id),
            )
        )
        audits = result.scalars().all()
        assert len(audits) == 1
        assert audits[0].details["host"] == "10.0.0.1"
        assert audits[0].details["allow_internal_egress"] is True

    async def test_scope_cidr_allowed_when_flag_set(self, session):
        user, _ = await _make_user(session)
        scope = await _make_scope(session, user, network_cidr="93.184.216.0/24")
        gateway = await _make_gateway(session, scope, allow_internal=True)
        agent = await _make_agent(session, user)

        await egress_service.check_egress_target_policy(
            session,
            gateway=gateway,
            target_url="http://93.184.216.34/x",
            request_type="GET",
            agent_id=agent.id,
        )
        await session.flush()
        result = await session.execute(
            select(AuditLog).where(AuditLog.action == "egress.internal_allowed")
        )
        assert len(result.scalars().all()) == 1


# ── Policy point inside proxy_external_request ─────────────────────


class TestProxyPolicyIntegration:
    async def test_internal_target_denied_httpx_never_called(self, session):
        user, _ = await _make_user(session)
        scope = await _make_scope(session, user)
        gateway = await _make_gateway(session, scope)
        agent = await _make_agent(session, user)

        with patch("app.services.egress_service.httpx.AsyncClient") as mock_httpx:
            with pytest.raises(DomainException) as exc_info:
                await egress_service.proxy_external_request(
                    session,
                    gateway_id=gateway.id,
                    task_id=None,
                    agent_id=agent.id,
                    request_type="GET",
                    target_url="http://169.254.169.254/latest/meta-data/",
                )
            assert exc_info.value.status_code == 403
            mock_httpx.assert_not_called()

        result = await session.execute(
            select(EgressLog).where(EgressLog.gateway_id == gateway.id)
        )
        logs = result.scalars().all()
        assert len(logs) == 1
        assert logs[0].status_code == 403

    async def test_public_target_proceeds(self, session):
        user, _ = await _make_user(session)
        scope = await _make_scope(session, user)
        gateway = await _make_gateway(session, scope)
        agent = await _make_agent(session, user)

        mock_instance = _mock_httpx_response()
        with patch("app.services.egress_service.httpx.AsyncClient") as mock_httpx:
            mock_httpx.return_value.__aenter__.return_value = mock_instance
            result = await egress_service.proxy_external_request(
                session,
                gateway_id=gateway.id,
                task_id=None,
                agent_id=agent.id,
                request_type="GET",
                target_url="https://api.example.com/data",
            )
        assert result == {"data": "ok"}

    async def test_internal_allowed_flag_reaches_httpx_and_audits(self, session):
        user, _ = await _make_user(session)
        scope = await _make_scope(session, user)
        gateway = await _make_gateway(session, scope, allow_internal=True)
        agent = await _make_agent(session, user)

        mock_instance = _mock_httpx_response()
        with patch("app.services.egress_service.httpx.AsyncClient") as mock_httpx:
            mock_httpx.return_value.__aenter__.return_value = mock_instance
            result = await egress_service.proxy_external_request(
                session,
                gateway_id=gateway.id,
                task_id=None,
                agent_id=agent.id,
                request_type="GET",
                target_url="http://10.0.0.1/internal-model",
            )
        assert result == {"data": "ok"}
        mock_instance.request.assert_awaited_once()

        await session.flush()
        result = await session.execute(
            select(AuditLog).where(AuditLog.action == "egress.internal_allowed")
        )
        assert len(result.scalars().all()) == 1

    async def test_netloc_normalization_matches_allowlist_entry(self, session):
        user, _ = await _make_user(session)
        scope = await _make_scope(session, user)
        gateway = await _make_gateway(
            session, scope, allowlist=["api.example.com", "*.safe-domain.com"]
        )

        for url in [
            "https://API.Example.com:8443/data",          # case + port
            "https://user:pass@api.example.com/data",     # userinfo
            "https://api.example.com./data",              # trailing dot
            "https://sub.safe-domain.com/x",              # wildcard
        ]:
            allowed = await egress_service.check_domain_allowlist(
                session, gateway.id, url
            )
            assert allowed is True, url

        # The normalized host still must not match sibling domains.
        allowed = await egress_service.check_domain_allowlist(
            session, gateway.id, "https://evil.example.com/data"
        )
        assert allowed is False


# ── Agent ↔ gateway binding API (PATCH /v1/agents/{id}) ─────────────


class TestAgentGatewayBinding:
    async def test_bind_then_get_reads_back(self, client, session):
        user, raw_key = await _make_user(session)
        agent = await _make_agent(session, user)
        scope = await _make_scope(session, user)
        gateway = await _make_gateway(session, scope)
        await session.commit()

        resp = await client.patch(
            f"/v1/agents/{agent.id}",
            json={"egress_gateway_id": str(gateway.id)},
            headers={"X-API-Key": raw_key},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["egress_gateway_id"] == str(gateway.id)

        # GET reads the binding back.
        resp = await client.get(f"/v1/agents/{agent.id}", headers={"X-API-Key": raw_key})
        assert resp.status_code == 200
        assert resp.json()["egress_gateway_id"] == str(gateway.id)

    async def test_unbind_with_explicit_null(self, client, session):
        user, raw_key = await _make_user(session)
        agent = await _make_agent(session, user)
        scope = await _make_scope(session, user)
        gateway = await _make_gateway(session, scope)
        agent.egress_gateway_id = gateway.id
        await session.commit()

        resp = await client.patch(
            f"/v1/agents/{agent.id}",
            json={"egress_gateway_id": None},
            headers={"X-API-Key": raw_key},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["egress_gateway_id"] is None

    async def test_omitted_field_leaves_binding_unchanged(self, client, session):
        user, raw_key = await _make_user(session)
        agent = await _make_agent(session, user)
        scope = await _make_scope(session, user)
        gateway = await _make_gateway(session, scope)
        agent.egress_gateway_id = gateway.id
        await session.commit()

        resp = await client.patch(
            f"/v1/agents/{agent.id}", json={}, headers={"X-API-Key": raw_key}
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["egress_gateway_id"] == str(gateway.id)

    async def test_bind_unknown_gateway_404(self, client, session):
        user, raw_key = await _make_user(session)
        agent = await _make_agent(session, user)
        await session.commit()

        resp = await client.patch(
            f"/v1/agents/{agent.id}",
            json={"egress_gateway_id": str(uuid.uuid4())},
            headers={"X-API-Key": raw_key},
        )
        assert resp.status_code == 404

    async def test_bind_disabled_gateway_400(self, client, session):
        user, raw_key = await _make_user(session)
        agent = await _make_agent(session, user)
        scope = await _make_scope(session, user)
        gateway = await _make_gateway(session, scope, enabled=False)
        await session.commit()

        resp = await client.patch(
            f"/v1/agents/{agent.id}",
            json={"egress_gateway_id": str(gateway.id)},
            headers={"X-API-Key": raw_key},
        )
        assert resp.status_code == 400

    async def test_bind_gateway_from_global_catalog_ok(self, client, session):
        # The gateway catalog is admin-curated and global: binding
        # resolves by gateway id regardless of which user seeded the
        # scope, mirroring how the console attaches agents to gateways.
        user, raw_key = await _make_user(session)
        agent = await _make_agent(session, user)
        other, _ = await _make_user(session)
        other_scope = await _make_scope(session, other)
        gateway = await _make_gateway(session, other_scope)
        await session.commit()

        resp = await client.patch(
            f"/v1/agents/{agent.id}",
            json={"egress_gateway_id": str(gateway.id)},
            headers={"X-API-Key": raw_key},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["egress_gateway_id"] == str(gateway.id)


# ── Gateway registration-time validation ──────────────────────────


class TestGatewayRegistrationValidation:
    async def test_create_with_unknown_scope_400(self, client, session):
        await _login_super_admin(client, session)
        resp = await client.post(
            "/v1/egress/gateways",
            json={
                "scope_id": str(uuid.uuid4()),
                "gateway_name": "m4-bad-scope",
                "gateway_type": "api",
            },
            headers=_csrf_headers(client),
        )
        assert resp.status_code == 400, resp.text

    async def test_create_with_bad_domain_entries_400(self, client, session):
        _, _ = await _login_super_admin(client, session)
        user2, _ = await _make_user(session)
        scope2 = await _make_scope(session, user2)
        await session.commit()

        bad_entries = [
            "http://evil.com",        # scheme smuggled in
            "api.example.com:8080",   # port
            "api.example.com/admin",  # path
            "user@api.example.com",   # userinfo
            "",                       # empty
        ]
        for entry in bad_entries:
            resp = await client.post(
                "/v1/egress/gateways",
                json={
                    "scope_id": str(scope2.id),
                    "gateway_name": f"m4-bad-domain-{entry[:8] or 'empty'}",
                    "gateway_type": "api",
                    "domain_allowlist": [entry],
                },
                headers=_csrf_headers(client),
            )
            assert resp.status_code == 400, (entry, resp.text)

    async def test_create_with_non_env_secret_ref_400(self, client, session):
        _, _ = await _login_super_admin(client, session)
        user2, _ = await _make_user(session)
        scope2 = await _make_scope(session, user2)
        await session.commit()

        for ref in ["sk-1234567890abcdef", "vault://secrets/api-key", "env:", "env: has space"]:
            resp = await client.post(
                "/v1/egress/gateways",
                json={
                    "scope_id": str(scope2.id),
                    "gateway_name": f"m4-bad-secret-{ref[:8]}",
                    "gateway_type": "api",
                    "secret_store_ref": ref,
                },
                headers=_csrf_headers(client),
            )
            assert resp.status_code == 400, (ref, resp.text)

    async def test_create_happy_path_defaults_flag_false(self, client, session):
        _, _ = await _login_super_admin(client, session)
        user2, _ = await _make_user(session)
        scope2 = await _make_scope(session, user2)
        await session.commit()

        resp = await client.post(
            "/v1/egress/gateways",
            json={
                "scope_id": str(scope2.id),
                "gateway_name": "m4-created",
                "gateway_type": "api",
                "domain_allowlist": ["api.example.com"],
                "secret_store_ref": "env:AGENTNET_TEST_EGRESS_REF_OK",
            },
            headers=_csrf_headers(client),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["allow_internal_egress"] is False

    async def test_update_with_bad_domain_entry_400(self, client, session):
        _, _ = await _login_super_admin(client, session)
        user2, _ = await _make_user(session)
        scope2 = await _make_scope(session, user2)
        gateway = await _make_gateway(session, scope2)
        await session.commit()

        resp = await client.patch(
            f"/v1/egress/gateways/{gateway.id}",
            json={"domain_allowlist": ["api.example.com:8080"]},
            headers=_csrf_headers(client),
        )
        assert resp.status_code == 400, resp.text


# ── Delete referenced gateway → 409 ────────────────────────────────


class TestDeleteReferencedGateway:
    async def test_delete_referenced_gateway_409(self, client, session):
        _, _ = await _login_super_admin(client, session)
        user2, _ = await _make_user(session)
        agent = await _make_agent(session, user2)
        scope = await _make_scope(session, user2)
        gateway = await _make_gateway(session, scope)
        agent.egress_gateway_id = gateway.id
        await session.commit()

        resp = await client.delete(
            f"/v1/egress/gateways/{gateway.id}", headers=_csrf_headers(client)
        )
        assert resp.status_code == 409, resp.text
        message = resp.json()["error"]["message"]
        assert "bound" in message.lower() or "agents" in message.lower()

        # Gateway still exists after the refused delete.
        resp = await client.get(f"/v1/egress/gateways/{gateway.id}")
        assert resp.status_code == 200

    async def test_delete_after_unbind_succeeds(self, client, session):
        _, _ = await _login_super_admin(client, session)
        user2, _ = await _make_user(session)
        scope = await _make_scope(session, user2)
        gateway = await _make_gateway(session, scope)
        # No agent bound → plain delete works as before.
        await session.commit()

        resp = await client.delete(
            f"/v1/egress/gateways/{gateway.id}", headers=_csrf_headers(client)
        )
        assert resp.status_code == 204, resp.text


# ── network_cidr registration validation ───────────────────────────


class TestNetworkCidrValidation:
    async def test_validate_network_cidr(self):
        from app.services.network_topology_service import validate_network_cidr

        for value in [None, "", "10.0.0.0/8", "192.168.1.0/24", "::/0", "10.1.2.3/8"]:
            validate_network_cidr(value)  # must not raise

        for value in ["999.0.0.0/8", "not-a-cidr", "10.0.0.0/33"]:
            with pytest.raises(DomainException) as exc_info:
                validate_network_cidr(value)
            assert exc_info.value.status_code == 400

    async def test_create_scope_with_invalid_cidr_400(self, client, session):
        admin, raw_key = await _login_super_admin(client, session)
        await session.commit()

        resp = await client.post(
            "/v1/dashboard/admin/network/scopes",
            json={
                "user_id": str(admin.id),
                "scope_name": "m4-bad-cidr-scope",
                "scope_type": "personal",
                "network_cidr": "10.0.0.0/33",
            },
            headers={"X-API-Key": raw_key},
        )
        assert resp.status_code == 400, resp.text

    async def test_create_scope_with_valid_cidr_201(self, client, session):
        admin, raw_key = await _login_super_admin(client, session)
        await session.commit()

        resp = await client.post(
            "/v1/dashboard/admin/network/scopes",
            json={
                "user_id": str(admin.id),
                "scope_name": "m4-good-cidr-scope",
                "scope_type": "personal",
                "network_cidr": "10.0.0.0/8",
            },
            headers={"X-API-Key": raw_key},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["network_cidr"] == "10.0.0.0/8"

    async def test_update_scope_with_invalid_cidr_400(self, client, session):
        admin, raw_key = await _login_super_admin(client, session)
        scope = await _make_scope(session, admin, network_cidr="10.0.0.0/8")
        await session.commit()

        resp = await client.put(
            f"/v1/dashboard/admin/network/scopes/{scope.id}",
            json={"network_cidr": "300.0.0.0/8"},
            headers={"X-API-Key": raw_key},
        )
        assert resp.status_code == 400, resp.text


# ── dispatch_task direct-call wiring (single-test-scope) ────────────


class _CapturingAdapter:
    """Fake adapter: records the AdapterContext and exercises the
    platform-provided make_external_request callback exactly like a
    real adapter would (via AdapterContext.external_request)."""

    def __init__(self, config=None):
        self.config = config
        self.context = None
        self.calls: list[dict] = []

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def handle_task(self, context, content):
        self.context = context
        return await context.external_request(
            request_type="GET",
            target_url=self.config["target_url"],
        )


class TestDispatchTaskEgressWiring:
    async def test_dispatch_routes_internal_target_to_policy_point(self, session):
        from app.services.adapter_service import dispatch_task

        user, _ = await _make_user(session)
        scope = await _make_scope(session, user)
        gateway = await _make_gateway(session, scope)
        agent = await _make_agent(session, user)
        agent.egress_gateway_id = gateway.id
        task = await _make_task(session, agent)
        await session.flush()

        adapter = _CapturingAdapter(config={"target_url": "http://10.0.0.1/internal"})

        with patch(
            "app.services.adapter_service._get_adapter", return_value=adapter
        ), patch("app.services.egress_service.httpx.AsyncClient") as mock_httpx:
            with pytest.raises(DomainException) as exc_info:
                await dispatch_task(
                    session,
                    task_id="m4-task-1",
                    agent_id=str(agent.id),
                    adapter_type="openclaw",
                    content=[{"type": "text", "text": "x"}],
                    metadata={
                        "task_uuid": str(task.id),
                        "agent_uuid": str(agent.id),
                    },
                    adapter_config={"target_url": "http://10.0.0.1/internal"},
                )
            assert exc_info.value.status_code == 403
            mock_httpx.assert_not_called()

        # The context the adapter received is bound to the gateway.
        assert adapter.context is not None
        assert adapter.context.egress_gateway_id == str(gateway.id)
        assert adapter.context.make_external_request is not None

    async def test_dispatch_routes_public_target_through_proxy(self, session):
        from app.services.adapter_service import dispatch_task

        user, _ = await _make_user(session)
        scope = await _make_scope(session, user)
        gateway = await _make_gateway(session, scope)
        agent = await _make_agent(session, user)
        agent.egress_gateway_id = gateway.id
        task = await _make_task(session, agent)
        await session.flush()

        adapter = _CapturingAdapter(config={"target_url": "https://api.example.com/data"})
        mock_instance = _mock_httpx_response()

        with patch(
            "app.services.adapter_service._get_adapter", return_value=adapter
        ), patch("app.services.egress_service.httpx.AsyncClient") as mock_httpx:
            mock_httpx.return_value.__aenter__.return_value = mock_instance
            result = await dispatch_task(
                session,
                task_id="m4-task-2",
                agent_id=str(agent.id),
                adapter_type="openclaw",
                content=[{"type": "text", "text": "x"}],
                metadata={
                    "task_uuid": str(task.id),
                    "agent_uuid": str(agent.id),
                },
                adapter_config={"target_url": "https://api.example.com/data"},
            )
        assert result == {"data": "ok"}

    async def test_dispatch_fails_closed_without_gateway(self, session):
        from app.services.adapter_service import dispatch_task

        user, _ = await _make_user(session)
        agent = await _make_agent(session, user)  # no egress_gateway_id
        task = await _make_task(session, agent)
        await session.flush()

        adapter = _CapturingAdapter(config={"target_url": "https://api.example.com/data"})

        with patch(
            "app.services.adapter_service._get_adapter", return_value=adapter
        ):
            # The adapter's fail-closed RuntimeError surfaces wrapped as
            # ADAPTER_EXECUTION_FAILED — the wiring never silently
            # succeeds without a gateway.
            with pytest.raises(DomainException, match="no egress gateway configured") as exc_info:
                await dispatch_task(
                    session,
                    task_id="m4-task-3",
                    agent_id=str(agent.id),
                    adapter_type="openclaw",
                    content=[{"type": "text", "text": "x"}],
                    metadata={
                        "task_uuid": str(task.id),
                        "agent_uuid": str(agent.id),
                    },
                    adapter_config={"target_url": "https://api.example.com/data"},
                )
            assert exc_info.value.status_code == 500
