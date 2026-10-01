"""Organization management API — session-authenticated, CSRF-protected, audited.

Endpoints (prefix /v1/organizations):
  GET    /mine                          — list orgs the session user belongs to
  POST   /                              — super_admin creates an organization
  GET    /{org_id}                      — org detail (manager or super_admin)
  GET    /{org_id}/members              — list members (manager or super_admin)
  POST   /{org_id}/members              — add member (manager or super_admin)
  PATCH  /{org_id}/members/{user_id}    — change member role
  DELETE /{org_id}/members/{user_id}    — remove member
  DELETE /{org_id}                      — super_admin deletes org (cascade)

Authorization rules (fail-closed):
  * "manager" permission on an org = a membership row with role='manager'
    on THAT org, OR user-level super_admin. A plain 'member' role, a
    member of a different org, or a user with no membership at all is 403.
  * A disabled organization (is_disabled=True) refuses every
    org-scoped operation below with 403, including super_admin access —
    fail-closed per contract. Deletion of a disabled org is likewise 403.
  * Organization membership roles (manager/member) are separate from the
    user-level UserRole (user/admin/super_admin); super_admin is checked
    through rbac_service.has_permission(PERM_SUPER_ADMIN_WRITE) — no raw
    role-string comparisons in the router.

Data access style: every lookup is a primary-key session.get() plus ORM
relationship traversal (User.organizations / Organization.members /
OrganizationMember.user / .organization). No request-derived value ever
reaches a SQL where/filter clause or raw SQL text, so there is no
injection surface and nothing to parameterize by hand. Slug uniqueness
is enforced by the DB unique constraint (IntegrityError → 409); org
deletion relies on the organization_members FK ON DELETE CASCADE.
Member add takes a resolved user_id (UUID) rather than a username — see
the note in app/schemas/organizations.py.

Performance note: /mine and the member list use chained selectin eager
loads (memberships + related user/org rows in one extra SELECT each),
because async sessions cannot lazy-load 'select' relationships on
attribute access. Membership counts are typically small (single digits
per user, low tens per org).
"""
import uuid

from fastapi import APIRouter, Depends, status as http_status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_session
from app.dependencies.auth import CurrentSession
from app.dependencies.csrf import require_csrf
from app.dependencies.rbac import require_permission
from app.exceptions import DomainException
from app.models.organization import Organization, OrganizationMember
from app.models.user import User
from app.protocol.constants import ErrorCode
from app.schemas.organizations import (
    OrganizationCreateRequest,
    OrganizationListResponse,
    OrganizationMemberAdd,
    OrganizationMemberListResponse,
    OrganizationMemberResponse,
    OrganizationMemberUpdateRequest,
    OrganizationResponse,
)
from app.services.audit_service import write_audit
from app.services.rbac_service import PERM_SUPER_ADMIN_WRITE, has_permission

router = APIRouter(
    prefix="/v1/organizations",
    tags=["organizations"],
    dependencies=[Depends(require_csrf)],
)

# Organization membership roles (NOT the user-level UserRole).
ROLE_MANAGER = "manager"
ROLE_MEMBER = "member"


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

def _forbidden(message: str = "Insufficient permissions for this operation") -> None:
    raise DomainException(
        ErrorCode.INVALID_REQUEST,
        message,
        status_code=http_status.HTTP_403_FORBIDDEN,
    )


# Eager-load memberships together with each member's user row in one
# selectin pass: async sessions cannot lazy-load ('select') relationships
# on attribute access, and the member list needs the usernames anyway.
_ORG_EAGER_OPTIONS = [
    selectinload(Organization.members).selectinload(OrganizationMember.user),
]


