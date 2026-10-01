"""Phase Web 2: Session/Auth/CSRF — endpoint and service tests."""
import hashlib
import secrets
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import ApiKey
from app.models.dashboard_session import DashboardSession
from app.models.user import User, UserRole
from app.services.csrf_service import validate_csrf
from app.services.dashboard_session_service import (
    _hash_token,
    create_session,
    find_session_by_token,
    revoke_all_sessions,
    revoke_session,
    rotate_session,
)


def csrf_headers(client):
    """Build X-CSRF-Token header from the CSRF cookie stored on the client."""
    csrf = client.cookies.get("agentnet_csrf")
    if csrf:
        return {"X-CSRF-Token": csrf}
    return {}


@pytest.fixture
async def user_with_key(session: AsyncSession):
    """Create a user with an API key."""
    user = User(
        id=uuid.uuid4(),
        username=f"web2-test-{uuid.uuid4().hex[:8]}",
    )
    session.add(user)
    await session.flush()

    api_key = ApiKey(
        id=uuid.uuid4(),
        user_id=user.id,
        key_hash=hashlib.sha256(b"test-key-12345").hexdigest(),
        key_prefix="ak_test",
        name="test-key",
    )
    session.add(api_key)
    await session.flush()
    return user, api_key, b"test-key-12345"


class TestLogin:
    async def test_login_success(self, client: AsyncClient, user_with_key):
        user, _, plain_key = user_with_key
        resp = await client.post("/v1/dashboard/auth/login", json={
            "username": user.username,
            "api_key": plain_key.decode(),
        })
        assert resp.status_code == 200
        assert "agentnet_session" in resp.cookies
        assert "agentnet_csrf" in resp.cookies

    async def test_login_invalid_credentials(self, client: AsyncClient):
        resp = await client.post("/v1/dashboard/auth/login", json={
            "username": "nonexistent",
            "api_key": "wrong",
        })
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"

    async def test_login_wrong_key(self, client: AsyncClient, user_with_key):
        user, _, _ = user_with_key
        resp = await client.post("/v1/dashboard/auth/login", json={
            "username": user.username,
            "api_key": "wrong-key",
        })
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"

    async def test_login_disabled_user(self, client: AsyncClient, user_with_key, session):
        user, _, plain_key = user_with_key
        user.is_disabled = True
        await session.flush()
        resp = await client.post("/v1/dashboard/auth/login", json={
            "username": user.username,
            "api_key": plain_key.decode(),
        })
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "USER_DISABLED"

    async def test_login_wrong_key_writes_failure_audit(self, client: AsyncClient, user_with_key, session):
        user, _, _ = user_with_key
        # Dynamically generated bogus key; no real credential literal in
        # the source tree.
        import uuid as _uuid
        bogus_key = "ak_" + _uuid.uuid4().hex
        resp = await client.post("/v1/dashboard/auth/login", json={
            "username": user.username,
            "api_key": bogus_key,
        })
        assert resp.status_code == 401

        # Key-first login (migration 0030): a wrong key cannot resolve any
        # account, so the failure audit is anonymous and carries the
        # submitted username for traceability instead of an actor_id.
        from app.models.audit_log import AuditLog
        from sqlalchemy import select
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.action == "dashboard.login.failure",
                AuditLog.actor_id == "unknown",
            )
        )
        # Other anonymous failure audits may exist in the shared test
        # database; match the one for this submission.
        logs = [
            row
            for row in result.scalars()
            if row.details.get("submitted_username") == user.username
        ]
        assert logs, "login failure audit should be written for wrong key"
        log = logs[0]
        assert log.details["reason"] == "invalid_credentials"
        assert log.details["submitted_username"] == user.username

    async def test_login_disabled_user_writes_failure_audit(self, client: AsyncClient, user_with_key, session):
        user, _, plain_key = user_with_key
        user.is_disabled = True
        await session.flush()
        resp = await client.post("/v1/dashboard/auth/login", json={
            "username": user.username,
            "api_key": plain_key.decode(),
        })
        assert resp.status_code == 403

        from app.models.audit_log import AuditLog
        from sqlalchemy import select
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.action == "dashboard.login.failure",
                AuditLog.actor_id == str(user.id),
            )
        )
        log = result.scalar_one_or_none()
        assert log is not None, "login failure audit should be written for disabled user"
        assert log.details["reason"] == "user_disabled"


