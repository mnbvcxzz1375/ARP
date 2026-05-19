"""Phase Web 1: RBAC (role, is_disabled) + dashboard sessions.

Revision ID: 0009_phase_web_1_rbac_sessions
Revises: 0008_fix_idempotency_scope
Create Date: 2026-05-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0009_phase_web_1_rbac_sessions"
down_revision: Union[str, None] = "0008_fix_idempotency_scope"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Users: add RBAC columns ---
    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'user'"),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "is_disabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index("ix_users_role", "users", ["role"])

    # --- Dashboard sessions table ---
    op.create_table(
        "dashboard_sessions",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("session_hash", sa.String(128), nullable=False),
        sa.Column("csrf_hash", sa.String(128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idle_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("last_csrf_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("step_up_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(256), nullable=True),
        sa.Column(
            "revoked_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("request_ip", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
    )

    # Indexes / constraints from autogenerate (detected from ORM)
    op.create_unique_constraint(
        "uq_dashboard_sessions_session_hash",
        "dashboard_sessions",
        ["session_hash"],
    )
    op.create_index(
        "ix_dashboard_sessions_user_id",
        "dashboard_sessions",
        ["user_id"],
    )

    # --- Manual amendments ---

    # Check constraint for valid role values
    op.create_check_constraint(
        "ck_users_valid_role", "users",
        "role IN ('user', 'admin', 'super_admin')",
    )

    # Composite indexes
    op.create_index("ix_dashboard_sessions_user_revoked", "dashboard_sessions", ["user_id", "revoked_at"])
    op.create_index("ix_dashboard_sessions_user_expires", "dashboard_sessions", ["user_id", "expires_at"])

    # Explicit single-column indexes
    op.create_index("ix_dashboard_sessions_revoked_by_user_id", "dashboard_sessions", ["revoked_by_user_id"])
    op.create_index("ix_dashboard_sessions_step_up_until", "dashboard_sessions", ["step_up_until"])
    op.create_index("ix_dashboard_sessions_expires_at", "dashboard_sessions", ["expires_at"])
    op.create_index("ix_dashboard_sessions_revoked_at", "dashboard_sessions", ["revoked_at"])


def downgrade() -> None:
    op.drop_index("ix_dashboard_sessions_user_expires", table_name="dashboard_sessions")
    op.drop_index("ix_dashboard_sessions_user_revoked", table_name="dashboard_sessions")
    op.drop_index("ix_dashboard_sessions_revoked_by_user_id", table_name="dashboard_sessions")
    op.drop_index("ix_dashboard_sessions_step_up_until", table_name="dashboard_sessions")
    op.drop_index("ix_dashboard_sessions_expires_at", table_name="dashboard_sessions")
    op.drop_index("ix_dashboard_sessions_revoked_at", table_name="dashboard_sessions")
    op.drop_constraint("uq_dashboard_sessions_session_hash", "dashboard_sessions", type_="unique")
    op.drop_index("ix_dashboard_sessions_user_id", table_name="dashboard_sessions")
    op.drop_table("dashboard_sessions")
    op.drop_constraint("ck_users_valid_role", "users")
    op.drop_index("ix_users_role", table_name="users")
    op.drop_column("users", "is_disabled")
    op.drop_column("users", "role")
