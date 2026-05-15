"""Fix idempotency_key scope: global -> (created_by, assigned_to, key) composite.

Revision ID: 0008_fix_idempotency_scope
Revises: 0007_phase10_audit_logs
Create Date: 2026-05-15
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0008_fix_idempotency_scope"
down_revision: Union[str, None] = "0007_phase10_audit_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the global unique constraint on idempotency_key alone
    op.drop_constraint("uq_tasks_idempotency_key", "tasks", type_="unique")
    # Add composite unique constraint: (created_by, assigned_to, idempotency_key)
    op.create_unique_constraint(
        "uq_tasks_idempotency_key",
        "tasks",
        ["created_by", "assigned_to", "idempotency_key"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_tasks_idempotency_key", "tasks", type_="unique")
    op.create_unique_constraint(
        "uq_tasks_idempotency_key",
        "tasks",
        ["idempotency_key"],
    )
