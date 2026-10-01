"""Organization RBAC: org-domain permission resolution and enterprise provisioning.

Covers:
- ORG_MANAGER_PERMISSIONS / ORG_MEMBER_PERMISSIONS constants
- resolve_user_permissions(): platform ∪ org permissions, multi-org union
- fail-closed behavior (membership read failure → empty permissions)
- /me echo: resolved permissions + organizations list; super_admin keeps
  the full global permission set
- Enterprise access-request approval: Organization created, applicant
  added as manager, enterprise NetworkScope backfilled with org_id,
  platform role unchanged ('user')
- Degradation: disabling an organization removes its org permissions
"""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.access_request import AccessRequest
from app.models.api_key import ApiKey
from app.models.network_scope import NetworkScope
from app.models.organization import Organization, OrganizationMember
from app.models.user import User
from app.services.auth import generate_api_key
from app.services.rbac_service import (
    ORG_MANAGER_PERMISSIONS,
    ORG_MEMBER_PERMISSIONS,
    ROLE_PERMISSIONS,
    resolve_user_permissions,
)

pytestmark = pytest.mark.asyncio


def _csrf_headers(client: AsyncClient) -> dict:
    csrf = client.cookies.get("agentnet_csrf")
    return {"X-CSRF-Token": csrf} if csrf else {}


async def _make_user(session, username: str, role: str = "user") -> User:
    user = User(username=username, role=role)
    session.add(user)
    await session.flush()
    return user


async def _make_org(
    session,
    name: str,
    slug: str,
    creator: User | None = None,
    disabled: bool = False,
) -> Organization:
    org = Organization(
        name=name,
        slug=slug,
        created_by_user_id=creator.id if creator else None,
        is_disabled=disabled,
    )
    session.add(org)
    await session.flush()
    return org


async def _add_member(session, org: Organization, user: User, role: str) -> OrganizationMember:
    member = OrganizationMember(org_id=org.id, user_id=user.id, role=role)
    session.add(member)
    await session.flush()
    return member


async def _login_super_admin(client: AsyncClient, session) -> str:
    """Create a super_admin, log in + step up, return the request_id flow helper."""
    user = User(username="org_admin_test", role="super_admin")
    session.add(user)
    await session.flush()

    raw_key, key_hash, key_prefix = generate_api_key()
    session.add(ApiKey(user_id=user.id, key_hash=key_hash, key_prefix=key_prefix, name="test"))
    await session.commit()

    resp = await client.post(
        "/v1/dashboard/auth/login",
        json={"username": "org_admin_test", "api_key": raw_key},
    )
    assert resp.status_code == 200
    step_up = await client.post(
        "/v1/dashboard/auth/step-up",
        json={"api_key": raw_key},
        headers=_csrf_headers(client),
    )
    assert step_up.status_code == 200
    return raw_key


# ──────────────────────────────────────────────────────────────────
# Permission constants
# ──────────────────────────────────────────────────────────────────


async def test_org_manager_permissions_exact():
    """Manager gets exactly the contracted org-domain permission set."""
    assert ORG_MANAGER_PERMISSIONS == [
        "overview:read:org",
        "agent:read:org",
        "task:read:org",
        "approval:handle:org",
        "connection:read:org",
        "policy:read:org",
        "sla:read:org",
        "audit:read:org",
        "org:manage",
    ]


async def test_org_member_permissions_read_only_overview():
    """Member (employee) only gets the org overview read."""
    assert ORG_MEMBER_PERMISSIONS == ["overview:read:org"]


async def test_platform_role_permissions_unchanged():
    """Platform role sets must not contain org-domain permissions."""
    for perms in ROLE_PERMISSIONS.values():
        assert not any(p.endswith(":org") or p == "org:manage" for p in perms)


# ──────────────────────────────────────────────────────────────────
# resolve_user_permissions
# ──────────────────────────────────────────────────────────────────


