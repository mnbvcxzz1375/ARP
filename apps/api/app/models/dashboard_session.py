import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DashboardSession(Base):
    __tablename__ = "dashboard_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # Only hash stored — never plaintext token
    session_hash: Mapped[str] = mapped_column(
        String(128), nullable=False
    )
    # Format not fixed; may include algorithm prefix in future
    csrf_hash: Mapped[str] = mapped_column(
        String(128), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    idle_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_csrf_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rotated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    step_up_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_reason: Mapped[str | None] = mapped_column(
        String(256), nullable=True
    )
    revoked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    request_ip: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    user_agent: Mapped[str | None] = mapped_column(
        String(512), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship(
        back_populates="dashboard_sessions",
        foreign_keys=[user_id],
    )
    revoked_by: Mapped["User | None"] = relationship(
        back_populates="revoked_dashboard_sessions",
        foreign_keys=[revoked_by_user_id],
    )
