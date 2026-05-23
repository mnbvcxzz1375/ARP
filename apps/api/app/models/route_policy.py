"""RoutePolicy model: defines routing rules and constraints for enterprise topology."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RoutePolicy(Base):
    __tablename__ = "route_policies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Scope association (Phase 15 Task #1 dependency)
    # For now, scope_id is optional to allow implementation without blocking on Task #1
    scope_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )

    # Policy identification
    policy_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Priority (lower number = higher priority, evaluated first)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100, index=True)

    # Zone constraints (Phase 15 Task #1 dependency)
    # For now, zone IDs are optional to allow implementation without blocking on Task #1
    source_zone_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    target_zone_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )

    # Route type constraints
    # allowed_route_types: list of route types that ARE allowed (whitelist)
    # denied_route_types: list of route types that are DENIED (blacklist)
    # If both are empty, all routes are allowed
    # If allowed_route_types is set, only those routes are allowed
    # If denied_route_types is set, those routes are explicitly denied
    # denied_route_types takes precedence over allowed_route_types
    allowed_route_types: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    denied_route_types: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)

    # Approval requirements
    require_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Risk level classification
    # Values: low, medium, high, critical
    risk_level: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # Data boundary rules (JSON structure for flexibility)
    # Example: {"max_payload_bytes": 1048576, "allowed_data_types": ["text", "json"], "deny_pii": true}
    data_boundary_rules: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Policy state
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
