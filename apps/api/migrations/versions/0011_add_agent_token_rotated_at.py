"""Add rotated_at column to agent_tokens.

Revision ID: 0011_add_agent_token_rotated_at
Revises: 0010_add_api_key_revoked_at
Create Date: 2026-05-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0011_add_agent_token_rotated_at"
down_revision: Union[str, None] = "0010_add_api_key_revoked_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agent_tokens",
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_tokens", "rotated_at")
