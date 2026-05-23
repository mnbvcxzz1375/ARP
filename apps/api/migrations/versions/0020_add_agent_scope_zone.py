"""Add scope_id and zone_id to agents table.

Revision ID: 0020_add_agent_scope_zone
Revises: 0019_phase17_dedicated_channels
Create Date: 2026-05-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0020_add_agent_scope_zone"
down_revision: Union[str, None] = "0019_phase17_dedicated_channels"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add scope_id and zone_id to agents table
    op.add_column(
        "agents",
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column(
        "agents",
        sa.Column("zone_id", postgresql.UUID(as_uuid=True), nullable=True)
    )

    # Add foreign key constraints
    op.create_foreign_key(
        "fk_agents_scope_id",
        "agents",
        "network_scopes",
        ["scope_id"],
        ["id"],
        ondelete="SET NULL"
    )
    op.create_foreign_key(
        "fk_agents_zone_id",
        "agents",
        "network_zones",
        ["zone_id"],
        ["id"],
        ondelete="SET NULL"
    )

    # Add indexes for efficient lookups
    op.create_index("ix_agents_scope_id", "agents", ["scope_id"])
    op.create_index("ix_agents_zone_id", "agents", ["zone_id"])


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_agents_zone_id", "agents")
    op.drop_index("ix_agents_scope_id", "agents")

    # Drop foreign key constraints
    op.drop_constraint("fk_agents_zone_id", "agents", type_="foreignkey")
    op.drop_constraint("fk_agents_scope_id", "agents", type_="foreignkey")

    # Drop columns
    op.drop_column("agents", "zone_id")
    op.drop_column("agents", "scope_id")
