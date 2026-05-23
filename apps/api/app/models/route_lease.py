"""RouteLease model: temporary communication authorization."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RouteLease(Base):
    __tablename__ = "route_leases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    route_type: Mapped[str] = mapped_column(String(32), nullable=False)

    # Lease constraints
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    max_messages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    allowed_task_types: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)

    # Usage tracking
    messages_sent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bytes_sent: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    # Approval linkage
    approval_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("approvals.id", ondelete="SET NULL"), nullable=True
    )

    # Revocation
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoke_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    source_agent: Mapped["Agent"] = relationship(foreign_keys=[source_agent_id], lazy="select")
    target_agent: Mapped["Agent"] = relationship(foreign_keys=[target_agent_id], lazy="select")
    approval: Mapped["Approval"] = relationship(back_populates="route_leases", lazy="select")
