import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


VALID_TRANSITIONS: dict[str, set[str]] = {
    "created": {"queued", "delivered", "accepted", "expired", "cancelled"},
    "queued": {"delivered", "expired", "cancelled"},
    "delivered": {"accepted", "expired", "cancelled", "failed"},
    "accepted": {"running", "expired", "cancelled", "failed"},
    "running": {"completed", "failed", "awaiting_approval", "cancelled", "expired"},
    "awaiting_approval": {"running", "failed", "rejected", "cancelled", "expired"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
    "expired": set(),
    "rejected": set(),
}


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="created", nullable=False, index=True)
    message_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_progress_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    messages: Mapped[list["Message"]] = relationship(back_populates="task", lazy="select")
    progress_entries: Mapped[list["TaskProgress"]] = relationship(back_populates="task", lazy="select", order_by="TaskProgress.seq")
    approvals: Mapped[list["Approval"]] = relationship(back_populates="task", lazy="select")

    __table_args__ = (
        UniqueConstraint("created_by", "assigned_to", "idempotency_key", name="uq_tasks_idempotency_key"),
    )
