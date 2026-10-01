"""Organization management API tests.

Covers: /mine listing, org creation (super_admin), detail read, member
list/add/update/remove, org deletion with cascade — plus
authorization boundaries (non-member, other-org member, plain member
role), CSRF enforcement, audit writes, and the disabled-org 403 rule.

Test data is constructed with session.add() (no User.username queries —
see the note in app/routers/organizations.py docstring), and audit
assertions mirror the pattern used by tests/test_phase_web_5_admin_api.py.
"""
import hashlib
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import ApiKey
from app.models.audit_log import AuditLog
from app.models.organization import Organization, OrganizationMember
from app.models.user import User, UserRole


# ──────────────────────────────────────────────────────────────────
# Fixtures and helpers
# ──────────────────────────────────────────────────────────────────

async def make_user(
    session: AsyncSession,
    role: str = UserRole.USER.value,
    prefix: str = "u",
) -> tuple[User, str]:
    """Create a user + API key. Returns (user, plain_api_key)."""
    plain = f"key-{prefix}-{uuid.uuid4().hex}"
    user = User(
        id=uuid.uuid4(),
        username=f"{prefix}-{uuid.uuid4().hex[:8]}",
        role=role,
    )
    session.add(user)
    await session.flush()

    session.add(
        ApiKey(
            id=uuid.uuid4(),
            user_id=user.id,
            key_hash=hashlib.sha256(plain.encode()).hexdigest(),
            key_prefix="ak_t",
            name="test-key",
        )
    )
    await session.flush()
    return user, plain


@pytest.fixture
async def super_admin(session: AsyncSession):
    return await make_user(session, role=UserRole.SUPER_ADMIN.value, prefix="sa")


@pytest.fixture
async def plain_user(session: AsyncSession):
    return await make_user(session, role=UserRole.USER.value, prefix="plain")


async def login(client: AsyncClient, username: str, api_key: str):
    """Login and set session + CSRF cookies on the client."""
    return await client.post(
        "/v1/dashboard/auth/login",
        json={"username": username, "api_key": api_key},
    )


def csrf_headers(client: AsyncClient) -> dict:
    csrf = client.cookies.get("agentnet_csrf")
    return {"X-CSRF-Token": csrf} if csrf else {}


