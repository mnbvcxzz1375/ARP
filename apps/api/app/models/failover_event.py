"""FailoverEvent model: records failover execution history."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FailoverEvent(Base):
    __tablename__ = "failover_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("failover_configs.id"), nullable=False, index=True
    )

    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    trigger_reason: Mapped[str] = mapped_column(Text, nullable=False)
    # Reason: health_check_failed, circuit_breaker_open, manual_trigger, etc.

    from_relay_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    to_relay_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    affected_task_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Number of tasks migrated during failover

    auto_triggered: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    approval_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("approvals.id"), nullable=True
    )
    # If manual_approval_required, link to approval record

    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rollback_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # If failover was rolled back

    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    # Status: pending, in_progress, completed, failed, rolled_back

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    config: Mapped["FailoverConfig"] = relationship(back_populates="failover_events", lazy="select")
    approval: Mapped["Approval | None"] = relationship(lazy="select")
