import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import sqlalchemy as sa

from app.database import Base


class UserRole(StrEnum):
    USER = "user"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'admin', 'super_admin')",
            name="ck_users_valid_role",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Non-unique display label: the user_id (UUID) is the canonical
    # identifier. Login resolves the user by API key, and the UI
    # disambiguates same-named users with a short user_id suffix.
    username: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=UserRole.USER.value,
        server_default=sa.text("'user'"),
        index=True,
    )
    is_disabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=sa.text("false"),
    )
    locale: Mapped[str | None] = mapped_column(String(16), nullable=True)
    preferences: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=sa.text("'{}'"),
    )

    api_keys: Mapped[list["ApiKey"]] = relationship(back_populates="user", lazy="selectin")
    agents: Mapped[list["Agent"]] = relationship(back_populates="owner", lazy="selectin", cascade="all, delete-orphan")
    dashboard_sessions: Mapped[list["DashboardSession"]] = relationship(
        back_populates="user",
        lazy="selectin",
        cascade="all, delete-orphan",
        foreign_keys="DashboardSession.user_id",
    )
    revoked_dashboard_sessions: Mapped[list["DashboardSession"]] = relationship(
        back_populates="revoked_by",
        lazy="selectin",
        foreign_keys="DashboardSession.revoked_by_user_id",
    )
    personal_scope: Mapped["PersonalScope"] = relationship(
        back_populates="user",
        lazy="selectin",
        uselist=False,
        cascade="all, delete-orphan",
    )
    network_scopes: Mapped[list["NetworkScope"]] = relationship(
        back_populates="user",
        lazy="select",
        cascade="all, delete-orphan",
    )
    # Organization memberships (OrganizationMember rows, which carry the
    # manager/member role). Not the user-level UserRole.
    organizations: Mapped[list["OrganizationMember"]] = relationship(
        back_populates="user",
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )