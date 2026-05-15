"""Phase 10: Hardening tests - rate limiting, timeout worker, audit logging."""

import uuid
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.protocol.constants import ErrorCode, TaskStatus
from app.exceptions import DomainException
from app.config import get_settings
from app.models.task import VALID_TRANSITIONS


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac





class TestPhase10Config:
    """Verify Phase 10 config fields exist with sensible defaults."""

    def test_rate_limit_fields(self):
        s = get_settings()
        assert s.rate_limit_window_s == 60.0
        assert s.rate_limit_global_max >= 1000  # test env may override
        assert s.rate_limit_user_max >= 300
        assert s.rate_limit_agent_max >= 200
        assert s.rate_limit_ip_max >= 100

    def test_task_timeout_fields(self):
        s = get_settings()
        assert s.task_max_runtime_s == 600
        assert s.task_lease_duration_s == 60
        assert s.timeout_worker_interval_s == 30.0


# ---------------------------------------------------------------------------
# Rate Limit Service Tests (unit, no Redis needed for structure)
# ---------------------------------------------------------------------------

class TestRateLimitService:
    """Unit tests for rate limit service."""

    @pytest.mark.anyio
    @patch("app.services.rate_limit_service.redis_client")
    async def test_check_rate_limit_accepts_no_dimensions(self, mock_redis):
        """check_rate_limit with no dimensions should pass."""
        mock_redis.eval = AsyncMock(return_value=0)
        from app.services.rate_limit_service import check_rate_limit
        # Should not raise
        await check_rate_limit()

    @pytest.mark.anyio
    async def test_check_rate_limit_no_max_should_pass(self):
        """With max_requests=0, rate limiting is disabled for that dimension."""
        from app.services.rate_limit_service import _check_and_increment
        # Should not raise
        await _check_and_increment("user", "test-user", max_requests=0, window_s=60)

    @pytest.mark.anyio
    @patch("app.services.rate_limit_service.redis_client")
    async def test_rate_limit_status_returns_structure(self, mock_redis):
        """get_rate_limit_status should return expected structure."""
        mock_redis.zremrangebyscore = AsyncMock()
        mock_redis.zcard = AsyncMock(return_value=0)
        from app.services.rate_limit_service import get_rate_limit_status
        status = await get_rate_limit_status(user_id="test-user")
        assert "window_seconds" in status
        assert "limits" in status
        assert "current" in status
        assert status["limits"]["user"] >= 300  # test env may override


# ---------------------------------------------------------------------------
# Audit Log Service Tests
# ---------------------------------------------------------------------------

class TestAuditService:
    """Tests for audit logging."""

    def test_write_audit_structure(self):
        """write_audit function exists and accepts expected parameters."""
        from app.services.audit_service import write_audit, list_audit_logs
        assert callable(write_audit)
        assert callable(list_audit_logs)

    @pytest.mark.anyio
    async def test_list_audit_logs_filters(self):
        """list_audit_logs function exists with filter parameters."""
        import inspect
        from app.services.audit_service import list_audit_logs
        sig = inspect.signature(list_audit_logs)
        params = list(sig.parameters.keys())
        assert "session" in params
        assert "actor_type" in params
        assert "action" in params
        assert "task_id" in params


# ---------------------------------------------------------------------------
# Timeout Worker Tests
# ---------------------------------------------------------------------------

class TestTimeoutWorker:
    """Tests for timeout worker."""

    def test_timeout_worker_exists(self):
        """Timeout worker module imports correctly."""
        from app.workers.timeout_worker import (
            timeout_loop,
            expire_stale_tasks,
            expire_long_running_tasks,
            expire_stale_approvals,
        )
        assert callable(timeout_loop)
        assert callable(expire_stale_tasks)
        assert callable(expire_long_running_tasks)
        assert callable(expire_stale_approvals)

    def test_timeoutable_statuses_are_non_terminal(self):
        """Timeout worker targets only non-terminal statuses."""
        from app.workers.timeout_worker import _TIMEOUTABLE_STATUSES
        terminal = {TaskStatus.COMPLETED.value, TaskStatus.FAILED.value,
                     TaskStatus.CANCELLED.value, TaskStatus.EXPIRED.value,
                     TaskStatus.REJECTED.value}
        assert not _TIMEOUTABLE_STATUSES & terminal


# ---------------------------------------------------------------------------
# Rate Limit Endpoint Tests
# ---------------------------------------------------------------------------

