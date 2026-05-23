"""RelayNode model: records relay infrastructure nodes."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RelayNode(Base):
    __tablename__ = "relay_nodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    node_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # Node types: central, personal_edge, local_edge, regional, egress, dedicated

    # Health status
    status: Mapped[str] = mapped_column(String(16), default="unknown", nullable=False)
    # Status: healthy, degraded, down, unknown

    # Load metrics
    current_load: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    queue_depth: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Performance metrics
    avg_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    success_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Capabilities
    capabilities: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    max_capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Network location
    region: Mapped[str | None] = mapped_column(String(64), nullable=True)
    zone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    network_info: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    # network_info: {"subnet": "192.168.1.0/24", "gateway": "192.168.1.1", "local_ip": "192.168.1.100"}

    # Heartbeat
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Metadata
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    route_decisions: Mapped[list["RouteDecision"]] = relationship(back_populates="relay_node", lazy="select")
    delivery_events: Mapped[list["MessageDeliveryEvent"]] = relationship(back_populates="relay_node", lazy="select")
    metric_events: Mapped[list["RouteMetricEvent"]] = relationship(back_populates="relay_node", lazy="select")
    route_metrics: Mapped[list["RouteMetric"]] = relationship(back_populates="relay_node", lazy="select")

    @property
    def is_healthy(self) -> bool:
        """Check if relay is healthy based on status and recent heartbeat."""
        if self.status not in ["healthy", "degraded"]:
            return False
        if not self.last_heartbeat_at:
            return False
        # Consider healthy if heartbeat within last 60 seconds
        age_seconds = (datetime.now(datetime.now().astimezone().tzinfo) - self.last_heartbeat_at).total_seconds()
        return age_seconds < 60
