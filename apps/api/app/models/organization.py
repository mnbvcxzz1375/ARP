"""Organization and OrganizationMember models.

Organizations are first-class entities that carry enterprise ownership
(previously enterprise network definitions hung off a personal user
account and died with it). Membership roles are limited to
'manager'/'member'; user-level RBAC stays on UserRole (user/admin/
super_admin).
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    is_disabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=func.text("false")
    )

    # Relationships
    # creator has no back_populates on User (User.organizations holds the
    # membership rows); defined so the unit of work can order inserts
    # when an org and its creating user are flushed together.
    creator: Mapped["User | None"] = relationship(
        foreign_keys=[created_by_user_id], lazy="select"
    )
    members: Mapped[list["OrganizationMember"]] = relationship(
        back_populates="organization",
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    network_scopes: Mapped[list["NetworkScope"]] = relationship(
        back_populates="org", lazy="selectin", passive_deletes=True
    )


class OrganizationMember(Base):
    __tablename__ = "organization_members"
    __table_args__ = (
        UniqueConstraint("org_id", "user_id", name="uq_organization_members_org_user"),
        CheckConstraint(
            "role IN ('manager', 'member')",
            name="ck_organization_members_valid_role",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Organization membership role: manager or member (NOT the user-level
    # UserRole user/admin/super_admin).
    role: Mapped[str] = mapped_column(String(16), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships (lazy on the child side to avoid selectin recursion
    # with Organization.members / User.organizations).
    organization: Mapped["Organization"] = relationship(back_populates="members", lazy="select")
    user: Mapped["User"] = relationship(back_populates="organizations", lazy="select")
