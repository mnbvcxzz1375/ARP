"""add user preferences (locale, preferences JSONB)

Revision ID: 0028_user_preferences
Revises: 0027_unique_task_progress_seq
Create Date: 2026-09-30

The console needs to persist per-user appearance and locale settings
server-side so they survive logouts and device switches. locale is a
nullable String(16) (unset users fall back to the client default);
preferences stores the appearance payload as JSONB, defaulting to '{}'.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0028_user_preferences"
down_revision = "0027_unique_task_progress_seq"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("locale", sa.String(16), nullable=True))
    op.add_column(
        "users",
        sa.Column("preferences", JSONB(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("users", "preferences")
    op.drop_column("users", "locale")
