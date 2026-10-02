"""agents.public_keys: E2EE trust-root column.

Adds a nullable JSONB column holding an agent's published composite
public keys: {"kem": <base64 X25519>, "sig": <base64 Ed25519>, "v": 1}.
NULL for legacy agents — they cannot receive e2ee traffic, which the
connection negotiation path rejects with 400.

Revision ID: 0031
Revises: 0030
Create Date: 2026-10-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0031_agent_public_keys"
down_revision = "0030_username_non_unique"
branch_labels = None
depends_on = None

TABLE_NAME = "agents"
COLUMN_NAME = "public_keys"


def upgrade() -> None:
    op.add_column(
        TABLE_NAME,
        sa.Column(
            COLUMN_NAME,
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(TABLE_NAME, COLUMN_NAME)
