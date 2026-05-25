"""Tests for public access request API — success, duplicate, failure, admin review."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.models.user import User
from app.models.api_key import ApiKey
from app.models.access_request import AccessRequest
from app.services.auth import generate_api_key


pytestmark = pytest.mark.asyncio


def _csrf_headers(client: AsyncClient) -> dict:
    """Build X-CSRF-Token header from the CSRF cookie stored on the client."""
    csrf = client.cookies.get("agentnet_csrf")
    if csrf:
        return {"X-CSRF-Token": csrf}
    return {}


async def _create_admin_with_session(client: AsyncClient, session) -> dict:
    """Create a super_admin user + API key, login + step-up, get session cookies."""
    from app.services.auth import generate_api_key

    user = User(username="admin_test", role="super_admin")
    session.add(user)
    await session.flush()

    raw_key, key_hash, key_prefix = generate_api_key()
    api_key = ApiKey(user_id=user.id, key_hash=key_hash, key_prefix=key_prefix, name="test")
    session.add(api_key)
    await session.commit()

    resp = await client.post(
        "/v1/dashboard/auth/login",
        json={"username": "admin_test", "api_key": raw_key},
    )
    assert resp.status_code == 200

    # Step-up re-authentication required for high-risk mutations
    csrf = client.cookies.get("agentnet_csrf")
    csrf_headers = {"X-CSRF-Token": csrf} if csrf else {}
    step_up_resp = await client.post(
        "/v1/dashboard/auth/step-up",
        json={"api_key": raw_key},
        headers=csrf_headers,
    )
    assert step_up_resp.status_code == 200

    return {"user_id": str(user.id), "raw_key": raw_key}


async def test_create_access_request_success(client: AsyncClient, session):
    """POST /v1/public/access-requests returns 201 with request_id."""
    resp = await client.post(
        "/v1/public/access-requests",
        json={
            "applicant_name": "Jane Doe",
            "applicant_email": "jane@example.com",
            "requested_mode": "personal",
            "use_case": "Connect my personal agents",
            "terms_acknowledged": True,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "request_id" in data
    assert data["status"] == "pending"


async def test_create_access_request_duplicate_pending(client: AsyncClient, session):
    """Duplicate pending request for same email+mode returns 409."""
    payload = {
        "applicant_name": "Dup User",
        "applicant_email": "dup@example.com",
        "requested_mode": "personal",
        "use_case": "Testing duplicate",
        "terms_acknowledged": True,
    }
    resp1 = await client.post("/v1/public/access-requests", json=payload)
    assert resp1.status_code == 201

    resp2 = await client.post("/v1/public/access-requests", json=payload)
    assert resp2.status_code == 409


async def test_create_access_request_terms_not_acknowledged(client: AsyncClient, session):
    """Request without terms acknowledged returns 400."""
    resp = await client.post(
        "/v1/public/access-requests",
        json={
            "applicant_name": "No Terms",
            "applicant_email": "noterms@example.com",
            "requested_mode": "personal",
            "use_case": "No terms test",
            "terms_acknowledged": False,
        },
    )
    assert resp.status_code == 400


async def test_create_access_request_invalid_mode(client: AsyncClient, session):
    """Invalid requested_mode returns 422 (Pydantic validation)."""
    resp = await client.post(
        "/v1/public/access-requests",
        json={
            "applicant_name": "Bad Mode",
            "applicant_email": "badmode@example.com",
            "requested_mode": "invalid",
            "use_case": "Bad mode test",
            "terms_acknowledged": True,
        },
    )
    assert resp.status_code == 422


async def test_admin_list_access_requests(client: AsyncClient, session):
    """Admin can list access requests."""
    admin = await _create_admin_with_session(client, session)

    # Create a request first
    await client.post(
        "/v1/public/access-requests",
        json={
            "applicant_name": "List Test",
            "applicant_email": "list@example.com",
            "requested_mode": "enterprise",
            "use_case": "Enterprise test",
            "terms_acknowledged": True,
        },
    )

    resp = await client.get(
        "/v1/dashboard/admin/access-requests",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_requests" in data
    assert data["total"] >= 1


async def test_admin_approve_access_request(client: AsyncClient, session):
    """Admin approve returns dict with user_id, api_key (auto-provisioned)."""
    admin = await _create_admin_with_session(client, session)

    # Create a request
    create_resp = await client.post(
        "/v1/public/access-requests",
        json={
            "applicant_name": "Approve Test",
            "applicant_email": "approve@example.com",
            "requested_mode": "personal",
            "use_case": "Approval test",
            "terms_acknowledged": True,
        },
    )
    request_id = create_resp.json()["request_id"]

    # Approve it — should return dict with provisioned user + api key
    resp = await client.post(
        f"/v1/dashboard/admin/access-requests/{request_id}/approve",
        json={"review_notes": "Looks good"},
        headers=_csrf_headers(client),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"
    assert "user_id" in data
    assert "api_key" in data
    assert data["api_key"].startswith("ak_")

    # Verify User was created in DB
    from sqlalchemy import select
    from app.models.user import User as UserModel
    from app.models.api_key import ApiKey as ApiKeyModel
    user_result = await session.execute(
        select(UserModel).where(UserModel.username == "approve@example.com")
    )
    provisioned_user = user_result.scalar_one_or_none()
    assert provisioned_user is not None
    assert provisioned_user.role == "user"  # personal mode stays "user"

    # Verify ApiKey was created for the user
    key_result = await session.execute(
        select(ApiKeyModel).where(ApiKeyModel.user_id == provisioned_user.id)
    )
    provisioned_key = key_result.scalar_one_or_none()
    assert provisioned_key is not None
    assert provisioned_key.name == "auto-provisioned-personal"
    assert provisioned_key.is_revoked is False


async def test_admin_reject_access_request(client: AsyncClient, session):
    """Admin can reject a pending access request with a reason."""
    admin = await _create_admin_with_session(client, session)

    create_resp = await client.post(
        "/v1/public/access-requests",
        json={
            "applicant_name": "Reject Test",
            "applicant_email": "reject@example.com",
            "requested_mode": "personal",
            "use_case": "Rejection test",
            "terms_acknowledged": True,
        },
    )
    request_id = create_resp.json()["request_id"]

    resp = await client.post(
        f"/v1/dashboard/admin/access-requests/{request_id}/reject",
        json={"review_notes": "Not eligible"},
        headers=_csrf_headers(client),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


async def test_reject_without_reason_fails(client: AsyncClient, session):
    """Rejecting without a reason returns 400 and leaves request pending."""
    admin = await _create_admin_with_session(client, session)

    create_resp = await client.post(
        "/v1/public/access-requests",
        json={
            "applicant_name": "No Reason",
            "applicant_email": "noreason@example.com",
            "requested_mode": "personal",
            "use_case": "No reason test",
            "terms_acknowledged": True,
        },
    )
    request_id = create_resp.json()["request_id"]

    # Reject with empty reason — Pydantic min_length=1 catches this (422), or DomainException (400)
    resp = await client.post(
        f"/v1/dashboard/admin/access-requests/{request_id}/reject",
        json={"review_notes": ""},
        headers=_csrf_headers(client),
    )
    assert resp.status_code in (400, 422)

    # Reject with whitespace-only reason — backend DomainException catches this
    resp2 = await client.post(
        f"/v1/dashboard/admin/access-requests/{request_id}/reject",
        json={"review_notes": "   "},
        headers=_csrf_headers(client),
    )
    assert resp2.status_code in (400, 422)

    # Reject with no body at all — Pydantic catches this (422)
    resp3 = await client.post(
        f"/v1/dashboard/admin/access-requests/{request_id}/reject",
        headers=_csrf_headers(client),
    )
    assert resp3.status_code in (400, 422)

    # Request should still be pending
    from sqlalchemy import select
    ar_result = await session.execute(
        select(AccessRequest).where(AccessRequest.id == __import__("uuid").UUID(request_id))
    )
    ar = ar_result.scalar_one()
    assert ar.status == "pending"


async def test_admin_approve_non_pending_fails(client: AsyncClient, session):
    """Approving an already-approved request returns 409."""
    admin = await _create_admin_with_session(client, session)

    create_resp = await client.post(
        "/v1/public/access-requests",
        json={
            "applicant_name": "Double Approve",
            "applicant_email": "double@example.com",
            "requested_mode": "personal",
            "use_case": "Double approve test",
            "terms_acknowledged": True,
        },
    )
    request_id = create_resp.json()["request_id"]

    # First approve
    await client.post(
        f"/v1/dashboard/admin/access-requests/{request_id}/approve",
        headers=_csrf_headers(client),
    )

    # Second approve should fail
    resp = await client.post(
        f"/v1/dashboard/admin/access-requests/{request_id}/approve",
        headers=_csrf_headers(client),
    )
    assert resp.status_code == 409


async def test_unauthenticated_admin_access_requests_fails(client: AsyncClient, session):
    """Unauthenticated request to admin endpoint returns 401."""
    resp = await client.get("/v1/dashboard/admin/access-requests")
    assert resp.status_code == 401


async def test_approve_enterprise_creates_network_scope(client: AsyncClient, session):
    """Approving an enterprise request upgrades role to admin, creates enterprise NetworkScope,
    and returns scope_id in response and audit."""
    admin = await _create_admin_with_session(client, session)

    create_resp = await client.post(
        "/v1/public/access-requests",
        json={
            "applicant_name": "Enterprise User",
            "applicant_email": "enterprise@example.com",
            "organization": "Acme Corp",
            "requested_mode": "enterprise",
            "use_case": "Enterprise deployment",
            "terms_acknowledged": True,
        },
    )
    request_id = create_resp.json()["request_id"]

    resp = await client.post(
        f"/v1/dashboard/admin/access-requests/{request_id}/approve",
        headers=_csrf_headers(client),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"
    assert data["scope_id"] is not None

    from sqlalchemy import select
    from app.models.user import User as UserModel
    from app.models.network_scope import NetworkScope

    user_result = await session.execute(
        select(UserModel).where(UserModel.username == "enterprise@example.com")
    )
    provisioned_user = user_result.scalar_one()
    assert provisioned_user.role == "admin"

    # Verify NetworkScope was created
    scope_result = await session.execute(
        select(NetworkScope).where(NetworkScope.user_id == provisioned_user.id)
    )
    scope = scope_result.scalar_one()
    assert scope.scope_type == "enterprise"
    assert scope.scope_name == "Acme Corp"
    assert scope.user_id == provisioned_user.id
    assert str(scope.id) == data["scope_id"]

    # Verify audit includes scope_id
    from app.models.audit_log import AuditLog
    audit_result = await session.execute(
        select(AuditLog)
        .where(AuditLog.resource_id == request_id)
        .where(AuditLog.action == "access_request.approve")
    )
    audit = audit_result.scalar_one()
    assert audit.details["scope_id"] == data["scope_id"]


async def test_approve_enterprise_scope_name_uses_email(client: AsyncClient, session):
    """Enterprise approve without organization uses email for scope_name."""
    admin = await _create_admin_with_session(client, session)

    create_resp = await client.post(
        "/v1/public/access-requests",
        json={
            "applicant_name": "No Org User",
            "applicant_email": "noorg@example.com",
            "requested_mode": "enterprise",
            "use_case": "Enterprise no org",
            "terms_acknowledged": True,
        },
    )
    request_id = create_resp.json()["request_id"]

    resp = await client.post(
        f"/v1/dashboard/admin/access-requests/{request_id}/approve",
        headers=_csrf_headers(client),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["scope_id"] is not None

    from sqlalchemy import select
    from app.models.network_scope import NetworkScope
    scope_result = await session.execute(
        select(NetworkScope).where(NetworkScope.id == __import__("uuid").UUID(data["scope_id"]))
    )
    scope = scope_result.scalar_one()
    assert scope.scope_name == "noorg@example.com"


async def test_approve_personal_no_scope_id(client: AsyncClient, session):
    """Personal mode approval returns no scope_id."""
    admin = await _create_admin_with_session(client, session)

    create_resp = await client.post(
        "/v1/public/access-requests",
        json={
            "applicant_name": "Personal User",
            "applicant_email": "personal_noscope@example.com",
            "requested_mode": "personal",
            "use_case": "Personal test",
            "terms_acknowledged": True,
        },
    )
    request_id = create_resp.json()["request_id"]

    resp = await client.post(
        f"/v1/dashboard/admin/access-requests/{request_id}/approve",
        headers=_csrf_headers(client),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("scope_id") is None


async def test_provisioned_key_enables_login(client: AsyncClient, session):
    """The auto-provisioned API key can be used to log into the dashboard."""
    admin = await _create_admin_with_session(client, session)

    create_resp = await client.post(
        "/v1/public/access-requests",
        json={
            "applicant_name": "Login Test",
            "applicant_email": "login@example.com",
            "requested_mode": "personal",
            "use_case": "Login test",
            "terms_acknowledged": True,
        },
    )
    request_id = create_resp.json()["request_id"]

    approve_resp = await client.post(
        f"/v1/dashboard/admin/access-requests/{request_id}/approve",
        headers=_csrf_headers(client),
    )
    provisioned_key = approve_resp.json()["api_key"]

    # Use the provisioned key to login
    login_resp = await client.post(
        "/v1/dashboard/auth/login",
        json={"username": "login@example.com", "api_key": provisioned_key},
    )
    assert login_resp.status_code == 200


async def test_re_approve_existing_user_no_duplicate(client: AsyncClient, session):
    """Approving a request for an already-existing user creates a new key, not a new user."""
    admin = await _create_admin_with_session(client, session)

    # Create user manually first
    from app.services.auth import get_or_create_user
    existing_user = await get_or_create_user("existing@example.com", session)
    await session.flush()
    original_user_id = str(existing_user.id)

    # Now approve an access request for the same email
    create_resp = await client.post(
        "/v1/public/access-requests",
        json={
            "applicant_name": "Existing User",
            "applicant_email": "existing@example.com",
            "requested_mode": "personal",
            "use_case": "Already exists",
            "terms_acknowledged": True,
        },
    )
    request_id = create_resp.json()["request_id"]

    resp = await client.post(
        f"/v1/dashboard/admin/access-requests/{request_id}/approve",
        headers=_csrf_headers(client),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == original_user_id  # Same user, not a new one


async def test_admin_get_access_request_detail(client: AsyncClient, session):
    """Admin can get full detail of a single access request."""
    admin = await _create_admin_with_session(client, session)

    create_resp = await client.post(
        "/v1/public/access-requests",
        json={
            "applicant_name": "Detail Test",
            "applicant_email": "detail@example.com",
            "organization": "Detail Corp",
            "requested_mode": "enterprise",
            "use_case": "Detail view test",
            "terms_acknowledged": True,
        },
    )
    request_id = create_resp.json()["request_id"]

    resp = await client.get(
        f"/v1/dashboard/admin/access-requests/{request_id}",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["request_id"] == request_id
    assert data["applicant_name"] == "Detail Test"
    assert data["applicant_email"] == "detail@example.com"
    assert data["organization"] == "Detail Corp"
    assert data["requested_mode"] == "enterprise"
    assert data["use_case"] == "Detail view test"
    assert data["terms_acknowledged"] is True
    assert data["status"] == "pending"
    assert data["review_notes"] is None
    assert data["reviewed_by"] is None
    assert data["reviewed_at"] is None
    assert "created_at" in data


async def test_admin_get_access_request_detail_not_found(client: AsyncClient, session):
    """Admin detail for non-existent request returns 404."""
    admin = await _create_admin_with_session(client, session)

    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = await client.get(
        f"/v1/dashboard/admin/access-requests/{fake_id}",
    )
    assert resp.status_code == 404


async def test_admin_get_access_request_detail_rejected(client: AsyncClient, session):
    """Admin detail shows review_notes and reviewed_by for rejected request."""
    admin = await _create_admin_with_session(client, session)

    create_resp = await client.post(
        "/v1/public/access-requests",
        json={
            "applicant_name": "Reject Detail",
            "applicant_email": "rejectdetail@example.com",
            "requested_mode": "personal",
            "use_case": "Reject detail test",
            "terms_acknowledged": True,
        },
    )
    request_id = create_resp.json()["request_id"]

    # Reject it
    await client.post(
        f"/v1/dashboard/admin/access-requests/{request_id}/reject",
        json={"review_notes": "Not eligible for access"},
        headers=_csrf_headers(client),
    )

    # Get detail
    resp = await client.get(
        f"/v1/dashboard/admin/access-requests/{request_id}",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "rejected"
    assert data["review_notes"] == "Not eligible for access"
    assert data["reviewed_by"] is not None
    assert data["reviewed_at"] is not None


# ──────────────────────────────────────────────────────────────────
# Access Request Audit Trail
# ──────────────────────────────────────────────────────────────────


async def test_access_request_audit_trail_after_create(client: AsyncClient, session):
    """Creating an access request produces an audit log entry accessible via audit-trail endpoint."""
    admin = await _create_admin_with_session(client, session)

    create_resp = await client.post(
        "/v1/public/access-requests",
        json={
            "applicant_name": "Audit Trail",
            "applicant_email": "audittrail@example.com",
            "requested_mode": "personal",
            "use_case": "Audit trail test",
            "terms_acknowledged": True,
        },
    )
    request_id = create_resp.json()["request_id"]

    resp = await client.get(
        f"/v1/dashboard/admin/access-requests/{request_id}/audit-trail",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    entries = data["audit_logs"]
    create_entry = next((e for e in entries if e["action"] == "access_request.create"), None)
    assert create_entry is not None
    assert create_entry["resource_type"] == "access_request"
    assert create_entry["resource_id"] == request_id


async def test_access_request_audit_trail_after_approve(client: AsyncClient, session):
    """Approving a request adds an approve audit entry to the trail."""
    admin = await _create_admin_with_session(client, session)

    create_resp = await client.post(
        "/v1/public/access-requests",
        json={
            "applicant_name": "Audit Approve",
            "applicant_email": "auditapprove@example.com",
            "requested_mode": "personal",
            "use_case": "Audit approve test",
            "terms_acknowledged": True,
        },
    )
    request_id = create_resp.json()["request_id"]

    await client.post(
        f"/v1/dashboard/admin/access-requests/{request_id}/approve",
        headers=_csrf_headers(client),
    )

    resp = await client.get(
        f"/v1/dashboard/admin/access-requests/{request_id}/audit-trail",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2
    actions = {e["action"] for e in data["audit_logs"]}
    assert "access_request.create" in actions
    assert "access_request.approve" in actions


async def test_access_request_audit_trail_after_reject(client: AsyncClient, session):
    """Rejecting a request adds a reject audit entry to the trail."""
    admin = await _create_admin_with_session(client, session)

    create_resp = await client.post(
        "/v1/public/access-requests",
        json={
            "applicant_name": "Audit Reject",
            "applicant_email": "auditreject@example.com",
            "requested_mode": "personal",
            "use_case": "Audit reject test",
            "terms_acknowledged": True,
        },
    )
    request_id = create_resp.json()["request_id"]

    await client.post(
        f"/v1/dashboard/admin/access-requests/{request_id}/reject",
        json={"review_notes": "Rejected"},
        headers=_csrf_headers(client),
    )

    resp = await client.get(
        f"/v1/dashboard/admin/access-requests/{request_id}/audit-trail",
    )
    assert resp.status_code == 200
    data = resp.json()
    actions = {e["action"] for e in data["audit_logs"]}
    assert "access_request.reject" in actions


async def test_access_request_audit_trail_empty_for_no_audit(client: AsyncClient, session):
    """Audit trail for a valid but non-existent request UUID returns 404, not empty list."""
    admin = await _create_admin_with_session(client, session)

    fake_id = "00000000-0000-0000-0000-000000000001"
    resp = await client.get(
        f"/v1/dashboard/admin/access-requests/{fake_id}/audit-trail",
    )
    assert resp.status_code == 404


async def test_access_request_audit_trail_invalid_uuid(client: AsyncClient, session):
    """Audit trail for an invalid UUID format returns 422, not empty list."""
    admin = await _create_admin_with_session(client, session)

    resp = await client.get(
        "/v1/dashboard/admin/access-requests/not-a-uuid/audit-trail",
    )
    assert resp.status_code == 422


async def test_access_request_audit_trail_unauthenticated_fails(client: AsyncClient, session):
    """Unauthenticated request to audit-trail endpoint returns 401."""
    resp = await client.get(
        "/v1/dashboard/admin/access-requests/00000000-0000-0000-0000-000000000000/audit-trail",
    )
    assert resp.status_code == 401


async def test_audit_logs_resource_id_filter(client: AsyncClient, session):
    """The audit-logs endpoint supports resource_id filter."""
    admin = await _create_admin_with_session(client, session)

    create_resp = await client.post(
        "/v1/public/access-requests",
        json={
            "applicant_name": "Filter Test",
            "applicant_email": "filtertest@example.com",
            "requested_mode": "personal",
            "use_case": "Filter test",
            "terms_acknowledged": True,
        },
    )
    request_id = create_resp.json()["request_id"]

    resp = await client.get(
        "/v1/dashboard/admin/audit-logs",
        params={"resource_type": "access_request", "resource_id": request_id},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    for entry in data["audit_logs"]:
        assert entry["resource_type"] == "access_request"
        assert entry["resource_id"] == request_id


async def test_audit_log_list_item_includes_details(client: AsyncClient, session):
    """AuditLogListItem now includes the details JSONB field."""
    admin = await _create_admin_with_session(client, session)

    create_resp = await client.post(
        "/v1/public/access-requests",
        json={
            "applicant_name": "Details Test",
            "applicant_email": "detailstest@example.com",
            "requested_mode": "personal",
            "use_case": "Details field test",
            "terms_acknowledged": True,
        },
    )
    request_id = create_resp.json()["request_id"]

    resp = await client.get(
        f"/v1/dashboard/admin/access-requests/{request_id}/audit-trail",
    )
    assert resp.status_code == 200
    entries = resp.json()["audit_logs"]
    create_entry = next((e for e in entries if e["action"] == "access_request.create"), None)
    assert create_entry is not None
    assert create_entry["details"] is not None
    assert "email" in create_entry["details"]