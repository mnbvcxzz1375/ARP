"""ChannelHealthCheck model: records health check results for dedicated channels."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ChannelHealthCheck(Base):
    __tablename__ = "channel_health_checks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Channel reference
    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dedicated_channels.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Check timestamp
    check_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # Performance metrics
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    packet_loss_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    bandwidth_mbps: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Health status
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    # Status: healthy, degraded, down

    # Error details (if any)
    error_message: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Relationship
    channel: Mapped["DedicatedChannel"] = relationship(back_populates="health_checks", lazy="select")