class TestRateLimitEndpoints:
    """Integration tests for rate limiting on endpoints."""

    @pytest.mark.anyio
    async def test_health_endpoint_not_rate_limited(self, client):
        """Health endpoint should not be rate limited."""
        for _ in range(5):
            resp = await client.get("/healthz")
            assert resp.status_code == 200

    @pytest.mark.anyio
    @patch("app.services.rate_limit_service.redis_client")
    async def test_task_create_rejected_when_no_auth(self, mock_redis, client):
        """Task creation without auth returns 401, not 429 (auth check first)."""
        mock_redis.eval = AsyncMock(return_value=0)
        resp = await client.post("/v1/tasks", json={
            "assigned_to": "AN-GLOBAL-XXXXXX-00",
            "payload": {"action": "test"},
        })
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Error Code Coverage
# ---------------------------------------------------------------------------

class TestPhase10ErrorCodes:
    """Ensure Phase 10 error codes are defined."""

    def test_rate_limited_code(self):
        assert ErrorCode.RATE_LIMITED.value == "RATE_LIMITED"

    def test_task_expired_code(self):
        assert ErrorCode.TASK_EXPIRED.value == "TASK_EXPIRED"

    def test_task_lease_expired_code(self):
        assert ErrorCode.TASK_LEASE_EXPIRED.value == "TASK_LEASE_EXPIRED"

    def test_message_too_large_code(self):
        assert ErrorCode.MESSAGE_TOO_LARGE.value == "MESSAGE_TOO_LARGE"


# ---------------------------------------------------------------------------
# Audit Model Tests
# ---------------------------------------------------------------------------

class TestAuditModel:
    """Tests for AuditLog SQLAlchemy model."""

    def test_audit_log_model_fields(self):
        """AuditLog model has all required fields."""
        from app.models.audit_log import AuditLog
        from sqlalchemy import inspect as sa_inspect

        mapper = sa_inspect(AuditLog)
        columns = {c.name: c for c in mapper.columns}

        required_fields = [
            "id", "actor_type", "actor_id", "action",
            "resource_type", "resource_id", "trace_id",
            "task_id", "message_id", "delivery_status",
            "error_code", "details", "request_ip", "created_at",
        ]
        for field in required_fields:
            assert field in columns, f"Missing field: {field}"

    def test_audit_log_registered_in_models_init(self):
        """AuditLog is exported from models.__init__."""
        from app.models import AuditLog
        assert AuditLog is not None

    def test_audit_log_no_secret_fields(self):
        """AuditLog model must not have token/secret fields."""
        from app.models.audit_log import AuditLog
        from sqlalchemy import inspect as sa_inspect

        mapper = sa_inspect(AuditLog)
        column_names = {c.name.lower() for c in mapper.columns}
        forbidden = ["token", "secret", "password", "api_key", "key"]
        for word in forbidden:
            assert word not in column_names, f"Forbidden field pattern: {word}"


# ---------------------------------------------------------------------------
# Task State Transition Validation
# ---------------------------------------------------------------------------

class TestTaskStateTransitions:
    """Ensure task state transitions allow expiry."""

    def test_expired_is_allowed_from_running(self):
        assert TaskStatus.EXPIRED.value in VALID_TRANSITIONS.get(
            TaskStatus.RUNNING.value, set()
        )

    def test_expired_is_allowed_from_created(self):
        assert TaskStatus.EXPIRED.value in VALID_TRANSITIONS.get(
            TaskStatus.CREATED.value, set()
        )

    def test_expired_is_terminal(self):
        assert VALID_TRANSITIONS.get(TaskStatus.EXPIRED.value, set()) == set()


# ---------------------------------------------------------------------------
# Payload Size Check
# ---------------------------------------------------------------------------

class TestPayloadSize:
    """Verify payload size validation."""

    def test_max_payload_bytes_config(self):
        s = get_settings()
        assert s.max_payload_bytes == 1_048_576  # 1MB default

    def test_payload_limit_rejects_oversized(self):
        """check_payload_size should reject oversized payloads."""
        from app.websocket.protocol import check_payload_size

        # Payload under limit
        check_payload_size("x" * 1000)  # Should not raise

        # Payload over limit
        with pytest.raises(DomainException) as exc:
            check_payload_size("x" * 2_000_000)
        assert exc.value.code == ErrorCode.MESSAGE_TOO_LARGE.value
