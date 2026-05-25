"""Public access request endpoints -- no auth required, fail-closed."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.access_request import (
    AccessRequestResponse,
    CreateAccessRequestBody,
)
from app.services.access_request_service import create_access_request

router = APIRouter(prefix="/v1/public", tags=["public"])


@router.post("/access-requests", response_model=AccessRequestResponse, status_code=201)
async def submit_access_request(
    body: CreateAccessRequestBody,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Submit a public access request. No auth required. Durable persistence required."""
    request_ip = request.client.host if request.client else None

    ar = await create_access_request(
        session,
        applicant_name=body.applicant_name,
        applicant_email=body.applicant_email,
        requested_mode=body.requested_mode,
        use_case=body.use_case,
        terms_acknowledged=body.terms_acknowledged,
        organization=body.organization,
        request_ip=request_ip,
    )
    await session.commit()

    return AccessRequestResponse(
        request_id=str(ar.id),
        status=ar.status,
        created_at=ar.created_at,
    )