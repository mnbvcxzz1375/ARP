"""Add revoked_at column to api_keys.

Revision ID: 0010_add_api_key_revoked_at
Revises: 0009_phase_web_1_rbac_sessions
Create Date: 2026-05-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0010_add_api_key_revoked_at"
down_revision: Union[str, None] = "0009_phase_web_1_rbac_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "api_keys",
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("api_keys", "revoked_at")
