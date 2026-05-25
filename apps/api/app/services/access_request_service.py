"""Business logic for public access requests -- fail-closed, no mock success."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DomainException
from app.models.access_request import AccessRequest
from app.models.network_scope import NetworkScope
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

    # Prevent duplicate pending requests from same email for same mode
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
    await session.flush()

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


async def approve_access_request(
    session: AsyncSession,
    request_id: uuid.UUID,
    reviewer_id: str,
    review_notes: str | None = None,
) -> dict:
    """Approve an access request and auto-provision a User + API key.

    Returns a dict with: request_id, status, reviewed_by, user_id, api_key (plain text, shown once),
    scope_id (for enterprise requests, None for personal).
    If user already exists, no new user is created but a new API key is still issued.
    If any provisioning step fails, the request remains pending (fail-closed).
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

    # If enterprise mode, upgrade role to admin, re-enable if disabled, and create NetworkScope
    if ar.requested_mode == "enterprise":
        if user.role == "user":
            user.role = "admin"
        if user.is_disabled:
            user.is_disabled = False
        await session.flush()

        # Create enterprise NetworkScope owned by the provisioned user
        scope_name = ar.organization if ar.organization else ar.applicant_email
        scope = NetworkScope(
            user_id=user.id,
            scope_name=scope_name,
            scope_type="enterprise",
        )
        session.add(scope)
        await session.flush()
        scope_id = str(scope.id)

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