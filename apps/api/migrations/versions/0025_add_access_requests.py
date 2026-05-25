"""add access_requests table

Revision ID: 0025
Revises: 0024_add_agent_egress_gateway
Create Date: 2026-05-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0025_add_access_requests"
down_revision = "0024_add_agent_egress_gateway"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "access_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("applicant_name", sa.String(128), nullable=False),
        sa.Column("applicant_email", sa.String(256), nullable=False),
        sa.Column("organization", sa.String(256), nullable=True),
        sa.Column("requested_mode", sa.String(32), nullable=False),
        sa.Column("use_case", sa.String(1000), nullable=False),
        sa.Column("terms_acknowledged", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("review_notes", sa.String(1000), nullable=True),
        sa.Column("reviewed_by", sa.String(36), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("request_ip", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "requested_mode IN ('personal', 'enterprise')",
            name="ck_access_requests_valid_mode",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'expired')",
            name="ck_access_requests_valid_status",
        ),
    )
    op.create_index("ix_access_requests_applicant_email", "access_requests", ["applicant_email"])
    op.create_index("ix_access_requests_status", "access_requests", ["status"])
    op.create_index("ix_access_requests_email_mode", "access_requests", ["applicant_email", "requested_mode"])


def downgrade() -> None:
    op.drop_index("ix_access_requests_email_mode")
    op.drop_index("ix_access_requests_status")
    op.drop_index("ix_access_requests_applicant_email")
    op.drop_table("access_requests")