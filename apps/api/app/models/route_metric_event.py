"""RouteMetricEvent model: records routing and delivery metrics."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RouteMetricEvent(Base):
    __tablename__ = "route_metric_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True, index=True
    )
    message_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # Route information
    route_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    relay_node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("relay_nodes.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Timing metrics
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    queue_wait_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Delivery metrics
    delivery_attempts: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    fallback_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Error tracking
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    policy_denied: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Data volume
    egress_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Additional metadata
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    task: Mapped["Task"] = relationship(back_populates="metric_events", lazy="select")
    relay_node: Mapped["RelayNode"] = relationship(back_populates="metric_events", lazy="select")