class TestResolveUserPermissions:
    async def test_plain_user_gets_only_platform_perms(self, session):
        user = await _make_user(session, "plain_user")
        perms = await resolve_user_permissions(session, user.id)
        assert perms == sorted(ROLE_PERMISSIONS["user"])
        assert not any(p.endswith(":org") for p in perms)

    async def test_org_manager_gets_org_perms(self, session):
        user = await _make_user(session, "org_manager")
        org = await _make_org(session, "Acme", "acme", creator=user)
        await _add_member(session, org, user, "manager")

        perms = await resolve_user_permissions(session, user.id)
        assert set(ORG_MANAGER_PERMISSIONS) <= set(perms)
        # platform permissions are still present
        assert "agent:read:own" in perms
        # sorted output
        assert perms == sorted(perms)

    async def test_org_member_gets_only_overview(self, session):
        user = await _make_user(session, "org_member")
        org = await _make_org(session, "Beta", "beta", creator=user)
        await _add_member(session, org, user, "member")

        perms = await resolve_user_permissions(session, user.id)
        assert "overview:read:org" in perms
        assert "agent:read:org" not in perms
        assert "org:manage" not in perms

    async def test_multi_org_union(self, session):
        """Manager of one org + member of another gets the union."""
        user = await _make_user(session, "multi_org_user")
        org_a = await _make_org(session, "Alpha", "alpha", creator=user)
        org_b = await _make_org(session, "BetaCorp", "betacorp", creator=user)
        await _add_member(session, org_a, user, "manager")
        await _add_member(session, org_b, user, "member")

        perms = await resolve_user_permissions(session, user.id)
        expected = set(ROLE_PERMISSIONS["user"]) | set(ORG_MANAGER_PERMISSIONS) | {"overview:read:org"}
        assert set(perms) == expected

    async def test_super_admin_keeps_global_perms(self, session):
        """super_admin retains the full global set even with no org membership."""
        user = await _make_user(session, "super_no_org", role="super_admin")
        perms = await resolve_user_permissions(session, user.id)
        assert set(perms) == set(ROLE_PERMISSIONS["super_admin"])

    async def test_super_admin_with_org_gets_union(self, session):
        user = await _make_user(session, "super_with_org", role="super_admin")
        org = await _make_org(session, "Gamma", "gamma", creator=user)
        await _add_member(session, org, user, "manager")
        perms = await resolve_user_permissions(session, user.id)
        assert set(ROLE_PERMISSIONS["super_admin"]) <= set(perms)
        assert "org:manage" in perms

    async def test_disabled_user_gets_no_permissions(self, session):
        user = await _make_user(session, "disabled_user")
        user.is_disabled = True
        await session.flush()
        perms = await resolve_user_permissions(session, user.id)
        assert perms == []

    async def test_unknown_role_fail_closed(self):
        """An unknown platform role resolves to no permissions (fail-closed).

        Persisting an invalid role is itself blocked by the users
        ck_users_valid_role check constraint, so this is exercised at the
        resolution level with a stand-in session.
        """
        from unittest.mock import AsyncMock, MagicMock

        user = User(id=uuid.uuid4(), username="weird_role_user", role="wizard")

        result = MagicMock()
        result.scalar_one_or_none.return_value = user
        fake_session = MagicMock()
        fake_session.execute = AsyncMock(return_value=result)

        perms = await resolve_user_permissions(fake_session, user.id)
        assert perms == []

    async def test_disabled_org_revokes_permissions(self, session):
        """Disabling an organization removes its org-domain permissions."""
        user = await _make_user(session, "disabled_org_manager")
        org = await _make_org(session, "Delta", "delta", creator=user)
        await _add_member(session, org, user, "manager")

        assert "org:manage" in await resolve_user_permissions(session, user.id)

        org.is_disabled = True
        await session.flush()

        perms = await resolve_user_permissions(session, user.id)
        assert "org:manage" not in perms
        assert "overview:read:org" not in perms
        # platform permissions survive org disablement
        assert "agent:read:own" in perms

    async def test_removed_membership_revokes_permissions(self, session):
        """Removing the membership row removes the org permissions."""
        user = await _make_user(session, "removed_member")
        org = await _make_org(session, "Epsilon", "epsilon", creator=user)
        member = await _add_member(session, org, user, "manager")

        assert "org:manage" in await resolve_user_permissions(session, user.id)

        await session.delete(member)
        await session.flush()

        perms = await resolve_user_permissions(session, user.id)
        assert "org:manage" not in perms
        assert perms == sorted(ROLE_PERMISSIONS["user"])

    async def test_fail_closed_on_membership_read_failure(self, session, monkeypatch):
        """Any exception while resolving yields an empty list (fail-closed)."""
        user = await _make_user(session, "fail_closed_user")

        original_execute = session.execute

        async def _exploding_execute(*args, **kwargs):
            # Let the user lookup succeed, blow up on the membership read.
            stmt = args[0] if args else kwargs.get("stmt")
            if stmt is not None and "organization_members" in str(stmt):
                raise RuntimeError("membership table unavailable")
            return await original_execute(*args, **kwargs)

        monkeypatch.setattr(session, "execute", _exploding_execute)

        perms = await resolve_user_permissions(session, user.id)
        assert perms == []

    async def test_fail_closed_on_user_read_failure(self, session, monkeypatch):
        """Exception on the initial user read also yields an empty list."""
        user = await _make_user(session, "fail_closed_user2")

        async def _exploding_execute(*args, **kwargs):
            raise RuntimeError("database unavailable")

        monkeypatch.setattr(session, "execute", _exploding_execute)

        perms = await resolve_user_permissions(session, user.id)
        assert perms == []

    async def test_unknown_user_returns_empty(self, session):
        perms = await resolve_user_permissions(session, uuid.uuid4())
        assert perms == []


