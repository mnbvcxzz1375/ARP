"""MessageDeliveryEvent model: records message delivery state transitions."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MessageDeliveryEvent(Base):
    __tablename__ = "message_delivery_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Event state
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # Event types: queued, route_selected, delivering, delivered, acknowledged, delivery_failed, expired

    # Route information
    route_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    relay_node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("relay_nodes.id", ondelete="SET NULL"), nullable=True
    )

    # Timing
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    queue_wait_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Error information
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Additional metadata
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    task: Mapped["Task"] = relationship(back_populates="delivery_events", lazy="select")
    relay_node: Mapped["RelayNode"] = relationship(back_populates="delivery_events", lazy="select")
