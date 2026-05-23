"""Phase 14: Personal Mode with Local-first Routing.

Revision ID: 0014_phase14_personal_routing
Revises: 0012_phase12_routing_foundation
Create Date: 2026-05-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0014_phase14_personal_routing"
down_revision: Union[str, None] = "0012_phase12_routing_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create personal_scopes table
    op.create_table(
        "personal_scopes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("scope_name", sa.String(64), nullable=False, server_default="personal"),
        sa.Column("default_relay_type", sa.String(32), nullable=False, server_default="central_relay"),
        sa.Column("enable_edge_relay", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("enable_secure_channel", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_personal_scopes_user_id", "personal_scopes", ["user_id"])

    # Add network_info to relay_nodes
    op.add_column(
        "relay_nodes",
        sa.Column("network_info", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
    )

    # Add timeliness mode fields to tasks
    op.add_column(
        "tasks",
        sa.Column("timeliness_mode", sa.String(16), nullable=False, server_default="normal"),
    )
    op.add_column(
        "tasks",
        sa.Column("ttl_seconds", sa.Integer(), nullable=True),
    )
    op.add_column(
        "tasks",
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tasks",
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "tasks",
        sa.Column("max_retry_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "tasks",
        sa.Column("retry_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "tasks",
        sa.Column("route_policy_hint", sa.String(64), nullable=True),
    )

    # Create index on timeliness_mode for query performance
    op.create_index("ix_tasks_timeliness_mode", "tasks", ["timeliness_mode"])


def downgrade() -> None:
    # Drop task columns
    op.drop_index("ix_tasks_timeliness_mode", "tasks")
    op.drop_column("tasks", "route_policy_hint")
    op.drop_column("tasks", "retry_policy")
    op.drop_column("tasks", "max_retry_count")
    op.drop_column("tasks", "priority")
    op.drop_column("tasks", "deadline_at")
    op.drop_column("tasks", "ttl_seconds")
    op.drop_column("tasks", "timeliness_mode")

    # Drop relay_nodes column
    op.drop_column("relay_nodes", "network_info")

    # Drop personal_scopes table
    op.drop_table("personal_scopes")