# ──────────────────────────────────────────────────────────────────
# /me endpoint echo
# ──────────────────────────────────────────────────────────────────


class TestMeOrganizations:
    async def _login_user(self, client: AsyncClient, session, user: User) -> str:
        raw_key, key_hash, key_prefix = generate_api_key()
        session.add(ApiKey(user_id=user.id, key_hash=key_hash, key_prefix=key_prefix, name="test"))
        await session.commit()
        resp = await client.post(
            "/v1/dashboard/auth/login",
            json={"username": user.username, "api_key": raw_key},
        )
        assert resp.status_code == 200
        return raw_key

    async def test_me_organizations_and_permissions(self, client: AsyncClient, session):
        user = await _make_user(session, "me_org_manager")
        org = await _make_org(session, "Zeta Corp", "zeta-corp", creator=user)
        await _add_member(session, org, user, "manager")
        await self._login_user(client, session, user)

        resp = await client.get("/v1/dashboard/auth/me")
        assert resp.status_code == 200
        data = resp.json()

        assert data["organizations"] == [
            {"org_id": str(org.id), "name": "Zeta Corp", "role": "manager"}
        ]
        assert "org:manage" in data["permissions"]
        assert "overview:read:org" in data["permissions"]
        # platform permissions still present
        assert "agent:read:own" in data["permissions"]

    async def test_me_no_organizations(self, client: AsyncClient, session):
        user = await _make_user(session, "me_plain_user")
        await self._login_user(client, session, user)

        resp = await client.get("/v1/dashboard/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["organizations"] == []
        assert data["permissions"] == sorted(ROLE_PERMISSIONS["user"])

    async def test_me_member_read_only(self, client: AsyncClient, session):
        user = await _make_user(session, "me_org_member")
        org = await _make_org(session, "Eta Corp", "eta-corp", creator=user)
        await _add_member(session, org, user, "member")
        await self._login_user(client, session, user)

        resp = await client.get("/v1/dashboard/auth/me")
        data = resp.json()
        assert "overview:read:org" in data["permissions"]
        assert "org:manage" not in data["permissions"]
        assert data["organizations"] == [
            {"org_id": str(org.id), "name": "Eta Corp", "role": "member"}
        ]

    async def test_me_super_admin_keeps_global_permissions(self, client: AsyncClient, session):
        """super_admin /me echo must still contain every global permission."""
        user = await _make_user(session, "me_super_admin", role="super_admin")
        org = await _make_org(session, "Theta Corp", "theta-corp", creator=user)
        await _add_member(session, org, user, "manager")
        await self._login_user(client, session, user)

        resp = await client.get("/v1/dashboard/auth/me")
        data = resp.json()
        assert set(ROLE_PERMISSIONS["super_admin"]) <= set(data["permissions"])
        assert "org:manage" in data["permissions"]  # org union on top

    async def test_me_excludes_disabled_org(self, client: AsyncClient, session):
        user = await _make_user(session, "me_disabled_org_user")
        org = await _make_org(session, "Iota Corp", "iota-corp", creator=user)
        await _add_member(session, org, user, "manager")
        org.is_disabled = True
        await session.flush()
        await self._login_user(client, session, user)

        resp = await client.get("/v1/dashboard/auth/me")
        data = resp.json()
        assert data["organizations"] == []
        assert "org:manage" not in data["permissions"]


# ──────────────────────────────────────────────────────────────────
# Enterprise approval end-to-end
# ──────────────────────────────────────────────────────────────────


async def _submit_enterprise_request(client: AsyncClient, *, email: str, org: str | None) -> str:
    payload = {
        "applicant_name": "Enterprise User",
        "applicant_email": email,
        "requested_mode": "enterprise",
        "use_case": "Enterprise deployment",
        "terms_acknowledged": True,
    }
    if org is not None:
        payload["organization"] = org
    resp = await client.post("/v1/public/access-requests", json=payload)
    assert resp.status_code == 201
    return resp.json()["request_id"]


class TestEnterpriseApproval:
    async def test_approve_enterprise_provisions_org_not_admin(
        self, client: AsyncClient, session
    ):
        """Enterprise approval creates org + manager membership + org-backed
        scope, and leaves the platform role as 'user'."""
        await _login_super_admin(client, session)
        request_id = await _submit_enterprise_request(
            client, email="enterprise_org@example.com", org="Acme Corp"
        )

        resp = await client.post(
            f"/v1/dashboard/admin/access-requests/{request_id}/approve",
            headers=_csrf_headers(client),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["scope_id"] is not None
        assert data["org_id"] is not None

        # User stays 'user' — org authority is modeled by membership.
        user_result = await session.execute(
            select(User).where(User.username == "enterprise_org@example.com")
        )
        provisioned_user = user_result.scalar_one()
        assert provisioned_user.role == "user"

        # Organization created with a slug derived from the org name.
        org_result = await session.execute(
            select(Organization).where(Organization.id == uuid.UUID(data["org_id"]))
        )
        org = org_result.scalar_one()
        assert org.name == "Acme Corp"
        assert org.slug == "acme-corp"
        assert org.is_disabled is False

        # Applicant is the org manager.
        member_result = await session.execute(
            select(OrganizationMember).where(
                OrganizationMember.org_id == org.id,
                OrganizationMember.user_id == provisioned_user.id,
            )
        )
        member = member_result.scalar_one()
        assert member.role == "manager"

        # Enterprise scope is attached to the org.
        scope_result = await session.execute(
            select(NetworkScope).where(NetworkScope.user_id == provisioned_user.id)
        )
        scope = scope_result.scalar_one()
        assert scope.scope_type == "enterprise"
        assert scope.scope_name == "Acme Corp"
        assert scope.org_id == org.id
        assert str(scope.id) == data["scope_id"]

        # Resolved permissions now include org-domain permissions.
        perms = await resolve_user_permissions(session, provisioned_user.id)
        assert "org:manage" in perms
        assert "overview:read:org" in perms

    async def test_approve_enterprise_without_org_name_uses_email(
        self, client: AsyncClient, session
    ):
        await _login_super_admin(client, session)
        request_id = await _submit_enterprise_request(
            client, email="noorg2@example.com", org=None
        )

        resp = await client.post(
            f"/v1/dashboard/admin/access-requests/{request_id}/approve",
            headers=_csrf_headers(client),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["org_id"] is not None

        org_result = await session.execute(
            select(Organization).where(Organization.id == uuid.UUID(data["org_id"]))
        )
        org = org_result.scalar_one()
        assert org.slug == "noorg2-example-com"
        assert org.name == "noorg2@example.com"

        scope_result = await session.execute(
            select(NetworkScope).where(NetworkScope.org_id == org.id)
        )
        scope = scope_result.scalar_one()
        assert scope.scope_type == "enterprise"

    async def test_approve_enterprise_backfills_existing_scope(
        self, client: AsyncClient, session
    ):
        """A pre-existing enterprise scope for the applicant is backfilled
        with org_id instead of a duplicate scope being created."""
        await _login_super_admin(client, session)

        # Pre-existing user with an enterprise scope (legacy provisioning).
        existing_user = User(username="backfill@example.com")
        session.add(existing_user)
        await session.flush()
        legacy_scope = NetworkScope(
            user_id=existing_user.id,
            scope_name="Legacy Corp",
            scope_type="enterprise",
        )
        session.add(legacy_scope)
        await session.flush()

        request_id = await _submit_enterprise_request(
            client, email="backfill@example.com", org="Legacy Corp"
        )
        resp = await client.post(
            f"/v1/dashboard/admin/access-requests/{request_id}/approve",
            headers=_csrf_headers(client),
        )
        assert resp.status_code == 200
        data = resp.json()

        # No duplicate scope: the legacy one was attached to the new org.
        scope_result = await session.execute(
            select(NetworkScope).where(NetworkScope.user_id == existing_user.id)
        )
        scopes = list(scope_result.scalars().all())
        assert len(scopes) == 1
        assert scopes[0].id == legacy_scope.id
        assert scopes[0].org_id == uuid.UUID(data["org_id"])

    async def test_approve_enterprise_slug_collision_gets_unique_suffix(
        self, client: AsyncClient, session
    ):
        """A slug already taken by an org the applicant does not manage must
        not be reused — a new uniquely-suffixed org is created instead."""
        await _login_super_admin(client, session)

        # An org belonging to someone else.
        other_user = User(username="other@example.com")
        session.add(other_user)
        await session.flush()
        other_org = Organization(
            name="Acme Corp", slug="acme-corp", created_by_user_id=other_user.id
        )
        session.add(other_org)
        await session.flush()

        request_id = await _submit_enterprise_request(
            client, email="collide@example.com", org="Acme Corp"
        )
        resp = await client.post(
            f"/v1/dashboard/admin/access-requests/{request_id}/approve",
            headers=_csrf_headers(client),
        )
        assert resp.status_code == 200
        data = resp.json()

        new_org_result = await session.execute(
            select(Organization).where(Organization.id == uuid.UUID(data["org_id"]))
        )
        new_org = new_org_result.scalar_one()
        assert new_org.id != other_org.id
        assert new_org.slug == "acme-corp-2"

        # Applicant is a manager of the NEW org, not of the pre-existing one.
        member_result = await session.execute(
            select(OrganizationMember).where(
                OrganizationMember.user_id == uuid.UUID(data["user_id"])
            )
        )
        members = list(member_result.scalars().all())
        assert [m.org_id for m in members] == [new_org.id]

    async def test_disabling_org_after_approval_revokes_permissions(
        self, client: AsyncClient, session
    ):
        """Degradation path: disabling the organization removes the granted
        org-domain permissions."""
        await _login_super_admin(client, session)
        request_id = await _submit_enterprise_request(
            client, email="disablepath@example.com", org="Revoke Corp"
        )
        resp = await client.post(
            f"/v1/dashboard/admin/access-requests/{request_id}/approve",
            headers=_csrf_headers(client),
        )
        data = resp.json()
        user_id = uuid.UUID(data["user_id"])
        org_id = uuid.UUID(data["org_id"])

        perms = await resolve_user_permissions(session, user_id)
        assert "org:manage" in perms

        org_result = await session.execute(
            select(Organization).where(Organization.id == org_id)
        )
        org = org_result.scalar_one()
        org.is_disabled = True
        await session.flush()

        perms = await resolve_user_permissions(session, user_id)
        assert "org:manage" not in perms
        assert "overview:read:org" not in perms
        assert perms == sorted(ROLE_PERMISSIONS["user"])

    async def test_removing_membership_after_approval_revokes_permissions(
        self, client: AsyncClient, session
    ):
        """Degradation path: removing the manager membership revokes the
        org-domain permissions."""
        await _login_super_admin(client, session)
        request_id = await _submit_enterprise_request(
            client, email="removemember@example.com", org="Remove Corp"
        )
        resp = await client.post(
            f"/v1/dashboard/admin/access-requests/{request_id}/approve",
            headers=_csrf_headers(client),
        )
        data = resp.json()
        user_id = uuid.UUID(data["user_id"])

        assert "org:manage" in await resolve_user_permissions(session, user_id)

        member_result = await session.execute(
            select(OrganizationMember).where(
                OrganizationMember.user_id == user_id
            )
        )
        member = member_result.scalar_one()
        await session.delete(member)
        await session.flush()

        perms = await resolve_user_permissions(session, user_id)
        assert perms == sorted(ROLE_PERMISSIONS["user"])
