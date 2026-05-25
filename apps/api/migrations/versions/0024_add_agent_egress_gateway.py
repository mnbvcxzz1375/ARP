"""Add egress_gateway_id to agents table.

Revision ID: 0024_add_agent_egress_gateway
Revises: 0023_phase18_business_continuity
Create Date: 2026-05-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0024_add_agent_egress_gateway"
down_revision: Union[str, None] = "0023_phase18_business_continuity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column("egress_gateway_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_agents_egress_gateway_id",
        "agents",
        "egress_gateways",
        ["egress_gateway_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_agents_egress_gateway_id",
        "agents",
        ["egress_gateway_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_agents_egress_gateway_id", "agents")
    op.drop_constraint("fk_agents_egress_gateway_id", "agents", type_="foreignkey")
    op.drop_column("agents", "egress_gateway_id")