async def _get_org_or_404(session: AsyncSession, org_id: uuid.UUID) -> Organization:
    # Primary-key lookup; memberships (and their users) eager-loaded.
    # populate_existing=True so cached instances (identity-map hits from
    # earlier in the same session) are refreshed together with the
    # eager options — otherwise 'members' may stay unloaded and lazy
    # access would raise MissingGreenlet on the async session.
    org = await session.get(
        Organization, org_id, options=_ORG_EAGER_OPTIONS, populate_existing=True
    )
    if org is None:
        raise DomainException(
            ErrorCode.RESOURCE_NOT_FOUND,
            "Organization not found.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )
    return org


def _find_membership(org: Organization, user_id: uuid.UUID) -> OrganizationMember | None:
    """In-memory scan of the org's loaded membership collection."""
    return next(
        (m for m in org.members if m.user_id == user_id),
        None,
    )


async def _load_org_for_manager_access(
    session: AsyncSession,
    org_id: uuid.UUID,
    user: User,
) -> tuple[Organization, OrganizationMember | None]:
    """Fetch the org and enforce fail-closed manager authorization.

    Raises 404 when the org does not exist, 403 when it is disabled,
    and 403 when the user is neither a manager of this org nor a
    super_admin. Returns (org, membership) — membership is None for a
    super_admin who is not a member.
    """
    org = await _get_org_or_404(session, org_id)

    # Fail-closed: a disabled org is unreachable through any org-scoped
    # endpoint, super_admin included.
    if org.is_disabled:
        _forbidden("Organization is disabled")

    membership = _find_membership(org, user.id)

    if has_permission(user, PERM_SUPER_ADMIN_WRITE):
        return org, membership
    if membership is not None and membership.role == ROLE_MANAGER:
        return org, membership

    _forbidden()


def _member_response(membership: OrganizationMember, username: str) -> OrganizationMemberResponse:
    return OrganizationMemberResponse(
        user_id=str(membership.user_id),
        username=username,
        role=membership.role,
        created_at=membership.created_at,
    )


# ──────────────────────────────────────────────────────────────────
# 1) GET /mine — organizations of the current session user
# ──────────────────────────────────────────────────────────────────

@router.get("/mine", response_model=OrganizationListResponse)
async def list_my_organizations(
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
):
    """Organizations the session user belongs to, with their membership role.

    Disabled organizations are still listed (with is_disabled=true):
    this is the user's own membership view, not org-scoped access.
    """
    # Primary-key lookup; User.organizations is selectin-loaded by the
    # model, and each membership's organization is eager-loaded here so
    # no lazy ('select') attribute access happens on the async session.
    user = await session.get(
        User,
        ds.user_id,
        options=[selectinload(User.organizations).selectinload(OrganizationMember.organization)],
        populate_existing=True,
    )
    if user is None:  # defensive: session was validated against this user
        raise DomainException(
            ErrorCode.RESOURCE_NOT_FOUND,
            "User not found.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )

    memberships = list(user.organizations)
    memberships.sort(key=lambda m: m.organization.created_at)

    return OrganizationListResponse(
        organizations=[
            OrganizationResponse(
                org_id=str(m.organization.id),
                name=m.organization.name,
                slug=m.organization.slug,
                role=m.role,
                is_disabled=m.organization.is_disabled,
                created_at=m.organization.created_at,
            )
            for m in memberships
        ]
    )


# ──────────────────────────────────────────────────────────────────
# 2) POST / — super_admin creates an organization
# ──────────────────────────────────────────────────────────────────

@router.post("", response_model=OrganizationResponse, status_code=http_status.HTTP_201_CREATED)
async def create_organization(
    body: OrganizationCreateRequest,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_permission(PERM_SUPER_ADMIN_WRITE)),
):
    """Create an organization (super_admin only).

    The creating super_admin is enrolled as 'manager' so the org is
    manageable without relying on the super_admin bypass, matching the
    0029 data-migration behavior for enterprise scopes. Slug uniqueness
    is enforced by the DB unique constraint below (409 on conflict).
    """
    org = Organization(
        name=body.name,
        slug=body.slug,
        created_by_user_id=ds.user_id,
        is_disabled=False,
    )
    # Append through the relationship so the unit of work wires the
    # membership's org_id as the org row is inserted (org.id is only
    # assigned at INSERT time) and org.members stays consistent.
    org.members.append(
        OrganizationMember(user_id=ds.user_id, role=ROLE_MANAGER)
    )
    session.add(org)

    try:
        await session.flush()
    except IntegrityError:
        # The unique constraint on organizations.slug is the
        # authoritative guard (also covers concurrent races).
        await session.rollback()
        raise DomainException(
            ErrorCode.INVALID_REQUEST,
            "Organization slug already exists.",
            status_code=http_status.HTTP_409_CONFLICT,
        )

    await write_audit(
        session,
        actor_type="user",
        actor_id=str(ds.user_id),
        action="organization.create",
        resource_type="organization",
        resource_id=str(org.id),
        details={
            "name": org.name,
            "slug": org.slug,
            "created_by_user_id": str(ds.user_id),
            "creator_role": ROLE_MANAGER,
        },
    )
    await session.commit()

    return OrganizationResponse(
        org_id=str(org.id),
        name=org.name,
        slug=org.slug,
        role=ROLE_MANAGER,
        is_disabled=org.is_disabled,
        created_at=org.created_at,
    )


# ──────────────────────────────────────────────────────────────────
# 3) GET /{org_id} — organization detail
# ──────────────────────────────────────────────────────────────────

@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    org_id: uuid.UUID,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
):
    """Organization detail. Manager of this org or super_admin only."""
    org, membership = await _load_org_for_manager_access(session, org_id, ds.user)

    return OrganizationResponse(
        org_id=str(org.id),
        name=org.name,
        slug=org.slug,
        role=membership.role if membership is not None else None,
        is_disabled=org.is_disabled,
        created_at=org.created_at,
    )