class TestMe:
    async def test_me_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/v1/dashboard/auth/me")
        assert resp.status_code == 401

    async def test_me_authenticated(self, client: AsyncClient, user_with_key):
        user, _, plain_key = user_with_key
        await client.post("/v1/dashboard/auth/login", json={
            "username": user.username,
            "api_key": plain_key.decode(),
        })
        resp = await client.get("/v1/dashboard/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == user.username
        assert data["role"] == user.role
        assert data["csrf_required"] is True


class TestLogout:
    async def test_logout(self, client: AsyncClient, user_with_key, session):
        user, _, plain_key = user_with_key
        await client.post("/v1/dashboard/auth/login", json={
            "username": user.username,
            "api_key": plain_key.decode(),
        })
        resp = await client.post("/v1/dashboard/auth/logout", headers=csrf_headers(client))
        assert resp.status_code == 200
        result = await session.execute(
            select(DashboardSession).where(DashboardSession.user_id == user.id)
        )
        ds = result.scalar_one()
        assert ds.revoked_at is not None


class TestStepUp:
    async def test_step_up_success(self, client: AsyncClient, user_with_key):
        user, _, plain_key = user_with_key
        await client.post("/v1/dashboard/auth/login", json={
            "username": user.username,
            "api_key": plain_key.decode(),
        })
        resp = await client.post("/v1/dashboard/auth/step-up", json={
            "api_key": plain_key.decode(),
        }, headers=csrf_headers(client))
        assert resp.status_code == 200
        assert "agentnet_session" in resp.cookies

    async def test_step_up_wrong_key_writes_failure_audit(self, client: AsyncClient, user_with_key, session):
        user, _, _ = user_with_key
        await client.post("/v1/dashboard/auth/login", json={
            "username": user.username,
            "api_key": "test-key-12345",
        })
        resp = await client.post("/v1/dashboard/auth/step-up", json={
            "api_key": "wrong-key",
        }, headers=csrf_headers(client))
        assert resp.status_code == 403

        from app.models.audit_log import AuditLog
        from sqlalchemy import select
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.action == "dashboard.step_up.failure",
                AuditLog.actor_id == str(user.id),
            )
        )
        log = result.scalar_one_or_none()
        assert log is not None, "step-up failure audit should be written for wrong key"
        assert log.details["reason"] == "invalid_credentials"

    async def test_step_up_expired_key_rejected(self, client: AsyncClient, session):
        """Step-up with an expired API key returns 403."""
        from datetime import UTC, datetime, timedelta

        user = User(id=uuid.uuid4(), username=f"expired-stepup-{uuid.uuid4().hex[:8]}")
        session.add(user)
        await session.flush()

        expired_key = ApiKey(
            id=uuid.uuid4(),
            user_id=user.id,
            key_hash=hashlib.sha256(b"expired-stepup-key").hexdigest(),
            key_prefix="ak_exp",
            name="expired-key",
            expires_at=datetime.now(UTC) - timedelta(days=1),
        )
        session.add(expired_key)
        await session.flush()

        # Login with a non-expired key first (to get a session)
        valid_key = ApiKey(
            id=uuid.uuid4(),
            user_id=user.id,
            key_hash=hashlib.sha256(b"valid-stepup-key").hexdigest(),
            key_prefix="ak_val",
            name="valid-key",
        )
        session.add(valid_key)
        await session.flush()

        resp = await client.post("/v1/dashboard/auth/login", json={
            "username": user.username,
            "api_key": "valid-stepup-key",
        })
        assert resp.status_code == 200

        # Try step-up with the expired key
        resp = await client.post("/v1/dashboard/auth/step-up", json={
            "api_key": "expired-stepup-key",
        }, headers=csrf_headers(client))
        assert resp.status_code == 403


class TestSessionService:
    async def test_create_and_find_session(self, session: AsyncSession, user_with_key):
        user, _, _ = user_with_key
        ds, token, csrf = await create_session(session, user)
        await session.flush()

        found = await find_session_by_token(session, token)
        assert found is not None
        assert found.id == ds.id

        not_found = await find_session_by_token(session, "wrong-token")
        assert not_found is None

    async def test_rotate_session(self, session: AsyncSession, user_with_key):
        user, _, _ = user_with_key
        ds, token, csrf = await create_session(session, user)
        await session.flush()

        new_ds, new_token, new_csrf = await rotate_session(session, ds)
        await session.flush()

        await session.refresh(ds)
        assert ds.revoked_at is not None

        found = await find_session_by_token(session, new_token)
        assert found is not None

    async def test_revoke_all_sessions(self, session: AsyncSession, user_with_key):
        user, _, _ = user_with_key
        await create_session(session, user)
        await create_session(session, user)
        await session.flush()

        count = await revoke_all_sessions(session, user.id, reason="test")
        await session.flush()
        assert count == 2

    async def test_disabled_user_cannot_find_session(self, session: AsyncSession, user_with_key):
        user, _, _ = user_with_key
        ds, token, _ = await create_session(session, user)
        await session.flush()

        user.is_disabled = True
        await session.flush()

        found = await find_session_by_token(session, token)
        assert found is None


class TestCSRF:
    async def test_valid_csrf(self, session: AsyncSession, user_with_key):
        user, _, _ = user_with_key
        ds, _, _ = await create_session(session, user)
        await session.flush()

        plain_csrf = secrets.token_urlsafe(32)
        ds.csrf_hash = _hash_token(plain_csrf)
        await session.flush()

        await validate_csrf(session, ds, plain_csrf)

    async def test_missing_csrf_raises(self, session: AsyncSession, user_with_key):
        user, _, _ = user_with_key
        ds, _, _ = await create_session(session, user)
        await session.flush()

        with pytest.raises(Exception):
            await validate_csrf(session, ds, "")
