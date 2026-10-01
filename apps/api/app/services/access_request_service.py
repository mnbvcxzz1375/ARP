"""Business logic for public access requests -- fail-closed, no mock success."""
from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DomainException
from app.models.access_request import AccessRequest
from app.models.network_scope import NetworkScope
from app.models.organization import Organization, OrganizationMember
from app.models.user import User
from app.protocol.constants import ErrorCode
from app.services.audit_service import write_audit
from app.services.auth import get_or_create_user, create_api_key_for_user


async def create_access_request(
    session: AsyncSession,
    *,
    applicant_name: str,
    applicant_email: str,
    requested_mode: str,
    use_case: str,
    terms_acknowledged: bool,
    organization: str | None = None,
    request_ip: str | None = None,
) -> AccessRequest:
    """Persist a new access request. Raises on duplicate pending or missing terms."""
    if not terms_acknowledged:
        raise DomainException(
            ErrorCode.INVALID_REQUEST,
            "Terms must be acknowledged to submit a request.",
            status_code=400,
        )

    # Prevent duplicate pending requests from same email for same mode.
    # This check is advisory; the partial unique index
    # uq_access_requests_pending_email_mode is the authoritative guard
    # against concurrent duplicate submissions.
    dup = await session.execute(
        select(AccessRequest).where(
            AccessRequest.applicant_email == applicant_email,
            AccessRequest.requested_mode == requested_mode,
            AccessRequest.status == "pending",
        )
    )
    if dup.scalar_one_or_none() is not None:
        raise DomainException(
            ErrorCode.INVALID_REQUEST,
            "A pending request already exists for this email and access mode.",
            status_code=409,
        )

    ar = AccessRequest(
        applicant_name=applicant_name,
        applicant_email=applicant_email,
        organization=organization,
        requested_mode=requested_mode,
        use_case=use_case,
        terms_acknowledged=True,
        request_ip=request_ip,
    )
    session.add(ar)
    try:
        await session.flush()
    except IntegrityError:
        # A concurrent submission won the race for (email, mode) pending.
        await session.rollback()
        raise DomainException(
            ErrorCode.INVALID_REQUEST,
            "A pending request already exists for this email and access mode.",
            status_code=409,
        )

    await write_audit(
        session,
        actor_type="public",
        actor_id=applicant_email,
        action="access_request.create",
        resource_type="access_request",
        resource_id=str(ar.id),
        details={"email": applicant_email, "mode": requested_mode},
        request_ip=request_ip,
    )
    await session.flush()
    return ar


async def list_access_requests(
    session: AsyncSession,
    *,
    status_filter: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[AccessRequest], int]:
    stmt = select(AccessRequest)
    count_stmt = select(func.count()).select_from(AccessRequest)

    if status_filter:
        stmt = stmt.where(AccessRequest.status == status_filter)
        count_stmt = count_stmt.where(AccessRequest.status == status_filter)

    total = (await session.execute(count_stmt)).scalar_one()
    result = await session.execute(
        stmt.order_by(AccessRequest.created_at.desc()).offset(offset).limit(limit)
    )
    return list(result.scalars().all()), total


