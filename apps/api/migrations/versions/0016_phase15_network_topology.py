"""Phase 15: Network Topology - Scopes and Zones.

Revision ID: 0016_phase15_network_topology
Revises: 0015_add_lease_id
Create Date: 2026-05-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0016_phase15_network_topology"
down_revision: Union[str, None] = "0015_add_lease_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create network_scopes table
    op.create_table(
        "network_scopes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope_name", sa.String(128), nullable=False),
        sa.Column("scope_type", sa.String(32), nullable=False),
        sa.Column("network_cidr", sa.String(64), nullable=True),
        sa.Column("agent_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False, server_default="{}"),
        sa.Column("zone_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_network_scopes_user_id", "network_scopes", ["user_id"])
    op.create_index("ix_network_scopes_scope_type", "network_scopes", ["scope_type"])

    # Create network_zones table
    op.create_table(
        "network_zones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("zone_name", sa.String(128), nullable=False),
        sa.Column("zone_type", sa.String(32), nullable=False),
        sa.Column("parent_zone_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("relay_node_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False, server_default="{}"),
        sa.Column("zone_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["scope_id"], ["network_scopes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_zone_id"], ["network_zones.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_network_zones_scope_id", "network_zones", ["scope_id"])
    op.create_index("ix_network_zones_zone_type", "network_zones", ["zone_type"])
    op.create_index("ix_network_zones_parent_zone_id", "network_zones", ["parent_zone_id"])


def downgrade() -> None:
    # Drop network_zones table
    op.drop_index("ix_network_zones_parent_zone_id", "network_zones")
    op.drop_index("ix_network_zones_zone_type", "network_zones")
    op.drop_index("ix_network_zones_scope_id", "network_zones")
    op.drop_table("network_zones")

    # Drop network_scopes table
    op.drop_index("ix_network_scopes_scope_type", "network_scopes")
    op.drop_index("ix_network_scopes_user_id", "network_scopes")
    op.drop_table("network_scopes")
