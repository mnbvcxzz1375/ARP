"""PersonalScope model: personal mode configuration per user."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PersonalScope(Base):
    __tablename__ = "personal_scopes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    scope_name: Mapped[str] = mapped_column(String(64), default="personal", nullable=False)

    # Relay preferences
    default_relay_type: Mapped[str] = mapped_column(String(32), default="central_relay", nullable=False)
    enable_edge_relay: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    enable_secure_channel: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # 0033: personal routing strategy ('fast' | 'normal' | 'reliable').
    # Scoring-layer override only; see path_optimizer.compute_final_score.
    routing_strategy: Mapped[str] = mapped_column(String(16), default="normal", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="personal_scope", lazy="selectin")
