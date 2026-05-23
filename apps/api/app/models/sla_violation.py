"""SLAViolation model: records SLA violations."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SLAViolation(Base):
    __tablename__ = "sla_violations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sla_targets.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # When the violation occurred
    violation_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # Actual metric value at violation time
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)

    # Severity: warning or critical
    severity: Mapped[str] = mapped_column(String(16), nullable=False, index=True)

    # Duration of violation in seconds
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # When the violation was resolved (None if still ongoing)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Resolution note
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    target: Mapped["SLATarget"] = relationship(back_populates="violations", lazy="select")
