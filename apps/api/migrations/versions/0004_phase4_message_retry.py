"""Phase 4: retry_count, next_retry_at, max_retries, ttl_seconds, priority on messages.

Revision ID: 0004_phase4_message_retry
Revises: 0003_phase3_task_message
Create Date: 2026-05-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_phase4_message_retry"
down_revision: Union[str, None] = "0003_phase3_task_message"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("messages", sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"))
    op.add_column("messages", sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("messages", sa.Column("ttl_seconds", sa.Integer(), nullable=True))
    op.add_column("messages", sa.Column("priority", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("messages", "priority")
    op.drop_column("messages", "ttl_seconds")
    op.drop_column("messages", "next_retry_at")
    op.drop_column("messages", "max_retries")
    op.drop_column("messages", "retry_count")
