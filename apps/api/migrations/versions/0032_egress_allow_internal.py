"""egress_gateways.allow_internal_egress: default-deny opt-in for internal targets.

Adds a non-nullable boolean (default false). The egress policy decision
point in egress_service.proxy_external_request denies requests whose
target host is loopback/private/reserved/link-local, or that fall inside
the gateway scope's network_cidr, unless this flag is explicitly set.
Default false preserves the default-deny baseline for existing rows
(server_default=false backfills them).

Merge discipline (serialized chain): M4 pins down_revision to
0031_agent_public_keys, which is created by module
m1-key-model-and-ciphertext-schema. M1 MUST be merged before M4. Do not
re-pin 0031/0032 to 0030 in parallel branches — that produces two heads
and breaks `alembic upgrade head` at merge time. If M4 lands first for
any reason, 0031 must keep down_revision pointing at 0030 and this
revision stays directly on top of it.

Revision ID: 0032
Revises: 0031
Create Date: 2026-10-01
"""

from alembic import op
import sqlalchemy as sa

revision = "0032_egress_allow_internal"
down_revision = "0031_agent_public_keys"
branch_labels = None
depends_on = None

TABLE_NAME = "egress_gateways"
COLUMN_NAME = "allow_internal_egress"


def upgrade() -> None:
    op.add_column(
        TABLE_NAME,
        sa.Column(
            COLUMN_NAME,
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column(TABLE_NAME, COLUMN_NAME)
