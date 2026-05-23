"""RouteDecision model: records route selection decisions for audit and analysis."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RouteDecision(Base):
    __tablename__ = "route_decisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # Selected route
    selected_route_type: Mapped[str] = mapped_column(String(32), nullable=False)
    selected_relay_node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("relay_nodes.id", ondelete="SET NULL"), nullable=True
    )

    # Associated route lease
    lease_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("route_leases.id", ondelete="SET NULL"), nullable=True
    )

    # Phase 15: Network topology and policy tracking
    scope_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("network_scopes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_zone_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("network_zones.id", ondelete="SET NULL"), nullable=True, index=True
    )
    target_zone_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("network_zones.id", ondelete="SET NULL"), nullable=True, index=True
    )
    policy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("route_policies.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Candidate routes considered
    candidate_routes: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    # Rejection reasons for filtered routes
    rejection_reasons: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Fallback information
    fallback_from_route: Mapped[str | None] = mapped_column(String(32), nullable=True)
    fallback_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Scoring and timeliness
    timeliness_mode: Mapped[str] = mapped_column(String(16), default="normal", nullable=False)
    risk_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    final_score: Mapped[float | None] = mapped_column(nullable=True)

    # Decision metadata
    decision_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shadow_mode: Mapped[bool] = mapped_column(default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    task: Mapped["Task"] = relationship(back_populates="route_decisions", lazy="select")
    relay_node: Mapped["RelayNode"] = relationship(back_populates="route_decisions", lazy="select")
    metrics: Mapped[list["RouteMetric"]] = relationship(back_populates="route_decision", lazy="select")
