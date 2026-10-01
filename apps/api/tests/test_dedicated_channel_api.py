"""Dedicated channel comprehensive tests.

Tests the CRUD, enable/disable, health-check endpoints, RBAC permissions,
audit logging, secret masking (including list-of-dict), ErrorCode constants,
and adapter service configuration correctness.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


def _auth_headers(api_key: str = "test-admin-key") -> dict[str, str]:
    return {"X-API-Key": api_key}


# ── Secret masking ─────────────────────────────────────────────────────────


class TestDedicatedChannelSchema:
    """Schema-level tests including list-of-dict masking."""

    def test_create_schema_valid(self):
        from app.schemas.dedicated_channel import DedicatedChannelCreate

        body = DedicatedChannelCreate(
            channel_name="test-vpn",
            channel_type="vpn",
            source_agent_id=uuid4(),
            target_agent_id=uuid4(),
        )
        assert body.channel_name == "test-vpn"
        assert body.connection_config == {}

    def test_create_schema_rejects_empty_name(self):
        from app.schemas.dedicated_channel import DedicatedChannelCreate
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            DedicatedChannelCreate(
                channel_name="",
                channel_type="vpn",
                source_agent_id=uuid4(),
                target_agent_id=uuid4(),
            )

    def test_create_schema_rejects_negative_bandwidth(self):
        from app.schemas.dedicated_channel import DedicatedChannelCreate
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            DedicatedChannelCreate(
                channel_name="test",
                channel_type="vpn",
                source_agent_id=uuid4(),
                target_agent_id=uuid4(),
                bandwidth_mbps=-10,
            )

    def test_update_schema_all_optional(self):
        from app.schemas.dedicated_channel import DedicatedChannelUpdate

        body = DedicatedChannelUpdate()
        assert body.channel_name is None
        assert body.connection_config is None

    def test_mask_secrets_dict(self):
        from app.schemas.dedicated_channel import _mask_secrets

        config = {
            "host": "10.0.0.1",
            "api_key": "super-secret",
            "auth_token": "bearer-xyz",
            "nested": {"password": "p@ss", "port": 443},
        }
        masked = _mask_secrets(config)
        assert masked["host"] == "10.0.0.1"
        assert masked["api_key"] == "***MASKED***"
        assert masked["auth_token"] == "***MASKED***"
        assert masked["nested"]["password"] == "***MASKED***"
        assert masked["nested"]["port"] == 443

    def test_mask_secrets_list_of_dict(self):
        """Peers: [{private_key: "..."}] must be masked."""
        from app.schemas.dedicated_channel import _mask_secrets

        config = {
            "peers": [
                {"host": "10.0.0.1", "private_key": "secret1"},
                {"host": "10.0.0.2", "private_key": "secret2"},
            ],
            "name": "vpn-mesh",
        }
        masked = _mask_secrets(config)
        assert masked["peers"][0]["private_key"] == "***MASKED***"
        assert masked["peers"][0]["host"] == "10.0.0.1"
        assert masked["peers"][1]["private_key"] == "***MASKED***"
        assert masked["name"] == "vpn-mesh"

    def test_mask_secrets_nested_list_in_dict(self):
        """Deep nesting: tls.certificates[{private_key}]"""
        from app.schemas.dedicated_channel import _mask_secrets

        config = {
            "tls": {
                "certificates": [
                    {"cert": "public-data", "private_key": "secret-key"},
                ],
            },
        }
        masked = _mask_secrets(config)
        cert_entry = masked["tls"]["certificates"][0]
        assert cert_entry["cert"] == "public-data"
        assert cert_entry["private_key"] == "***MASKED***"

    def test_mask_secrets_list_of_scalars_unchanged(self):
        """Non-dict list items should pass through untouched."""
        from app.schemas.dedicated_channel import _mask_secrets

        config = {"allowed_ips": ["10.0.0.0/24", "172.16.0.0/16"]}
        masked = _mask_secrets(config)
        assert masked["allowed_ips"] == ["10.0.0.0/24", "172.16.0.0/16"]

    def test_mask_secrets_empty_list(self):
        from app.schemas.dedicated_channel import _mask_secrets

        config = {"peers": []}
        masked = _mask_secrets(config)
        assert masked["peers"] == []

    def test_mask_secrets_deeply_nested_list(self):
        from app.schemas.dedicated_channel import _mask_secrets

        config = {
            "layers": [
                {"inner": [{"password": "deep-secret", "name": "ok"}]},
            ],
        }
        masked = _mask_secrets(config)
        assert masked["layers"][0]["inner"][0]["password"] == "***MASKED***"
        assert masked["layers"][0]["inner"][0]["name"] == "ok"

    def test_response_from_channel_masks_secrets(self):
        from app.schemas.dedicated_channel import DedicatedChannelResponse
        from types import SimpleNamespace

        channel = SimpleNamespace(
            id=uuid4(),
            scope_id=None,
            channel_name="vpn-1",
            channel_type="vpn",
            source_agent_id=uuid4(),
            target_agent_id=uuid4(),
            connection_config={"host": "10.0.0.1", "secret_key": "abc"},
            encryption_config={"token": "xyz", "algorithm": "AES-256"},
            bandwidth_mbps=100.0,
            latency_target_ms=5.0,
            enabled=True,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        resp = DedicatedChannelResponse.from_channel(channel)
        assert resp.connection_config["secret_key"] == "***MASKED***"
        assert resp.connection_config["host"] == "10.0.0.1"
        assert resp.encryption_config["token"] == "***MASKED***"
        assert resp.encryption_config["algorithm"] == "AES-256"

    def test_response_from_channel_masks_list_secrets(self):
        """Verify masking works for list-of-dict structures in full response."""
        from app.schemas.dedicated_channel import DedicatedChannelResponse
        from types import SimpleNamespace

        channel = SimpleNamespace(
            id=uuid4(),
            scope_id=None,
            channel_name="mesh",
            channel_type="vpn",
            source_agent_id=uuid4(),
            target_agent_id=uuid4(),
            connection_config={
                "peers": [
                    {"host": "10.0.0.1", "private_key": "sk1"},
                    {"host": "10.0.0.2", "private_key": "sk2"},
                ],
            },
            encryption_config={"algorithm": "AES-256"},
            bandwidth_mbps=None,
            latency_target_ms=None,
            enabled=True,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        resp = DedicatedChannelResponse.from_channel(channel)
        assert resp.connection_config["peers"][0]["private_key"] == "***MASKED***"
        assert resp.connection_config["peers"][0]["host"] == "10.0.0.1"
        assert resp.connection_config["peers"][1]["private_key"] == "***MASKED***"


# ── RBAC permission verification ──────────────────────────────────────────


class TestRBACPermissions:
    """Verify that super_admin:write exists in role permissions."""

    def test_super_admin_write_in_super_admin_role(self):
        from app.services.rbac_service import ROLE_PERMISSIONS, PERM_SUPER_ADMIN_WRITE

        assert PERM_SUPER_ADMIN_WRITE in ROLE_PERMISSIONS["super_admin"], (
            f"super_admin:write must be in super_admin permissions"
        )

    def test_super_admin_write_not_in_admin_role(self):
        from app.services.rbac_service import ROLE_PERMISSIONS, PERM_SUPER_ADMIN_WRITE

        assert PERM_SUPER_ADMIN_WRITE not in ROLE_PERMISSIONS["admin"]

    def test_super_admin_write_not_in_user_role(self):
        from app.services.rbac_service import ROLE_PERMISSIONS, PERM_SUPER_ADMIN_WRITE

        assert PERM_SUPER_ADMIN_WRITE not in ROLE_PERMISSIONS["user"]

    def test_admin_has_admin_read(self):
        from app.services.rbac_service import ROLE_PERMISSIONS, PERM_ADMIN_READ
        assert PERM_ADMIN_READ in ROLE_PERMISSIONS["admin"]

    def test_super_admin_has_admin_read(self):
        from app.services.rbac_service import ROLE_PERMISSIONS, PERM_ADMIN_READ
        assert PERM_ADMIN_READ in ROLE_PERMISSIONS["super_admin"]


# ── ErrorCode verification ────────────────────────────────────────────────


class TestErrorCodeConstants:
    """Verify adapter and resource ErrorCodes exist in the protocol."""

    def test_adapter_not_found_exists(self):
        from app.protocol.constants import ErrorCode
        assert ErrorCode.ADAPTER_NOT_FOUND == "ADAPTER_NOT_FOUND"

    def test_adapter_execution_failed_exists(self):
        from app.protocol.constants import ErrorCode
        assert ErrorCode.ADAPTER_EXECUTION_FAILED == "ADAPTER_EXECUTION_FAILED"

    def test_resource_not_found_exists(self):
        from app.protocol.constants import ErrorCode
        assert ErrorCode.RESOURCE_NOT_FOUND == "RESOURCE_NOT_FOUND"


# ── Adapter service verification ──────────────────────────────────────────


class TestAdapterServiceConfig:
    """Verify adapter_service uses correct field names and config."""

    def test_egress_gateway_has_enabled_not_is_active(self):
        from app.models.egress_gateway import EgressGateway
        assert hasattr(EgressGateway, "enabled")
        assert not hasattr(EgressGateway, "is_active")

    def test_openclaw_adapter_requires_config(self):
        """OpenClawAdapter cannot be instantiated without config."""
        from agentnet_openclaw.adapter import OpenClawAdapter
        with pytest.raises(TypeError):
            OpenClawAdapter()

    def test_adapter_service_no_config_fails_closed(self):
        """_get_adapter must fail closed when config is None."""
        from app.services.adapter_service import _get_adapter
        with pytest.raises(Exception) as exc_info:
            _get_adapter("openclaw", config=None)
        assert "requires explicit adapter_config" in str(exc_info.value) or "INVALID_REQUEST" in str(exc_info.value)

    def test_adapter_registry_key_differs_for_config(self):
        """Registry keys must differ when config differs."""
        from app.services.adapter_service import _registry_key
        key_a = _registry_key("openclaw", {"working_dir": "/a"})
        key_b = _registry_key("openclaw", {"working_dir": "/b"})
        key_none = _registry_key("openclaw", None)
        assert key_a != key_b
        assert key_a != key_none
        assert key_b != key_none

    async def test_dispatch_task_fails_without_task_uuid(self):
        """dispatch_task must fail if metadata lacks task_uuid."""
        from app.services.adapter_service import dispatch_task
        from app.exceptions import DomainException

        session = AsyncMock()
        with pytest.raises(DomainException) as exc_info:
            await dispatch_task(
                session,
                task_id="t1",
                agent_id="a1",
                adapter_type="openclaw",
                content=[],
                metadata={"agent_uuid": "some-uuid"},
                adapter_config={"working_dir": "/test"},
            )
        assert "task_uuid" in str(exc_info.value.message)

    async def test_dispatch_task_fails_without_agent_uuid(self):
        """dispatch_task must fail if metadata lacks agent_uuid."""
        from app.services.adapter_service import dispatch_task
        from app.exceptions import DomainException

        session = AsyncMock()
        with pytest.raises(DomainException) as exc_info:
            await dispatch_task(
                session,
                task_id="t1",
                agent_id="a1",
                adapter_type="openclaw",
                content=[],
                metadata={"task_uuid": "some-uuid"},
                adapter_config={"working_dir": "/test"},
            )
        assert "agent_uuid" in str(exc_info.value.message)


# ── Mutation audit persistence ───────────────────────────────────────────


class TestMutationAuditPersistence:
    """Verify mutation endpoints write audit entries and commit in same transaction."""

    def test_create_channel_has_single_commit_and_audit(self):
        """create_dedicated_channel handler should only commit once, after audit."""
        import inspect
        from app.routers.dedicated_channels import create_dedicated_channel
        source = inspect.getsource(create_dedicated_channel)
        # There should be exactly one session.commit() call
        commit_count = source.count("session.commit()")
        assert commit_count == 1, f"Expected 1 commit in create, got {commit_count}"
        # write_audit should appear before the commit
        audit_pos = source.find("write_audit")
        commit_pos = source.find("session.commit()")
        assert audit_pos < commit_pos, "write_audit should be before session.commit()"

    def test_update_channel_has_single_commit_and_audit(self):
        import inspect
        from app.routers.dedicated_channels import update_dedicated_channel
        source = inspect.getsource(update_dedicated_channel)
        commit_count = source.count("session.commit()")
        assert commit_count == 1, f"Expected 1 commit in update, got {commit_count}"
        audit_pos = source.find("write_audit")
        commit_pos = source.find("session.commit()")
        assert audit_pos < commit_pos

    def test_enable_channel_has_single_commit_and_audit(self):
        import inspect
        from app.routers.dedicated_channels import enable_dedicated_channel
        source = inspect.getsource(enable_dedicated_channel)
        commit_count = source.count("session.commit()")
        assert commit_count == 1, f"Expected 1 commit in enable, got {commit_count}"
        audit_pos = source.find("write_audit")
        commit_pos = source.find("session.commit()")
        assert audit_pos < commit_pos

    def test_disable_channel_has_single_commit_and_audit(self):
        import inspect
        from app.routers.dedicated_channels import disable_dedicated_channel
        source = inspect.getsource(disable_dedicated_channel)
        commit_count = source.count("session.commit()")
        assert commit_count == 1, f"Expected 1 commit in disable, got {commit_count}"
        audit_pos = source.find("write_audit")
        commit_pos = source.find("session.commit()")
        assert audit_pos < commit_pos

    def test_health_check_has_single_commit_and_audit(self):
        import inspect
        from app.routers.dedicated_channels import trigger_health_check
        source = inspect.getsource(trigger_health_check)
        commit_count = source.count("session.commit()")
        assert commit_count == 1, f"Expected 1 commit in health-check, got {commit_count}"
        audit_pos = source.find("write_audit")
        commit_pos = source.find("session.commit()")
        assert audit_pos < commit_pos

    def test_delete_channel_has_single_commit_and_audit(self):
        import inspect
        from app.routers.dedicated_channels import delete_dedicated_channel
        source = inspect.getsource(delete_dedicated_channel)
        commit_count = source.count("session.commit()")
        assert commit_count == 1, f"Expected 1 commit in delete, got {commit_count}"
        audit_pos = source.find("write_audit")
        commit_pos = source.find("session.commit()")
        assert audit_pos < commit_pos


# ── Read audit persistence ────────────────────────────────────────────────


class TestReadAuditPersistence:
    """Verify read endpoints commit after write_audit so audit is persisted."""

    def test_list_channels_commits_after_audit(self):
        import inspect
        from app.routers.dedicated_channels import list_dedicated_channels
        source = inspect.getsource(list_dedicated_channels)
        commit_count = source.count("session.commit()")
        assert commit_count >= 1, "list_dedicated_channels must commit to persist read audit"
        audit_pos = source.find("write_audit")
        commit_pos = source.find("session.commit()")
        assert audit_pos < commit_pos

    def test_get_channel_commits_after_audit(self):
        import inspect
        from app.routers.dedicated_channels import get_dedicated_channel
        source = inspect.getsource(get_dedicated_channel)
        commit_count = source.count("session.commit()")
        assert commit_count >= 1, "get_dedicated_channel must commit to persist read audit"
        audit_pos = source.find("write_audit")
        commit_pos = source.find("session.commit()")
        assert audit_pos < commit_pos

    def test_list_health_checks_commits_after_audit(self):
        import inspect
        from app.routers.dedicated_channels import list_health_checks
        source = inspect.getsource(list_health_checks)
        commit_count = source.count("session.commit()")
        assert commit_count >= 1, "list_health_checks must commit to persist read audit"
        audit_pos = source.find("write_audit")
        commit_pos = source.find("session.commit()")
        assert audit_pos < commit_pos


# ── Health check permission ───────────────────────────────────────────────


class TestHealthCheckPermission:
    """Verify that trigger_health_check requires super_admin:write + step-up, not admin:read."""

    def test_health_check_uses_high_risk_dependency(self):
        import inspect
        from app.routers.dedicated_channels import trigger_health_check
        source = inspect.getsource(trigger_health_check)
        assert "require_high_risk" in source, "health-check must use require_high_risk"
        assert "super_admin:write" in source, "health-check must require super_admin:write"
        assert 'admin:read' not in source, "health-check must NOT use admin:read"


# ── 404 ErrorCode consistency ─────────────────────────────────────────────


class TestErrorCode404Consistency:
    """Verify all 404 responses use RESOURCE_NOT_FOUND."""

    def test_update_uses_resource_not_found(self):
        import inspect
        from app.routers.dedicated_channels import update_dedicated_channel
        source = inspect.getsource(update_dedicated_channel)
        assert "RESOURCE_NOT_FOUND" in source, "update must use RESOURCE_NOT_FOUND for 404"
        assert "INVALID_REQUEST" not in source or source.find("INVALID_REQUEST") < source.find("404"), \
            "update should not use INVALID_REQUEST for 404"

    def test_enable_uses_resource_not_found(self):
        import inspect
        from app.routers.dedicated_channels import enable_dedicated_channel
        source = inspect.getsource(enable_dedicated_channel)
        assert "RESOURCE_NOT_FOUND" in source

    def test_disable_uses_resource_not_found(self):
        import inspect
        from app.routers.dedicated_channels import disable_dedicated_channel
        source = inspect.getsource(disable_dedicated_channel)
        assert "RESOURCE_NOT_FOUND" in source

    def test_delete_uses_resource_not_found(self):
        import inspect
        from app.routers.dedicated_channels import delete_dedicated_channel
        source = inspect.getsource(delete_dedicated_channel)
        assert "RESOURCE_NOT_FOUND" in source

    def test_get_uses_resource_not_found(self):
        import inspect
        from app.routers.dedicated_channels import get_dedicated_channel
        source = inspect.getsource(get_dedicated_channel)
        assert "RESOURCE_NOT_FOUND" in source


# ── Endpoint auth tests (unauthenticated) ─────────────────────────────────


class TestDedicatedChannelEndpoints:
    """API endpoint tests. These need auth and DB mocking."""

    def test_list_channels_requires_auth(self, client):
        resp = client.get("/v1/dashboard/admin/dedicated-channels")
        assert resp.status_code in (401, 403)

    def test_get_channel_requires_auth(self, client):
        resp = client.get(f"/v1/dashboard/admin/dedicated-channels/{uuid4()}")
        assert resp.status_code in (401, 403)

    def test_create_channel_requires_auth(self, client):
        resp = client.post(
            "/v1/dashboard/admin/dedicated-channels",
            json={"channel_name": "x", "channel_type": "vpn", "source_agent_id": str(uuid4()), "target_agent_id": str(uuid4())},
        )
        assert resp.status_code in (401, 403)

    def test_update_channel_requires_auth(self, client):
        resp = client.patch(
            f"/v1/dashboard/admin/dedicated-channels/{uuid4()}",
            json={"channel_name": "new"},
        )
        assert resp.status_code in (401, 403)

    def test_delete_channel_requires_auth(self, client):
        resp = client.delete(f"/v1/dashboard/admin/dedicated-channels/{uuid4()}")
        assert resp.status_code in (401, 403)

    def test_enable_channel_requires_auth(self, client):
        resp = client.post(f"/v1/dashboard/admin/dedicated-channels/{uuid4()}/enable")
        assert resp.status_code in (401, 403)

    def test_disable_channel_requires_auth(self, client):
        resp = client.post(f"/v1/dashboard/admin/dedicated-channels/{uuid4()}/disable")
        assert resp.status_code in (401, 403)

    def test_health_check_requires_auth(self, client):
        resp = client.post(f"/v1/dashboard/admin/dedicated-channels/{uuid4()}/health-check")
        assert resp.status_code in (401, 403)

    def test_list_health_checks_requires_auth(self, client):
        resp = client.get(f"/v1/dashboard/admin/dedicated-channels/{uuid4()}/health-checks")
        assert resp.status_code in (401, 403)

    def test_health_check_endpoint_not_accessible_with_admin_read_only(self, client):
        """POST health-check must not be accessible with admin:read permission alone.
        This is a structural test — the endpoint dependency must be require_high_risk
        with super_admin:write, not require_permission with admin:read."""
        import inspect
        from app.routers.dedicated_channels import trigger_health_check
        source = inspect.getsource(trigger_health_check)
        assert "require_high_risk" in source, "health-check must use require_high_risk, not require_permission"
        assert "super_admin:write" in source