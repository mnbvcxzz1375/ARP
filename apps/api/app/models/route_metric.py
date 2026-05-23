"""RouteMetric model: records route performance metrics for SLA monitoring."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RouteMetric(Base):
    __tablename__ = "route_metrics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Link to route decision
    route_decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("route_decisions.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Metric timestamp
    metric_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # Latency in milliseconds
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)

    # Whether the delivery was successful
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)

    # Error code if failed
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Relay node used (for zone-level metrics)
    relay_node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("relay_nodes.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Zone ID (for zone-level aggregation)
    zone_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    route_decision: Mapped["RouteDecision"] = relationship(back_populates="metrics", lazy="select")
    relay_node: Mapped["RelayNode"] = relationship(back_populates="route_metrics", lazy="select")
