"""Egress Gateway model for external API/service access control."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EgressGateway(Base):
    __tablename__ = "egress_gateways"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scope_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True, comment="User/org scope"
    )
    gateway_name: Mapped[str] = mapped_column(String(128), nullable=False)
    gateway_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="api/model/github/deployment/mcp"
    )
    domain_allowlist: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, comment="Allowed domains/endpoints"
    )
    secret_store_ref: Mapped[str | None] = mapped_column(
        String(256), nullable=True, comment="Reference to secret store (not the secret itself)"
    )
    rate_limit_config: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="Rate limit rules per gateway"
    )
    cache_config: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="Cache TTL and rules"
    )
    cost_tracking: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
