"""initial empty schema

Revision ID: 0001_initial_empty
Revises:
Create Date: 2026-05-14 11:45:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001_initial_empty"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("SELECT 1")


def downgrade() -> None:
    op.execute("SELECT 1")

