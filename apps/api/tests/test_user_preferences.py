"""User preferences (locale + appearance JSONB) — endpoint tests.

Covers GET/PATCH /v1/dashboard/auth/me/preferences: happy path, locale
validation (400), unknown preference keys (400), unauthenticated access
(401), missing CSRF (403), audit row writes, and locale surfacing on
/v1/dashboard/auth/me.
"""
import hashlib
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import ApiKey
from app.models.audit_log import AuditLog
from app.models.user import User

PREFERENCES_URL = "/v1/dashboard/auth/me/preferences"
ME_URL = "/v1/dashboard/auth/me"


def csrf_headers(client):
    """Build X-CSRF-Token header from the CSRF cookie stored on the client."""
    csrf = client.cookies.get("agentnet_csrf")
    if csrf:
        return {"X-CSRF-Token": csrf}
    return {}


@pytest.fixture
async def user_with_key(session: AsyncSession):
    """Create a user with an API key, matching the login flow."""
    user = User(
        id=uuid.uuid4(),
        username=f"prefs-test-{uuid.uuid4().hex[:8]}",
    )
    session.add(user)
    await session.flush()

    api_key = ApiKey(
        id=uuid.uuid4(),
        user_id=user.id,
        key_hash=hashlib.sha256(b"prefs-key-12345").hexdigest(),
        key_prefix="ak_prefs",
        name="prefs-test-key",
    )
    session.add(api_key)
    await session.flush()
    return user, api_key, b"prefs-key-12345"


async def _login(client: AsyncClient, user_with_key) -> None:
    user, _, plain_key = user_with_key
    resp = await client.post(
        "/v1/dashboard/auth/login",
        json={"username": user.username, "api_key": plain_key.decode()},
    )
    assert resp.status_code == 200