def _slugify(value: str) -> str:
    """Derive an organization slug from a name or email.

    Lowercase, alphanumeric segments separated by single hyphens, capped
    at 64 characters (the Organization.slug column width). Returns an
    empty string when nothing usable can be derived.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return slug[:64]


async def _get_or_create_organization(
    session: AsyncSession,
    *,
    org_name: str | None,
    applicant_email: str,
    creator_id: uuid.UUID,
) -> Organization:
    """Create an organization with a unique slug derived from its name.

    The slug is derived from the organization name (falling back to the
    applicant email) and made unique by appending a numeric suffix when
    the derived slug is already taken by an organization the applicant
    does not already manage. An existing org the applicant already
    manages is reused, which keeps re-approvals idempotent; an org
    belonging to someone else is never reused — the applicant gets a
    distinct organization instead.
    """
    base = _slugify(org_name) if org_name else ""
    if not base:
        base = _slugify(applicant_email)
    if not base:
        base = f"org-{uuid.uuid4().hex[:12]}"

    candidate = base
    suffix = 2
    while True:
        result = await session.execute(
            select(Organization).where(Organization.slug == candidate)
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            break

        # Slug is taken. If the applicant already manages this org this is
        # a re-approval — reuse it. Otherwise never attach the applicant
        # to someone else's organization; derive a new candidate slug.
        member_result = await session.execute(
            select(OrganizationMember).where(
                OrganizationMember.org_id == existing.id,
                OrganizationMember.user_id == creator_id,
            )
        )
        if member_result.scalar_one_or_none() is not None:
            return existing

        candidate = f"{base}-{suffix}"
        suffix += 1
        if suffix > 64:
            raise DomainException(
                ErrorCode.INTERNAL_ERROR,
                "Could not derive a unique organization slug.",
                status_code=500,
            )

    org = Organization(
        name=org_name if org_name else applicant_email,
        slug=candidate,
        created_by_user_id=creator_id,
    )
    session.add(org)
    await session.flush()
    return org


async def _ensure_org_manager(
    session: AsyncSession,
    *,
    org: Organization,
    user_id: uuid.UUID,
) -> None:
    """Add the applicant as an org manager, or upgrade an existing membership.

    Respects the UNIQUE(org_id, user_id) constraint: an existing membership
    row is updated to 'manager' instead of re-inserted.
    """
    result = await session.execute(
        select(OrganizationMember).where(
            OrganizationMember.org_id == org.id,
            OrganizationMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        session.add(
            OrganizationMember(
                org_id=org.id,
                user_id=user_id,
                role="manager",
            )
        )
    elif member.role != "manager":
        member.role = "manager"
    await session.flush()


async def approve_access_request(
    session: AsyncSession,
    request_id: uuid.UUID,
    reviewer_id: str,
    review_notes: str | None = None,
) -> dict:
    """Approve an access request and auto-provision a User + API key.

    Returns a dict with: request_id, status, reviewed_by, user_id, api_key (plain text, shown once),
    scope_id (for enterprise requests, None for personal), org_id (for enterprise requests, None for personal).
    If user already exists, no new user is created but a new API key is still issued.
    If any provisioning step fails, the request remains pending (fail-closed).

    Enterprise provisioning no longer grants the platform 'admin' role —
    that conflated platform administration with organization management.
    Instead it creates (or reuses) an Organization, adds the applicant as
    an org 'manager', and attaches their enterprise NetworkScope to the
    org. Org-scoped permissions are derived from membership, and revoking
    the membership or disabling the organization removes them.
    """
    ar = await _get_or_fail(session, request_id, for_update=True)
    if ar.status != "pending":
        raise DomainException(
            ErrorCode.INVALID_STATE,
            f"Request is '{ar.status}', not 'pending'.",
            status_code=409,
        )

    # --- Provisioning: create User + API key BEFORE marking approved ---
    # This ensures fail-closed: if provisioning fails, request stays pending.
    user = await get_or_create_user(
        username=ar.applicant_email,
        session=session,
    )

    scope_id: str | None = None
    org_id: str | None = None

    # Re-enable a disabled user on approval — both modes issue an API key,
    # and authenticate() rejects keys of disabled users, so approving a
    # request for a still-disabled user would provision a dead key.
    if user.is_disabled:
        user.is_disabled = False

    # If enterprise mode, provision an Organization + manager membership +
    # an enterprise NetworkScope. The user's platform role stays 'user';
    # org authority is modeled by the OrganizationMember role instead.
    if ar.requested_mode == "enterprise":
        org = await _get_or_create_organization(
            session,
            org_name=ar.organization,
            applicant_email=ar.applicant_email,
            creator_id=user.id,
        )
        await _ensure_org_manager(session, org=org, user_id=user.id)

        # Backfill org_id on the applicant's existing enterprise scopes;
        # create one attached to the org if they have none.
        scope_result = await session.execute(
            select(NetworkScope).where(
                NetworkScope.user_id == user.id,
                NetworkScope.scope_type == "enterprise",
            )
        )
        scopes = list(scope_result.scalars().all())
        if not scopes:
            scope_name = ar.organization if ar.organization else ar.applicant_email
            scopes = [
                NetworkScope(
                    user_id=user.id,
                    org_id=org.id,
                    scope_name=scope_name,
                    scope_type="enterprise",
                )
            ]
            session.add(scopes[0])
            await session.flush()
        else:
            for scope in scopes:
                if scope.org_id is None:
                    scope.org_id = org.id
            await session.flush()

        org_id = str(org.id)
        scope_id = str(scopes[0].id)

    # Issue a new API key for the user
    raw_api_key = await create_api_key_for_user(
        user=user,
        name=f"auto-provisioned-{ar.requested_mode}",
        session=session,
    )

    # --- Now mark approved ---
    ar.status = "approved"
    ar.reviewed_by = reviewer_id
    ar.reviewed_at = datetime.now(UTC)
    ar.review_notes = review_notes

    audit_details: dict = {
        "email": ar.applicant_email,
        "mode": ar.requested_mode,
        "provisioned_user_id": str(user.id),
    }
    if scope_id is not None:
        audit_details["scope_id"] = scope_id
    if org_id is not None:
        audit_details["org_id"] = org_id

    await write_audit(
        session,
        actor_type="user",
        actor_id=reviewer_id,
        action="access_request.approve",
        resource_type="access_request",
        resource_id=str(ar.id),
        details=audit_details,
    )
    await session.flush()
    return {
        "request_id": str(ar.id),
        "status": ar.status,
        "reviewed_by": ar.reviewed_by,
        "user_id": str(user.id),
        "api_key": raw_api_key,
        "scope_id": scope_id,
        "org_id": org_id,
    }


async def reject_access_request(
    session: AsyncSession,
    request_id: uuid.UUID,
    reviewer_id: str,
    review_notes: str | None = None,
) -> AccessRequest:
    if not review_notes or not review_notes.strip():
        raise DomainException(
            ErrorCode.INVALID_REQUEST,
            "Rejection reason is required and cannot be empty.",
            status_code=400,
        )
    ar = await _get_or_fail(session, request_id, for_update=True)
    if ar.status != "pending":
        raise DomainException(
            ErrorCode.INVALID_STATE,
            f"Request is '{ar.status}', not 'pending'.",
            status_code=409,
        )
    ar.status = "rejected"
    ar.reviewed_by = reviewer_id
    ar.reviewed_at = datetime.now(UTC)
    ar.review_notes = review_notes

    await write_audit(
        session,
        actor_type="user",
        actor_id=reviewer_id,
        action="access_request.reject",
        resource_type="access_request",
        resource_id=str(ar.id),
        details={"email": ar.applicant_email, "mode": ar.requested_mode},
    )
    await session.flush()
    return ar


async def _get_or_fail(session: AsyncSession, request_id: uuid.UUID, *, for_update: bool = False) -> AccessRequest:
    if for_update:
        stmt = select(AccessRequest).where(AccessRequest.id == request_id).with_for_update()
        result = await session.execute(stmt)
        ar = result.scalar_one_or_none()
    else:
        ar = await session.get(AccessRequest, request_id)
    if ar is None:
        raise DomainException(
            ErrorCode.RESOURCE_NOT_FOUND,
            "Access request not found.",
            status_code=404,
        )
    return ar