def second_client(app):
    """A fresh client for acting as a second user in the same test."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


async def make_org(
    session: AsyncSession,
    *,
    name: str,
    slug: str,
    members: list[tuple[User, str]],
    is_disabled: bool = False,
) -> Organization:
    """Create an organization with the given (user, role) memberships."""
    org = Organization(
        id=uuid.uuid4(),
        name=name,
        slug=slug,
        created_by_user_id=members[0][0].id if members else None,
        is_disabled=is_disabled,
    )
    session.add(org)
    await session.flush()
    for user, role in members:
        session.add(
            OrganizationMember(
                id=uuid.uuid4(),
                org_id=org.id,
                user_id=user.id,
                role=role,
            )
        )
    await session.flush()
    return org


async def get_audit_entries(
    session: AsyncSession,
    action: str,
    actor_id: str,
) -> list[AuditLog]:
    result = await session.execute(
        select(AuditLog).where(
            AuditLog.action == action,
            AuditLog.actor_id == actor_id,
        )
    )
    return list(result.scalars().all())


# ──────────────────────────────────────────────────────────────────
# 1) GET /mine
# ──────────────────────────────────────────────────────────────────

class TestMine:
    async def test_mine_lists_own_orgs_with_roles(
        self, client: AsyncClient, session: AsyncSession, plain_user, super_admin
    ):
        user, plain_key = plain_user
        sa, sa_key = super_admin
        org_a = await make_org(session, name="Org A", slug="org-a", members=[(user, "manager")])
        await make_org(session, name="Org B", slug="org-b", members=[(user, "member"), (sa, "manager")])

        resp = await login(client, user.username, plain_key)
        assert resp.status_code == 200
        resp = await client.get("/v1/organizations/mine")
        assert resp.status_code == 200

        orgs = resp.json()["organizations"]
        by_slug = {o["slug"]: o for o in orgs}
        assert set(by_slug) == {"org-a", "org-b"}
        assert by_slug["org-a"]["role"] == "manager"
        assert by_slug["org-b"]["role"] == "member"
        assert by_slug["org-a"]["name"] == "Org A"
        assert by_slug["org-a"]["org_id"] == str(org_a.id)
        assert by_slug["org-a"]["is_disabled"] is False

    async def test_mine_empty_for_user_without_orgs(
        self, client: AsyncClient, plain_user
    ):
        user, plain_key = plain_user
        await login(client, user.username, plain_key)
        resp = await client.get("/v1/organizations/mine")
        assert resp.status_code == 200
        assert resp.json()["organizations"] == []

    async def test_mine_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/v1/organizations/mine")
        assert resp.status_code == 401


# ──────────────────────────────────────────────────────────────────
# 2) POST / — create organization (super_admin)
# ──────────────────────────────────────────────────────────────────

class TestCreateOrganization:
    async def test_super_admin_creates_org(
        self, client: AsyncClient, session: AsyncSession, super_admin
    ):
        sa, sa_key = super_admin
        await login(client, sa.username, sa_key)

        resp = await client.post(
            "/v1/organizations",
            json={"name": "Acme", "slug": "acme"},
            headers=csrf_headers(client),
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["name"] == "Acme"
        assert body["slug"] == "acme"
        assert body["role"] == "manager"
        assert body["is_disabled"] is False
        org_id = body["org_id"]

        # Creator enrolled as manager
        created = await session.get(Organization, uuid.UUID(org_id))
        assert created is not None
        assert created.created_by_user_id == sa.id
        assert [(m.user_id, m.role) for m in created.members] == [(sa.id, "manager")]

        # Audit written
        logs = await get_audit_entries(session, "organization.create", str(sa.id))
        assert len(logs) == 1
        assert logs[0].resource_type == "organization"
        assert logs[0].resource_id == org_id
        assert logs[0].details["slug"] == "acme"

        # Visible in /mine
        resp = await client.get("/v1/organizations/mine")
        assert resp.status_code == 200
        assert any(o["slug"] == "acme" and o["role"] == "manager" for o in resp.json()["organizations"])

    async def test_admin_cannot_create(self, client: AsyncClient, session: AsyncSession):
        admin, admin_key = await make_user(session, role=UserRole.ADMIN.value, prefix="adm")
        await login(client, admin.username, admin_key)
        resp = await client.post(
            "/v1/organizations",
            json={"name": "X", "slug": "x"},
            headers=csrf_headers(client),
        )
        assert resp.status_code == 403

    async def test_regular_user_cannot_create(self, client: AsyncClient, plain_user):
        user, plain_key = plain_user
        await login(client, user.username, plain_key)
        resp = await client.post(
            "/v1/organizations",
            json={"name": "X", "slug": "x"},
            headers=csrf_headers(client),
        )
        assert resp.status_code == 403

    async def test_duplicate_slug_conflict(
        self, client: AsyncClient, session: AsyncSession, super_admin
    ):
        sa, sa_key = super_admin
        await make_org(session, name="Taken", slug="taken", members=[(sa, "manager")])
        await login(client, sa.username, sa_key)

        resp = await client.post(
            "/v1/organizations",
            json={"name": "Other", "slug": "taken"},
            headers=csrf_headers(client),
        )
        assert resp.status_code == 409

    async def test_invalid_slug_rejected(self, client: AsyncClient, super_admin):
        sa, sa_key = super_admin
        await login(client, sa.username, sa_key)
        resp = await client.post(
            "/v1/organizations",
            json={"name": "Bad", "slug": "Not_A_Slug"},
            headers=csrf_headers(client),
        )
        assert resp.status_code == 422

    async def test_create_requires_csrf(self, client: AsyncClient, super_admin):
        sa, sa_key = super_admin
        await login(client, sa.username, sa_key)
        resp = await client.post(
            "/v1/organizations",
            json={"name": "NoCsrf", "slug": "no-csrf"},
            # no X-CSRF-Token header
        )
        assert resp.status_code == 403

    async def test_create_requires_session(self, client: AsyncClient):
        resp = await client.post(
            "/v1/organizations",
            json={"name": "Anon", "slug": "anon"},
            headers={"X-CSRF-Token": "anything"},
        )
        assert resp.status_code == 401


# ──────────────────────────────────────────────────────────────────
# 3) GET /{org_id} — detail
# ──────────────────────────────────────────────────────────────────

class TestGetOrganizationDetail:
    async def test_manager_reads_detail(
        self, client: AsyncClient, session: AsyncSession, plain_user
    ):
        user, plain_key = plain_user
        org = await make_org(session, name="Alpha", slug="alpha", members=[(user, "manager")])
        await login(client, user.username, plain_key)

        resp = await client.get(f"/v1/organizations/{org.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["org_id"] == str(org.id)
        assert body["name"] == "Alpha"
        assert body["slug"] == "alpha"
        assert body["role"] == "manager"

    async def test_super_admin_reads_org_they_are_not_in(
        self, client: AsyncClient, session: AsyncSession, super_admin, plain_user
    ):
        sa, sa_key = super_admin
        user, _ = plain_user
        org = await make_org(session, name="Beta", slug="beta", members=[(user, "manager")])
        await login(client, sa.username, sa_key)

        resp = await client.get(f"/v1/organizations/{org.id}")
        assert resp.status_code == 200
        assert resp.json()["role"] is None

    async def test_plain_member_forbidden(
        self, client: AsyncClient, session: AsyncSession, plain_user
    ):
        user, plain_key = plain_user
        org = await make_org(session, name="Gamma", slug="gamma", members=[(user, "member")])
        await login(client, user.username, plain_key)
        resp = await client.get(f"/v1/organizations/{org.id}")
        assert resp.status_code == 403

    async def test_non_member_forbidden(
        self, client: AsyncClient, session: AsyncSession, plain_user, super_admin
    ):
        sa, _ = super_admin
        user, plain_key = plain_user
        org = await make_org(session, name="Delta", slug="delta", members=[(sa, "manager")])
        await login(client, user.username, plain_key)
        resp = await client.get(f"/v1/organizations/{org.id}")
        assert resp.status_code == 403

    async def test_manager_of_other_org_forbidden(
        self, client: AsyncClient, session: AsyncSession, plain_user, super_admin
    ):
        sa, _ = super_admin
        user, plain_key = plain_user
        org_a = await make_org(session, name="A", slug="spa-a", members=[(sa, "manager")])
        await make_org(session, name="B", slug="spa-b", members=[(user, "manager")])
        await login(client, user.username, plain_key)
        resp = await client.get(f"/v1/organizations/{org_a.id}")
        assert resp.status_code == 403

    async def test_unknown_org_not_found(self, client: AsyncClient, plain_user):
        user, plain_key = plain_user
        await login(client, user.username, plain_key)
        resp = await client.get(f"/v1/organizations/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_disabled_org_forbidden(
        self, client: AsyncClient, session: AsyncSession, plain_user, super_admin
    ):
        sa, sa_key = super_admin
        user, plain_key = plain_user
        org = await make_org(
            session, name="Off", slug="off", members=[(user, "manager")], is_disabled=True
        )
        await login(client, user.username, plain_key)
        resp = await client.get(f"/v1/organizations/{org.id}")
        assert resp.status_code == 403

        # super_admin is also refused on a disabled org (fail-closed)
        await login(client, sa.username, sa_key)
        resp = await client.get(f"/v1/organizations/{org.id}")
        assert resp.status_code == 403


# ──────────────────────────────────────────────────────────────────
# 4) GET /{org_id}/members
# ──────────────────────────────────────────────────────────────────

class TestListMembers:
    async def test_manager_lists_members(
        self, client: AsyncClient, session: AsyncSession, plain_user, super_admin
    ):
        sa, _ = super_admin
        user, plain_key = plain_user
        org = await make_org(
            session,
            name="Members",
            slug="members",
            members=[(user, "manager"), (sa, "member")],
        )
        await login(client, user.username, plain_key)

        resp = await client.get(f"/v1/organizations/{org.id}/members")
        assert resp.status_code == 200
        members = resp.json()["members"]
        assert len(members) == 2
        by_user = {m["user_id"]: m for m in members}
        assert by_user[str(user.id)]["role"] == "manager"
        assert by_user[str(user.id)]["username"] == user.username
        assert by_user[str(sa.id)]["role"] == "member"

    async def test_super_admin_lists_members(
        self, client: AsyncClient, session: AsyncSession, super_admin, plain_user
    ):
        sa, sa_key = super_admin
        user, _ = plain_user
        org = await make_org(session, name="S", slug="member-sa", members=[(user, "manager")])
        await login(client, sa.username, sa_key)
        resp = await client.get(f"/v1/organizations/{org.id}/members")
        assert resp.status_code == 200
        assert len(resp.json()["members"]) == 1

    async def test_plain_member_forbidden(
        self, client: AsyncClient, session: AsyncSession, plain_user, super_admin
    ):
        sa, _ = super_admin
        user, plain_key = plain_user
        org = await make_org(
            session, name="P", slug="member-p", members=[(sa, "manager"), (user, "member")]
        )
        await login(client, user.username, plain_key)
        resp = await client.get(f"/v1/organizations/{org.id}/members")
        assert resp.status_code == 403

    async def test_non_member_forbidden(
        self, client: AsyncClient, session: AsyncSession, plain_user, super_admin
    ):
        sa, _ = super_admin
        user, plain_key = plain_user
        org = await make_org(session, name="N", slug="member-n", members=[(sa, "manager")])
        await login(client, user.username, plain_key)
        resp = await client.get(f"/v1/organizations/{org.id}/members")
        assert resp.status_code == 403

    async def test_disabled_org_forbidden(
        self, client: AsyncClient, session: AsyncSession, plain_user
    ):
        user, plain_key = plain_user
        org = await make_org(
            session, name="D", slug="member-d", members=[(user, "manager")], is_disabled=True
        )
        await login(client, user.username, plain_key)
        resp = await client.get(f"/v1/organizations/{org.id}/members")
        assert resp.status_code == 403


# ──────────────────────────────────────────────────────────────────
# 5) POST /{org_id}/members
# ──────────────────────────────────────────────────────────────────

class TestAddMember:
    async def test_manager_adds_member(
        self, app, client: AsyncClient, session: AsyncSession, plain_user
    ):
        manager, manager_key = plain_user
        newcomer, newcomer_key = await make_user(session, prefix="new")
        org = await make_org(session, name="Add", slug="add", members=[(manager, "manager")])
        await login(client, manager.username, manager_key)

        resp = await client.post(
            f"/v1/organizations/{org.id}/members",
            json={"user_id": str(newcomer.id), "role": "member"},
            headers=csrf_headers(client),
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["user_id"] == str(newcomer.id)
        assert body["username"] == newcomer.username
        assert body["role"] == "member"

        # Member list includes the newcomer
        resp = await client.get(f"/v1/organizations/{org.id}/members")
        assert resp.status_code == 200
        assert any(m["user_id"] == str(newcomer.id) for m in resp.json()["members"])

        # Audit written
        logs = await get_audit_entries(session, "organization.add_member", str(manager.id))
        assert len(logs) == 1
        assert logs[0].details["username"] == newcomer.username
        assert logs[0].details["role"] == "member"

        # The newcomer can now act on the org (member-role read is 403,
        # but the membership exists — verify via /mine)
        async with second_client(app) as c2:
            resp = await login(c2, newcomer.username, newcomer_key)
            assert resp.status_code == 200
            resp = await c2.get("/v1/organizations/mine")
            assert resp.status_code == 200
            assert any(o["org_id"] == str(org.id) and o["role"] == "member" for o in resp.json()["organizations"])

    async def test_super_admin_adds_manager(
        self, client: AsyncClient, session: AsyncSession, super_admin, plain_user
    ):
        sa, sa_key = super_admin
        user, _ = plain_user
        org = await make_org(session, name="Add2", slug="add2", members=[(sa, "manager")])
        await login(client, sa.username, sa_key)
        resp = await client.post(
            f"/v1/organizations/{org.id}/members",
            json={"user_id": str(user.id), "role": "manager"},
            headers=csrf_headers(client),
        )
        assert resp.status_code == 201
        assert resp.json()["role"] == "manager"

    async def test_plain_member_cannot_add(
        self, client: AsyncClient, session: AsyncSession, plain_user
    ):
        member_a, key_a = plain_user
        member_b, _ = await make_user(session, prefix="mb")
        org = await make_org(
            session, name="Add3", slug="add3", members=[(member_a, "member")]
        )
        await login(client, member_a.username, key_a)
        resp = await client.post(
            f"/v1/organizations/{org.id}/members",
            json={"user_id": str(member_b.id), "role": "member"},
            headers=csrf_headers(client),
        )
        assert resp.status_code == 403

    async def test_non_member_cannot_add(
        self, client: AsyncClient, session: AsyncSession, plain_user, super_admin
    ):
        sa, _ = super_admin
        user, plain_key = plain_user
        member_b, _ = await make_user(session, prefix="mb2")
        org = await make_org(session, name="Add4", slug="add4", members=[(sa, "manager")])
        await login(client, user.username, plain_key)
        resp = await client.post(
            f"/v1/organizations/{org.id}/members",
            json={"user_id": str(member_b.id), "role": "member"},
            headers=csrf_headers(client),
        )
        assert resp.status_code == 403

    async def test_add_unknown_user_not_found(
        self, client: AsyncClient, session: AsyncSession, plain_user
    ):
        manager, key = plain_user
        org = await make_org(session, name="Add5", slug="add5", members=[(manager, "manager")])
        await login(client, manager.username, key)
        resp = await client.post(
            f"/v1/organizations/{org.id}/members",
            json={"user_id": str(uuid.uuid4()), "role": "member"},
            headers=csrf_headers(client),
        )
        assert resp.status_code == 404

    async def test_add_existing_member_conflict(
        self, client: AsyncClient, session: AsyncSession, plain_user
    ):
        manager, key = plain_user
        org = await make_org(
            session, name="Add6", slug="add6", members=[(manager, "manager")]
        )
        await login(client, manager.username, key)
        resp = await client.post(
            f"/v1/organizations/{org.id}/members",
            json={"user_id": str(manager.id), "role": "member"},
            headers=csrf_headers(client),
        )
        assert resp.status_code == 409

    async def test_invalid_role_rejected(self, client: AsyncClient, session: AsyncSession, plain_user):
        manager, key = plain_user
        newcomer, _ = await make_user(session, prefix="new2")
        org = await make_org(session, name="Add7", slug="add7", members=[(manager, "manager")])
        await login(client, manager.username, key)
        resp = await client.post(
            f"/v1/organizations/{org.id}/members",
            json={"user_id": str(newcomer.id), "role": "owner"},
            headers=csrf_headers(client),
        )
        assert resp.status_code == 422

    async def test_add_requires_csrf(self, client: AsyncClient, session: AsyncSession, plain_user):
        manager, key = plain_user
        newcomer, _ = await make_user(session, prefix="new3")
        org = await make_org(session, name="Add8", slug="add8", members=[(manager, "manager")])
        await login(client, manager.username, key)
        resp = await client.post(
            f"/v1/organizations/{org.id}/members",
            json={"user_id": str(newcomer.id), "role": "member"},
            # no X-CSRF-Token header
        )
        assert resp.status_code == 403

    async def test_disabled_org_forbidden(
        self, client: AsyncClient, session: AsyncSession, plain_user
    ):
        manager, key = plain_user
        newcomer, _ = await make_user(session, prefix="new4")
        org = await make_org(
            session, name="Add9", slug="add9", members=[(manager, "manager")], is_disabled=True
        )
        await login(client, manager.username, key)
        resp = await client.post(
            f"/v1/organizations/{org.id}/members",
            json={"user_id": str(newcomer.id), "role": "member"},
            headers=csrf_headers(client),
        )
        assert resp.status_code == 403


# ──────────────────────────────────────────────────────────────────
# 6) PATCH /{org_id}/members/{user_id}
# ──────────────────────────────────────────────────────────────────

class TestUpdateMemberRole:
    async def test_manager_promotes_member(
        self, app, client: AsyncClient, session: AsyncSession, plain_user
    ):
        manager, key = plain_user
        member, member_key = await make_user(session, prefix="mem")
        org = await make_org(
            session,
            name="Promo",
            slug="promo",
            members=[(manager, "manager"), (member, "member")],
        )
        await login(client, manager.username, key)

        resp = await client.patch(
            f"/v1/organizations/{org.id}/members/{member.id}",
            json={"role": "manager"},
            headers=csrf_headers(client),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["role"] == "manager"

        # Audit written
        logs = await get_audit_entries(session, "organization.update_member_role", str(manager.id))
        assert len(logs) == 1
        assert logs[0].details["previous_role"] == "member"
        assert logs[0].details["new_role"] == "manager"

        # The promoted member now has manager access
        async with second_client(app) as c2:
            await login(c2, member.username, member_key)
            resp = await c2.get(f"/v1/organizations/{org.id}")
            assert resp.status_code == 200
            assert resp.json()["role"] == "manager"

    async def test_demote_manager_to_member(
        self, app, client: AsyncClient, session: AsyncSession, plain_user
    ):
        manager, key = plain_user
        other, other_key = await make_user(session, prefix="dem")
        org = await make_org(
            session,
            name="Demote",
            slug="demote",
            members=[(manager, "manager"), (other, "manager")],
        )
        await login(client, manager.username, key)
        resp = await client.patch(
            f"/v1/organizations/{org.id}/members/{other.id}",
            json={"role": "member"},
            headers=csrf_headers(client),
        )
        assert resp.status_code == 200

        async with second_client(app) as c2:
            await login(c2, other.username, other_key)
            resp = await c2.get(f"/v1/organizations/{org.id}")
            assert resp.status_code == 403

    async def test_plain_member_cannot_promote(
        self, client: AsyncClient, session: AsyncSession, plain_user
    ):
        member_a, key_a = plain_user
        member_b, _ = await make_user(session, prefix="mem2")
        org = await make_org(
            session, name="P2", slug="promo2", members=[(member_a, "member"), (member_b, "member")]
        )
        await login(client, member_a.username, key_a)
        resp = await client.patch(
            f"/v1/organizations/{org.id}/members/{member_b.id}",
            json={"role": "manager"},
            headers=csrf_headers(client),
        )
        assert resp.status_code == 403

    async def test_patch_non_member_target_not_found(
        self, client: AsyncClient, session: AsyncSession, plain_user
    ):
        manager, key = plain_user
        stranger, _ = await make_user(session, prefix="stranger")
        org = await make_org(session, name="P3", slug="promo3", members=[(manager, "manager")])
        await login(client, manager.username, key)
        resp = await client.patch(
            f"/v1/organizations/{org.id}/members/{stranger.id}",
            json={"role": "manager"},
            headers=csrf_headers(client),
        )
        assert resp.status_code == 404

    async def test_disabled_org_forbidden(
        self, client: AsyncClient, session: AsyncSession, plain_user
    ):
        manager, key = plain_user
        member, _ = await make_user(session, prefix="mem3")
        org = await make_org(
            session,
            name="P4",
            slug="promo4",
            members=[(manager, "manager"), (member, "member")],
            is_disabled=True,
        )
        await login(client, manager.username, key)
        resp = await client.patch(
            f"/v1/organizations/{org.id}/members/{member.id}",
            json={"role": "manager"},
            headers=csrf_headers(client),
        )
        assert resp.status_code == 403


# ──────────────────────────────────────────────────────────────────
# 7) DELETE /{org_id}/members/{user_id}
# ──────────────────────────────────────────────────────────────────

class TestRemoveMember:
    async def test_manager_removes_member(
        self, app, client: AsyncClient, session: AsyncSession, plain_user
    ):
        manager, key = plain_user
        member, member_key = await make_user(session, prefix="rm")
        org = await make_org(
            session,
            name="Rm",
            slug="remove",
            members=[(manager, "manager"), (member, "member")],
        )
        await login(client, manager.username, key)

        resp = await client.delete(
            f"/v1/organizations/{org.id}/members/{member.id}",
            headers=csrf_headers(client),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["removed"] is True

        # Member list no longer includes them
        resp = await client.get(f"/v1/organizations/{org.id}/members")
        assert resp.status_code == 200
        assert all(m["user_id"] != str(member.id) for m in resp.json()["members"])

        # Audit written
        logs = await get_audit_entries(session, "organization.remove_member", str(manager.id))
        assert len(logs) == 1
        assert logs[0].details["removed_role"] == "member"

        # The removed user loses access
        async with second_client(app) as c2:
            await login(c2, member.username, member_key)
            resp = await c2.get(f"/v1/organizations/{org.id}")
            assert resp.status_code == 403

    async def test_manager_removes_other_manager(self, client: AsyncClient, session: AsyncSession, plain_user):
        manager, key = plain_user
        other_mgr, _ = await make_user(session, prefix="rm2")
        org = await make_org(
            session,
            name="Rm2",
            slug="remove2",
            members=[(manager, "manager"), (other_mgr, "manager")],
        )
        await login(client, manager.username, key)
        resp = await client.delete(
            f"/v1/organizations/{org.id}/members/{other_mgr.id}",
            headers=csrf_headers(client),
        )
        assert resp.status_code == 200

    async def test_plain_member_cannot_remove(
        self, client: AsyncClient, session: AsyncSession, plain_user
    ):
        member_a, key_a = plain_user
        member_b, _ = await make_user(session, prefix="rm3")
        org = await make_org(
            session, name="Rm3", slug="remove3", members=[(member_a, "member"), (member_b, "member")]
        )
        await login(client, member_a.username, key_a)
        resp = await client.delete(
            f"/v1/organizations/{org.id}/members/{member_b.id}",
            headers=csrf_headers(client),
        )
        assert resp.status_code == 403

    async def test_remove_non_member_target_not_found(
        self, client: AsyncClient, session: AsyncSession, plain_user
    ):
        manager, key = plain_user
        stranger, _ = await make_user(session, prefix="rm4")
        org = await make_org(session, name="Rm4", slug="remove4", members=[(manager, "manager")])
        await login(client, manager.username, key)
        resp = await client.delete(
            f"/v1/organizations/{org.id}/members/{stranger.id}",
            headers=csrf_headers(client),
        )
        assert resp.status_code == 404

    async def test_remove_requires_csrf(self, client: AsyncClient, session: AsyncSession, plain_user):
        manager, key = plain_user
        member, _ = await make_user(session, prefix="rm5")
        org = await make_org(
            session, name="Rm5", slug="remove5", members=[(manager, "manager"), (member, "member")]
        )
        await login(client, manager.username, key)
        resp = await client.delete(f"/v1/organizations/{org.id}/members/{member.id}")
        assert resp.status_code == 403

    async def test_disabled_org_forbidden(
        self, client: AsyncClient, session: AsyncSession, plain_user
    ):
        manager, key = plain_user
        member, _ = await make_user(session, prefix="rm6")
        org = await make_org(
            session,
            name="Rm6",
            slug="remove6",
            members=[(manager, "manager"), (member, "member")],
            is_disabled=True,
        )
        await login(client, manager.username, key)
        resp = await client.delete(
            f"/v1/organizations/{org.id}/members/{member.id}",
            headers=csrf_headers(client),
        )
        assert resp.status_code == 403


# ──────────────────────────────────────────────────────────────────
# 8) DELETE /{org_id}
# ──────────────────────────────────────────────────────────────────

class TestDeleteOrganization:
    async def test_super_admin_deletes_org_with_cascade(
        self, client: AsyncClient, session: AsyncSession, super_admin
    ):
        sa, sa_key = super_admin
        member, _ = await make_user(session, prefix="del")
        org = await make_org(
            session,
            name="Del",
            slug="delete",
            members=[(sa, "manager"), (member, "member")],
        )
        await session.refresh(org, ["members"])  # load the collection on the async session
        membership_ids = [m.id for m in org.members]

        await login(client, sa.username, sa_key)
        resp = await client.delete(
            f"/v1/organizations/{org.id}",
            headers=csrf_headers(client),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["deleted"] is True
        assert body["cascaded_members"] == 2

        # Org gone
        resp = await client.get(f"/v1/organizations/{org.id}")
        assert resp.status_code == 404

        # Compose the actor id before expiring: attribute access on an
        # expired object triggers a sync refresh, which the async
        # session cannot do (MissingGreenlet).
        sa_id_str = str(sa.id)

        # Membership rows cascaded away (PK lookups after expiry)
        session.expire_all()
        assert await session.get(Organization, org.id) is None
        for mid in membership_ids:
            assert await session.get(OrganizationMember, mid) is None

        # Audit written
        logs = await get_audit_entries(session, "organization.delete", sa_id_str)
        assert len(logs) == 1
        assert logs[0].details["cascaded_members"] == 2

    async def test_manager_cannot_delete(
        self, client: AsyncClient, session: AsyncSession, plain_user
    ):
        manager, key = plain_user
        org = await make_org(session, name="NoDel", slug="no-delete", members=[(manager, "manager")])
        await login(client, manager.username, key)
        resp = await client.delete(f"/v1/organizations/{org.id}", headers=csrf_headers(client))
        assert resp.status_code == 403
        # Org still exists
        assert await session.get(Organization, org.id) is not None

    async def test_regular_user_cannot_delete(
        self, client: AsyncClient, session: AsyncSession, plain_user, super_admin
    ):
        sa, _ = super_admin
        user, key = plain_user
        org = await make_org(session, name="NoDel2", slug="no-delete2", members=[(sa, "manager")])
        await login(client, user.username, key)
        resp = await client.delete(f"/v1/organizations/{org.id}", headers=csrf_headers(client))
        assert resp.status_code == 403

    async def test_disabled_org_not_deletable(
        self, client: AsyncClient, session: AsyncSession, super_admin
    ):
        sa, sa_key = super_admin
        org = await make_org(
            session, name="DisDel", slug="dis-delete", members=[(sa, "manager")], is_disabled=True
        )
        await login(client, sa.username, sa_key)
        resp = await client.delete(f"/v1/organizations/{org.id}", headers=csrf_headers(client))
        assert resp.status_code == 403
        # Org still exists (disabled but not deleted)
        assert await session.get(Organization, org.id) is not None

    async def test_delete_requires_csrf(self, client: AsyncClient, session: AsyncSession, super_admin):
        sa, sa_key = super_admin
        org = await make_org(session, name="CsrfDel", slug="csrf-delete", members=[(sa, "manager")])
        await login(client, sa.username, sa_key)
        resp = await client.delete(f"/v1/organizations/{org.id}")
        assert resp.status_code == 403