class TestGetPreferences:
    async def test_unauthenticated_returns_401(self, client: AsyncClient):
        resp = await client.get(PREFERENCES_URL)
        assert resp.status_code == 401

    async def test_defaults_when_never_set(
        self, client: AsyncClient, user_with_key
    ):
        await _login(client, user_with_key)
        resp = await client.get(PREFERENCES_URL)
        assert resp.status_code == 200
        assert resp.json() == {"locale": None, "preferences": {}}

    async def test_returns_stored_values(
        self, client: AsyncClient, user_with_key, session: AsyncSession
    ):
        user, _, _ = user_with_key
        user.locale = "zh"
        user.preferences = {"theme": "dark", "fontScale": 1.25}
        await session.flush()

        await _login(client, user_with_key)
        resp = await client.get(PREFERENCES_URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["locale"] == "zh"
        assert body["preferences"] == {"theme": "dark", "fontScale": 1.25}

    async def test_me_includes_locale(self, client: AsyncClient, user_with_key):
        await _login(client, user_with_key)
        resp = await client.get(ME_URL)
        assert resp.status_code == 200
        assert "locale" in resp.json()
        assert resp.json()["locale"] is None


class TestUpdatePreferences:
    async def test_unauthenticated_returns_401(self, client: AsyncClient):
        resp = await client.patch(
            PREFERENCES_URL, json={"locale": "zh"}, headers=csrf_headers(client)
        )
        assert resp.status_code == 401

    async def test_missing_csrf_rejected(self, client: AsyncClient, user_with_key):
        await _login(client, user_with_key)
        resp = await client.patch(PREFERENCES_URL, json={"locale": "zh"})
        assert resp.status_code == 403

    async def test_happy_path_updates_locale_and_preferences(
        self, client: AsyncClient, user_with_key
    ):
        await _login(client, user_with_key)

        resp = await client.patch(
            PREFERENCES_URL,
            json={
                "locale": "zh",
                "preferences": {
                    "theme": "dark",
                    "fontScale": 1.1,
                    "reducedMotion": True,
                },
            },
            headers=csrf_headers(client),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["locale"] == "zh"
        assert body["preferences"] == {
            "theme": "dark",
            "fontScale": 1.1,
            "reducedMotion": True,
        }

        # The persisted state must be readable back from GET.
        resp = await client.get(PREFERENCES_URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["locale"] == "zh"
        assert body["preferences"] == {
            "theme": "dark",
            "fontScale": 1.1,
            "reducedMotion": True,
        }

        # /me must surface the new locale too.
        resp = await client.get(ME_URL)
        assert resp.json()["locale"] == "zh"

    async def test_patch_merges_preferences_instead_of_replacing(
        self, client: AsyncClient, user_with_key
    ):
        await _login(client, user_with_key)

        resp = await client.patch(
            PREFERENCES_URL,
            json={"preferences": {"theme": "dark", "fontScale": 1.0}},
            headers=csrf_headers(client),
        )
        assert resp.status_code == 200

        # Partial update: fontScale is untouched, reducedMotion is added.
        resp = await client.patch(
            PREFERENCES_URL,
            json={"preferences": {"reducedMotion": True}},
            headers=csrf_headers(client),
        )
        assert resp.status_code == 200
        assert resp.json()["preferences"] == {
            "theme": "dark",
            "fontScale": 1.0,
            "reducedMotion": True,
        }

    async def test_locale_null_clears_locale(
        self, client: AsyncClient, user_with_key
    ):
        await _login(client, user_with_key)

        resp = await client.patch(
            PREFERENCES_URL, json={"locale": "zh"}, headers=csrf_headers(client)
        )
        assert resp.status_code == 200
        assert resp.json()["locale"] == "zh"

        resp = await client.patch(
            PREFERENCES_URL, json={"locale": None}, headers=csrf_headers(client)
        )
        assert resp.status_code == 200
        assert resp.json()["locale"] is None

    async def test_invalid_locale_returns_400(
        self, client: AsyncClient, user_with_key
    ):
        await _login(client, user_with_key)
        resp = await client.patch(
            PREFERENCES_URL, json={"locale": "fr"}, headers=csrf_headers(client)
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "INVALID_REQUEST"

    async def test_unknown_preference_key_returns_400(
        self, client: AsyncClient, user_with_key
    ):
        await _login(client, user_with_key)
        resp = await client.patch(
            PREFERENCES_URL,
            json={"preferences": {"dashboardDensity": "compact"}},
            headers=csrf_headers(client),
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == "INVALID_REQUEST"
        assert "dashboardDensity" in body["error"]["message"]

    async def test_invalid_theme_value_returns_400(
        self, client: AsyncClient, user_with_key
    ):
        await _login(client, user_with_key)
        resp = await client.patch(
            PREFERENCES_URL,
            json={"preferences": {"theme": "neon"}},
            headers=csrf_headers(client),
        )
        assert resp.status_code == 400

    async def test_font_scale_out_of_range_returns_400(
        self, client: AsyncClient, user_with_key
    ):
        await _login(client, user_with_key)
        resp = await client.patch(
            PREFERENCES_URL,
            json={"preferences": {"fontScale": 3.0}},
            headers=csrf_headers(client),
        )
        assert resp.status_code == 400

    async def test_updated_value_rejected_before_write(
        self, client: AsyncClient, user_with_key
    ):
        """A rejected PATCH must not partially persist."""
        await _login(client, user_with_key)
        resp = await client.patch(
            PREFERENCES_URL,
            json={"locale": "zh", "preferences": {"bogus": 1}},
            headers=csrf_headers(client),
        )
        assert resp.status_code == 400

        resp = await client.get(PREFERENCES_URL)
        assert resp.status_code == 200
        assert resp.json() == {"locale": None, "preferences": {}}

    async def test_update_writes_audit_row(
        self, client: AsyncClient, user_with_key, session: AsyncSession
    ):
        user, _, _ = user_with_key
        await _login(client, user_with_key)

        resp = await client.patch(
            PREFERENCES_URL,
            json={"locale": "en", "preferences": {"theme": "light"}},
            headers=csrf_headers(client),
        )
        assert resp.status_code == 200

        result = await session.execute(
            select(AuditLog).where(
                AuditLog.actor_id == str(user.id),
                AuditLog.action == "dashboard.preferences.update",
                AuditLog.resource_type == "user",
                AuditLog.resource_id == str(user.id),
            )
        )
        log = result.scalar_one_or_none()
        assert log is not None, "preferences update audit row should be written"
        assert set(log.details["changed_fields"]) == {"locale", "preferences"}
