"""Pydantic schemas for public access request endpoints."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class CreateAccessRequestBody(BaseModel):
    applicant_name: str = Field(min_length=1, max_length=128)
    applicant_email: EmailStr
    organization: str | None = Field(default=None, max_length=256)
    requested_mode: str = Field(pattern=r"^(personal|enterprise)$")
    use_case: str = Field(min_length=1, max_length=1000)
    terms_acknowledged: bool


class AccessRequestResponse(BaseModel):
    request_id: str
    status: str
    created_at: datetime


class AccessRequestListItem(BaseModel):
    request_id: str
    applicant_name: str
    applicant_email: str
    organization: str | None
    requested_mode: str
    status: str
    review_notes: str | None = None
    created_at: datetime
    reviewed_at: datetime | None


class AccessRequestListResponse(BaseModel):
    access_requests: list[AccessRequestListItem]
    total: int
    offset: int
    limit: int


class AccessRequestDetailResponse(BaseModel):
    """Full detail of an access request for admin view."""
    request_id: str
    applicant_name: str
    applicant_email: EmailStr
    organization: str | None = None
    requested_mode: str
    use_case: str
    terms_acknowledged: bool
    status: str
    review_notes: str | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    request_ip: str | None = None
    created_at: datetime


class ApproveAccessRequestBody(BaseModel):
    review_notes: str | None = Field(default=None, max_length=1000)


class RejectAccessRequestBody(BaseModel):
    review_notes: str = Field(min_length=1, max_length=1000)


class ApproveAccessRequestResponse(BaseModel):
    request_id: str
    status: str
    reviewed_by: str
    review_notes: str | None = None
    user_id: str
    api_key: str
    scope_id: str | None = None
    # Organization provisioned for enterprise requests (None for personal).
    org_id: str | None = None


class RejectAccessRequestResponse(BaseModel):
    request_id: str
    status: str
    reviewed_by: str
    review_notes: str | None = None