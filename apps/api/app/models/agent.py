import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    runtime: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    capabilities: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    inbound_policy: Mapped[str] = mapped_column(String(32), default="request_approval", nullable=False)
    discoverable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="offline", nullable=False)

    # Phase 15: Network topology
    scope_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("network_scopes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    zone_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("network_zones.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Phase 16: Egress gateway assignment
    egress_gateway_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("egress_gateways.id", ondelete="SET NULL"), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    owner: Mapped["User"] = relationship(back_populates="agents", lazy="joined")
    tokens: Mapped[list["AgentToken"]] = relationship(back_populates="agent", lazy="selectin", cascade="all, delete-orphan")
    outbound_channels: Mapped[list["DedicatedChannel"]] = relationship(
        foreign_keys="DedicatedChannel.source_agent_id", back_populates="source_agent", lazy="select"
    )
    inbound_channels: Mapped[list["DedicatedChannel"]] = relationship(
        foreign_keys="DedicatedChannel.target_agent_id", back_populates="target_agent", lazy="select"
    )