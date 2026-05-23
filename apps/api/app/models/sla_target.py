"""SLATarget model: defines SLA targets for monitoring."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SLATarget(Base):
    __tablename__ = "sla_targets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Scope: global, zone, relay_node, or agent
    scope_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    # Target name for identification
    target_name: Mapped[str] = mapped_column(String(128), nullable=False)

    # Metric type: latency_p99, latency_p95, success_rate, availability, throughput
    metric_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    # Target value (e.g., 500 for 500ms P99, 0.999 for 99.9% success rate)
    target_value: Mapped[float] = mapped_column(Float, nullable=False)

    # Warning threshold (e.g., 0.95 means warn at 95% of target)
    warning_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.9)

    # Critical threshold (e.g., 0.8 means critical at 80% of target)
    critical_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)

    # Measurement window in seconds (e.g., 300 for 5 minutes)
    measurement_window_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)

    # Whether this target is enabled
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    violations: Mapped[list["SLAViolation"]] = relationship(
        back_populates="target", cascade="all, delete-orphan", lazy="select"
    )
