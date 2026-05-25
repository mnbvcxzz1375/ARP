"""AccessRequest model — durable persistence for public access applications."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, CheckConstraint, Index, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AccessRequest(Base):
    __tablename__ = "access_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    applicant_name: Mapped[str] = mapped_column(String(128), nullable=False)
    applicant_email: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    organization: Mapped[str | None] = mapped_column(String(256), nullable=True)
    requested_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    use_case: Mapped[str] = mapped_column(String(1000), nullable=False)
    terms_acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True,
    )
    review_notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    request_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "requested_mode IN ('personal', 'enterprise')",
            name="ck_access_requests_valid_mode",
        ),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'expired')",
            name="ck_access_requests_valid_status",
        ),
        Index("ix_access_requests_email_mode", "applicant_email", "requested_mode"),
    )