"""NetworkScope model: defines enterprise network boundaries and agent groupings."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class NetworkScope(Base):
    __tablename__ = "network_scopes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Owner
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Scope identification
    scope_name: Mapped[str] = mapped_column(String(128), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # scope_type: personal, enterprise

    # Network definition
    network_cidr: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Example: "10.0.0.0/8", "192.168.1.0/24"

    # Agent membership (array of agent IDs)
    agent_ids: Mapped[list[str]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list, nullable=False)

    # Zone membership (array of zone IDs)
    zone_ids: Mapped[list[str]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="network_scopes", lazy="selectin")
    zones: Mapped[list["NetworkZone"]] = relationship(
        back_populates="scope", lazy="select", cascade="all, delete-orphan", passive_deletes=True
    )
    dedicated_channels: Mapped[list["DedicatedChannel"]] = relationship(back_populates="scope", lazy="select")
