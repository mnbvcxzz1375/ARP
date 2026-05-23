"""NetworkZone model: defines hierarchical network zones within a scope."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class NetworkZone(Base):
    __tablename__ = "network_zones"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Scope association
    scope_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("network_scopes.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Zone identification
    zone_name: Mapped[str] = mapped_column(String(128), nullable=False)
    zone_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # zone_type: local, regional, global, local_edge, central, cloud, egress

    # Hierarchical structure
    parent_zone_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("network_zones.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Relay nodes in this zone (array of relay node IDs)
    relay_node_ids: Mapped[list[str]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list, nullable=False)

    # Zone metadata (flexible JSON for zone-specific config)
    zone_metadata: Mapped[dict] = mapped_column("zone_metadata", JSONB, default=dict, nullable=False)
    # Example: {"region": "us-west-2", "latency_target_ms": 50, "bandwidth_mbps": 1000}

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    scope: Mapped["NetworkScope"] = relationship(back_populates="zones", lazy="selectin")
    parent_zone: Mapped["NetworkZone | None"] = relationship(
        remote_side=[id], back_populates="child_zones", lazy="selectin"
    )
    child_zones: Mapped[list["NetworkZone"]] = relationship(
        back_populates="parent_zone", lazy="selectin"
    )
