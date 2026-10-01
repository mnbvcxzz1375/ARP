"""add unique constraint on task_progress (task_id, seq)

Revision ID: 0027_unique_task_progress_seq
Revises: 0026_uq_pending_access_req
Create Date: 2026-09-30

Concurrent progress reports on the same task could both compute max(seq)+1
and insert duplicate seq values. The unique constraint makes the loser
retry instead of silently corrupting the progress order.
"""
from alembic import op

revision = "0027_unique_task_progress_seq"
down_revision = "0026_uq_pending_access_req"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_task_progress_task_seq",
        "task_progress",
        ["task_id", "seq"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_task_progress_task_seq", "task_progress")
