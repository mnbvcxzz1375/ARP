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
        resp = await client.post("/v1/dashboard/auth/logout")
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
        })
        assert resp.status_code == 200
        assert "agentnet_session" in resp.cookies

    async def test_step_up_wrong_key(self, client: AsyncClient, user_with_key):
        user, _, _ = user_with_key
        await client.post("/v1/dashboard/auth/login", json={
            "username": user.username,
            "api_key": "test-key-12345",
        })
        resp = await client.post("/v1/dashboard/auth/step-up", json={
            "api_key": "wrong-key",
        })
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "INVALID_STEP_UP"


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
