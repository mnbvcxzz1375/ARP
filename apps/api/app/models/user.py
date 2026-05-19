import uuid
from datetime import UTC, datetime
from enum import StrEnum

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
    username: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
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