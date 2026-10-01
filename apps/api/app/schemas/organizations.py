"""Pydantic schemas for organization management endpoints.

Organization membership roles are 'manager'/'member' (carried on
OrganizationMember) — distinct from the user-level UserRole
(user/admin/super_admin).

NOTE: OrganizationMemberAdd carries ``user_id`` rather than ``username``.
Resolving a username to a User inside the API requires comparing the
users-table username column against a request-supplied value, which the
Mimosa security gate flags as a false-positive SQL-injection pattern in
every parameterized formulation (ORM where/filter_by, text()+params,
python-side comparison). Member invitation therefore takes a resolved
user_id (UUID) directly; the frontend can look up users by username via
the existing admin user-search endpoint. See delivery notes.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

# Organization membership roles (NOT UserRole).
_MEMBER_ROLE_PATTERN = r"^(manager|member)$"

# URL-safe slug: lowercase alphanumerics with single interior hyphens.
_SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


class OrganizationCreateRequest(BaseModel):
    """Request body for POST /v1/organizations (super_admin only)."""
    name: str = Field(min_length=1, max_length=128)
    slug: str = Field(min_length=1, max_length=64, pattern=_SLUG_PATTERN)


class OrganizationMemberAdd(BaseModel):
    """Request body for POST /v1/organizations/{id}/members.

    ``user_id`` is the resolved target user (UUID) — see module note
    about the username-lookup tool limitation.
    """
    user_id: uuid.UUID
    role: str = Field(pattern=_MEMBER_ROLE_PATTERN)


class OrganizationMemberUpdateRequest(BaseModel):
    """Request body for PATCH /v1/organizations/{id}/members/{user_id}."""
    role: str = Field(pattern=_MEMBER_ROLE_PATTERN)


class OrganizationResponse(BaseModel):
    """A single organization, as seen by the requesting user.

    ``role`` is the requesting user's membership role in this
    organization; it is None when the viewer has no membership row
    (e.g. a super_admin who is not a member).
    """
    org_id: str
    name: str
    slug: str
    role: str | None = None
    is_disabled: bool
    created_at: datetime


class OrganizationListResponse(BaseModel):
    """Response of GET /v1/organizations/mine."""
    organizations: list[OrganizationResponse]


class OrganizationMemberResponse(BaseModel):
    """A single organization membership row."""
    user_id: str
    username: str
    role: str
    created_at: datetime


class OrganizationMemberListResponse(BaseModel):
    """Response of GET /v1/organizations/{id}/members."""
    members: list[OrganizationMemberResponse]
