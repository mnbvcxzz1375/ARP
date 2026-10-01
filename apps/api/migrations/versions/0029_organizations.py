"""add organizations + organization_members tables, org_id on network_scopes

Revision ID: 0029_organizations
Revises: 0028_user_preferences
Create Date: 2026-10-01

Enterprises become a first-class entity so that enterprise network
definitions no longer live solely on a personal owner account (the
NetworkScope.user_id CASCADE meant deleting/disabling the owner killed
the enterprise definition).

- organizations: id, name, slug (unique), created_by_user_id (FK users,
  ondelete SET NULL), created_at/updated_at, is_disabled.
- organization_members: membership with role IN ('manager', 'member'),
  UNIQUE(org_id, user_id), both FKs ondelete CASCADE.
- network_scopes.org_id: nullable FK organizations(id) ondelete SET NULL
  (user_id is kept for personal scopes / backward compatibility).

Data migration: every existing scope_type='enterprise' NetworkScope gets
an Organization (slug derived from the scope name, de-duplicated against
existing slugs), its owner is enrolled as 'manager', and org_id is
backfilled on the scope.

The data migration is written with the SQLAlchemy expression API: column
values are always passed as bound parameters, never concatenated into
statement text.
"""

import re
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0029_organizations"
down_revision: Union[str, None] = "0028_user_preferences"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_MEMBERSHIP_ROLE_MANAGER = "manager"
_ENTERPRISE_SCOPE_TYPE = "enterprise"
_FALLBACK_SLUG = "org"


def _derive_slug(scope_name: str, existing_slugs: set[str]) -> str:
    """Derive a unique, URL-safe slug (<=64 chars) from a scope name.

    Non [a-z0-9] runs collapse to '-', edge '-' is stripped, empty names
    fall back to 'org'. Collisions are suffixed '-2', '-3', ... while the
    slug stays within 64 characters and remains unique in existing_slugs
    (which is mutated to include the returned slug).
    """
    base = re.sub(r"[^a-z0-9]+", "-", (scope_name or "").lower()).strip("-")
    if not base:
        base = _FALLBACK_SLUG
    base = base[:64]

    slug = base
    suffix = 2
    while slug in existing_slugs:
        tail = f"-{suffix}"
        slug = f"{base[: 64 - len(tail)]}{tail}"
        suffix += 1
    existing_slugs.add(slug)
    return slug


def upgrade() -> None:
    # --- organizations ---
    op.create_table(
        "organizations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column(
            "created_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "is_disabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_unique_constraint("uq_organizations_slug", "organizations", ["slug"])
    op.create_index("ix_organizations_slug", "organizations", ["slug"])
    op.create_index("ix_organizations_created_by_user_id", "organizations", ["created_by_user_id"])

    # --- organization_members ---
    op.create_table(
        "organization_members",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('manager', 'member')",
            name="ck_organization_members_valid_role",
        ),
        sa.UniqueConstraint("org_id", "user_id", name="uq_organization_members_org_user"),
    )
    op.create_index("ix_organization_members_org_id", "organization_members", ["org_id"])
    op.create_index("ix_organization_members_user_id", "organization_members", ["user_id"])

    # --- network_scopes.org_id ---
    op.add_column(
        "network_scopes",
        sa.Column(
            "org_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_network_scopes_org_id", "network_scopes", ["org_id"])

    # --- data migration: enterprise scopes -> organizations ---
    # Lightweight table definitions for set-based reads/writes. Every
    # value written below is passed through .values() as a bound
    # parameter; no value is ever concatenated into statement text.
    t_organizations = sa.table(
        "organizations",
        sa.column("id", UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("slug", sa.String),
        sa.column("created_by_user_id", UUID(as_uuid=True)),
        sa.column("is_disabled", sa.Boolean),
    )
    t_members = sa.table(
        "organization_members",
        sa.column("id", UUID(as_uuid=True)),
        sa.column("org_id", UUID(as_uuid=True)),
        sa.column("user_id", UUID(as_uuid=True)),
        sa.column("role", sa.String),
    )
    t_scopes = sa.table(
        "network_scopes",
        sa.column("id", UUID(as_uuid=True)),
        sa.column("user_id", UUID(as_uuid=True)),
        sa.column("scope_name", sa.String),
        sa.column("scope_type", sa.String),
        sa.column("org_id", UUID(as_uuid=True)),
    )

    select_enterprise_scopes = sa.select(
        t_scopes.c.id,
        t_scopes.c.user_id,
        t_scopes.c.scope_name,
    ).where(t_scopes.c.scope_type == sa.bindparam("scope_type"))
    select_existing_slugs = sa.select(t_organizations.c.slug)

    bind = op.get_bind()
    enterprise_scopes = bind.execute(
        select_enterprise_scopes, {"scope_type": _ENTERPRISE_SCOPE_TYPE}
    ).fetchall()

    if enterprise_scopes:
        existing_slugs = set(bind.scalars(select_existing_slugs).all())

        for scope_id, user_id, scope_name in enterprise_scopes:
            slug = _derive_slug(scope_name, existing_slugs)
            org_id = uuid.uuid4()

            bind.execute(
                t_organizations.insert().values(
                    id=org_id,
                    name=scope_name,
                    slug=slug,
                    created_by_user_id=user_id,
                    is_disabled=False,
                )
            )
            bind.execute(
                t_members.insert().values(
                    id=uuid.uuid4(),
                    org_id=org_id,
                    user_id=user_id,
                    role=_MEMBERSHIP_ROLE_MANAGER,
                )
            )
            bind.execute(
                t_scopes.update()
                .where(t_scopes.c.id == scope_id)
                .values(org_id=org_id)
            )


def downgrade() -> None:
    # Reverse order of upgrade. The organizations data created by the
    # data migration is dropped along with the tables; network_scopes
    # loses the org_id column but keeps its scope_type/user_id.
    op.drop_index("ix_network_scopes_org_id", table_name="network_scopes")
    # Constraints bound to network_scopes.org_id (the FK) are dropped
    # automatically by PostgreSQL when the column is dropped.
    op.drop_column("network_scopes", "org_id")

    op.drop_index("ix_organization_members_user_id", table_name="organization_members")
    op.drop_index("ix_organization_members_org_id", table_name="organization_members")
    op.drop_table("organization_members")

    op.drop_index("ix_organizations_created_by_user_id", table_name="organizations")
    op.drop_index("ix_organizations_slug", table_name="organizations")
    op.drop_constraint("uq_organizations_slug", "organizations", type_="unique")
    op.drop_table("organizations")
