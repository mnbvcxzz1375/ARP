"""FailoverConfig model: stores failover configuration for relay nodes."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FailoverConfig(Base):
    __tablename__ = "failover_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scope_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    # Scope can be network_scope_id, personal_scope_id, or global (null)

    primary_relay_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    backup_relay_ids: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    # Ordered list of backup relay UUIDs (as strings)

    failover_threshold_seconds: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    # Trigger failover if primary unhealthy for this duration

    auto_failover_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    manual_approval_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # If true, failover requires approval even when auto_failover_enabled

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    failover_events: Mapped[list["FailoverEvent"]] = relationship(back_populates="config", lazy="select")