# ──────────────────────────────────────────────────────────────────
# 4) GET /{org_id}/members — list members
# ──────────────────────────────────────────────────────────────────

@router.get("/{org_id}/members", response_model=OrganizationMemberListResponse)
async def list_organization_members(
    org_id: uuid.UUID,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
):
    """List organization members. Manager of this org or super_admin only."""
    org, _ = await _load_org_for_manager_access(session, org_id, ds.user)

    # org.members is selectin-loaded with the org; usernames are read
    # through the membership→user relationship.
    members = list(org.members)
    members.sort(key=lambda m: m.created_at)

    return OrganizationMemberListResponse(
        members=[_member_response(m, m.user.username) for m in members]
    )


# ──────────────────────────────────────────────────────────────────
# 5) POST /{org_id}/members — add a member
# ──────────────────────────────────────────────────────────────────

@router.post(
    "/{org_id}/members",
    response_model=OrganizationMemberResponse,
    status_code=http_status.HTTP_201_CREATED,
)
async def add_organization_member(
    org_id: uuid.UUID,
    body: OrganizationMemberAdd,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
):
    """Add a member by user id. Manager of this org or super_admin only.

    Takes a resolved ``user_id`` (UUID) rather than a username — see the
    note in app/schemas/organizations.py for the tool limitation that
    rules out a username lookup inside the API.
    """
    org, _ = await _load_org_for_manager_access(session, org_id, ds.user)

    # Primary-key lookup for the target user.
    target = await session.get(User, body.user_id)
    if target is None:
        raise DomainException(
            ErrorCode.RESOURCE_NOT_FOUND,
            "User not found.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )

    existing = _find_membership(org, target.id)
    if existing is not None:
        raise DomainException(
            ErrorCode.INVALID_STATE,
            "User is already a member of this organization.",
            status_code=http_status.HTTP_409_CONFLICT,
        )

    # Append through the relationship: org_id is wired by the unit of
    # work and org.members stays consistent within the session.
    membership = OrganizationMember(user_id=target.id, role=body.role)
    org.members.append(membership)
    await session.flush()

    await write_audit(
        session,
        actor_type="user",
        actor_id=str(ds.user_id),
        action="organization.add_member",
        resource_type="organization_member",
        resource_id=str(membership.id),
        details={
            "org_id": str(org.id),
            "org_slug": org.slug,
            "username": target.username,
            "user_id": str(target.id),
            "role": body.role,
        },
    )
    await session.commit()

    return _member_response(membership, target.username)


# ──────────────────────────────────────────────────────────────────
# 6) PATCH /{org_id}/members/{user_id} — change a member's role
# ──────────────────────────────────────────────────────────────────

@router.patch("/{org_id}/members/{user_id}", response_model=OrganizationMemberResponse)
async def update_organization_member_role(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    body: OrganizationMemberUpdateRequest,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
):
    """Change a member's role (manager|member).

    Manager of this org or super_admin only. A no-op change (same role)
    is accepted and audited like any other attempt.
    """
    org, _ = await _load_org_for_manager_access(session, org_id, ds.user)

    membership = _find_membership(org, user_id)
    if membership is None:
        raise DomainException(
            ErrorCode.RESOURCE_NOT_FOUND,
            "Membership not found.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )

    previous_role = membership.role
    membership.role = body.role

    await write_audit(
        session,
        actor_type="user",
        actor_id=str(ds.user_id),
        action="organization.update_member_role",
        resource_type="organization_member",
        resource_id=str(membership.id),
        details={
            "org_id": str(org.id),
            "org_slug": org.slug,
            "user_id": str(user_id),
            "previous_role": previous_role,
            "new_role": body.role,
        },
    )
    await session.commit()

    # Username read through the membership→user relationship.
    return _member_response(membership, membership.user.username)


# ──────────────────────────────────────────────────────────────────
# 7) DELETE /{org_id}/members/{user_id} — remove a member
# ──────────────────────────────────────────────────────────────────

@router.delete("/{org_id}/members/{user_id}")
async def remove_organization_member(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
):
    """Remove a member (the org degrades to fewer members).

    Manager of this org or super_admin only.
    """
    org, _ = await _load_org_for_manager_access(session, org_id, ds.user)

    membership = _find_membership(org, user_id)
    if membership is None:
        raise DomainException(
            ErrorCode.RESOURCE_NOT_FOUND,
            "Membership not found.",
            status_code=http_status.HTTP_404_NOT_FOUND,
        )

    removed_role = membership.role
    membership_id = membership.id  # captured before the row is deleted
    await session.delete(membership)

    await write_audit(
        session,
        actor_type="user",
        actor_id=str(ds.user_id),
        action="organization.remove_member",
        resource_type="organization_member",
        resource_id=str(membership_id),
        details={
            "org_id": str(org.id),
            "org_slug": org.slug,
            "user_id": str(user_id),
            "removed_role": removed_role,
        },
    )
    await session.commit()

    return {"org_id": str(org.id), "user_id": str(user_id), "removed": True}


# ──────────────────────────────────────────────────────────────────
# 8) DELETE /{org_id} — delete an organization
# ──────────────────────────────────────────────────────────────────

@router.delete("/{org_id}")
async def delete_organization(
    org_id: uuid.UUID,
    ds: CurrentSession,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_permission(PERM_SUPER_ADMIN_WRITE)),
):
    """Delete an organization and cascade its memberships (super_admin only).

    Fail-closed: a disabled organization is not deletable through this
    endpoint (403).
    """
    org, _ = await _load_org_for_manager_access(session, org_id, ds.user)

    # org.members is already loaded (selectin); count before deletion.
    member_count = len(org.members)

    # ORM delete: the organization_members FK ON DELETE CASCADE removes
    # the membership rows along with the org row.
    await session.delete(org)

    await write_audit(
        session,
        actor_type="user",
        actor_id=str(ds.user_id),
        action="organization.delete",
        resource_type="organization",
        resource_id=str(org.id),
        details={
            "name": org.name,
            "slug": org.slug,
            "cascaded_members": member_count,
        },
    )
    await session.commit()

    return {"org_id": str(org.id), "deleted": True, "cascaded_members": member_count}
