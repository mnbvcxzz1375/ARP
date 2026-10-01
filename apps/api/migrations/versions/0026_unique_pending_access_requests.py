"""add partial unique index on pending access requests

Revision ID: 0026_uq_pending_access_req
Revises: 0025_add_access_requests
Create Date: 2026-09-30

Enforces at-most-one pending request per (applicant_email, requested_mode),
closing the check-then-act race in create_access_request where two
concurrent submissions both passed the SELECT check and both inserted.
"""
from alembic import op

revision = "0026_uq_pending_access_req"
down_revision = "0025_add_access_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_access_requests_pending_email_mode",
        "access_requests",
        ["applicant_email", "requested_mode"],
        unique=True,
        postgresql_where=op.f("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("uq_access_requests_pending_email_mode", table_name="access_requests")
