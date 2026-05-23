"""Add topology and policy tracking to route_decisions.

Revision ID: 0021_add_route_decision_topology
Revises: 0020_add_agent_scope_zone
Create Date: 2026-05-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0021_add_route_decision_topology"
down_revision: Union[str, None] = "0020_add_agent_scope_zone"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add topology and policy tracking columns to route_decisions
    op.add_column(
        "route_decisions",
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column(
        "route_decisions",
        sa.Column("source_zone_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column(
        "route_decisions",
        sa.Column("target_zone_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column(
        "route_decisions",
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), nullable=True)
    )

    # Add foreign key constraints
    op.create_foreign_key(
        "fk_route_decisions_scope_id",
        "route_decisions",
        "network_scopes",
        ["scope_id"],
        ["id"],
        ondelete="SET NULL"
    )
    op.create_foreign_key(
        "fk_route_decisions_source_zone_id",
        "route_decisions",
        "network_zones",
        ["source_zone_id"],
        ["id"],
        ondelete="SET NULL"
    )
    op.create_foreign_key(
        "fk_route_decisions_target_zone_id",
        "route_decisions",
        "network_zones",
        ["target_zone_id"],
        ["id"],
        ondelete="SET NULL"
    )
    op.create_foreign_key(
        "fk_route_decisions_policy_id",
        "route_decisions",
        "route_policies",
        ["policy_id"],
        ["id"],
        ondelete="SET NULL"
    )

    # Add indexes for efficient lookups
    op.create_index("ix_route_decisions_scope_id", "route_decisions", ["scope_id"])
    op.create_index("ix_route_decisions_source_zone_id", "route_decisions", ["source_zone_id"])
    op.create_index("ix_route_decisions_target_zone_id", "route_decisions", ["target_zone_id"])
    op.create_index("ix_route_decisions_policy_id", "route_decisions", ["policy_id"])


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_route_decisions_policy_id", "route_decisions")
    op.drop_index("ix_route_decisions_target_zone_id", "route_decisions")
    op.drop_index("ix_route_decisions_source_zone_id", "route_decisions")
    op.drop_index("ix_route_decisions_scope_id", "route_decisions")

    # Drop foreign key constraints
    op.drop_constraint("fk_route_decisions_policy_id", "route_decisions", type_="foreignkey")
    op.drop_constraint("fk_route_decisions_target_zone_id", "route_decisions", type_="foreignkey")
    op.drop_constraint("fk_route_decisions_source_zone_id", "route_decisions", type_="foreignkey")
    op.drop_constraint("fk_route_decisions_scope_id", "route_decisions", type_="foreignkey")

    # Drop columns
    op.drop_column("route_decisions", "policy_id")
    op.drop_column("route_decisions", "target_zone_id")
    op.drop_column("route_decisions", "source_zone_id")
    op.drop_column("route_decisions", "scope_id")
