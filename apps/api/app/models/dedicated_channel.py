"""DedicatedChannel model: records dedicated network channels between agents."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DedicatedChannel(Base):
    __tablename__ = "dedicated_channels"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Scope association
    scope_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("network_scopes.id", ondelete="CASCADE"), nullable=True, index=True
    )

    # Channel identification
    channel_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    channel_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # Channel types: vpn, private_link, p2p, direct_connect

    # Agent endpoints
    source_agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Connection configuration
    connection_config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    # Example: {"endpoint": "vpn.example.com:443", "protocol": "wireguard", "public_key": "..."}

    # Encryption configuration
    encryption_config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    # Example: {"algorithm": "AES-256-GCM", "key_rotation_days": 30, "tls_version": "1.3"}

    # Performance targets
    bandwidth_mbps: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_target_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Status
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    scope: Mapped["NetworkScope"] = relationship(back_populates="dedicated_channels", lazy="select")
    source_agent: Mapped["Agent"] = relationship(
        foreign_keys=[source_agent_id], back_populates="outbound_channels", lazy="select"
    )
    target_agent: Mapped["Agent"] = relationship(
        foreign_keys=[target_agent_id], back_populates="inbound_channels", lazy="select"
    )
    health_checks: Mapped[list["ChannelHealthCheck"]] = relationship(
        back_populates="channel", lazy="select", cascade="all, delete-orphan"
    )

    @property
    def is_healthy(self) -> bool:
        """Check if channel is healthy based on most recent health check."""
        if not self.enabled:
            return False
        if not self.health_checks:
            return False
        latest_check = max(self.health_checks, key=lambda c: c.check_time)
        return latest_check.status == "healthy"
