"""Phase 15: Route Policy - Enterprise routing policies.

Revision ID: 0018_phase15_route_policy
Revises: 0017_phase16_egress_gateway
Create Date: 2026-05-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0018_phase15_route_policy"
down_revision: Union[str, None] = "0017_phase16_egress_gateway"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create route_policies table
    op.create_table(
        "route_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("policy_name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("source_zone_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_zone_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("allowed_route_types", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("denied_route_types", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("require_approval", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("risk_level", sa.String(16), nullable=True),
        sa.Column("data_boundary_rules", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        # Foreign keys are optional to allow policies without scope/zone constraints
        # When scope/zone models are available, these will reference them
    )

    # Create indexes for efficient policy lookup
    op.create_index("ix_route_policies_scope_id", "route_policies", ["scope_id"])
    op.create_index("ix_route_policies_priority", "route_policies", ["priority"])
    op.create_index("ix_route_policies_enabled", "route_policies", ["enabled"])
    op.create_index("ix_route_policies_source_zone_id", "route_policies", ["source_zone_id"])
    op.create_index("ix_route_policies_target_zone_id", "route_policies", ["target_zone_id"])

    # Composite index for common query pattern: scope + enabled + priority
    op.create_index(
        "ix_route_policies_scope_enabled_priority",
        "route_policies",
        ["scope_id", "enabled", "priority"],
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_route_policies_scope_enabled_priority", "route_policies")
    op.drop_index("ix_route_policies_target_zone_id", "route_policies")
    op.drop_index("ix_route_policies_source_zone_id", "route_policies")
    op.drop_index("ix_route_policies_enabled", "route_policies")
    op.drop_index("ix_route_policies_priority", "route_policies")
    op.drop_index("ix_route_policies_scope_id", "route_policies")

    # Drop table
    op.drop_table("route_policies")
