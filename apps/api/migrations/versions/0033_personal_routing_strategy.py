"""personal_scopes.routing_strategy: per-user routing strategy.

Adds a non-nullable String(16) column with server_default='normal'.
Existing rows are backfilled by the server default (no data migration
needed). Allowed values: 'fast' | 'normal' | 'reliable'.

The strategy is a scoring-layer override only (see
RouteCandidate.compute_final_score and select_route in
app.services.path_optimizer):
- normal: identity transform (unchanged weights)
- fast: rank candidates purely by latency (the 7 non-latency weights,
  including security_score, are zeroed)
- reliable: favor delivery success (success/failure weights x1.5,
  latency weight x0.5) plus a strict health gate that excludes
  'degraded' relays from candidacy

The hard filter chain (_get_healthy_relays: status/60s heartbeat
window/circuit breaker) and the fail-closed security-mode negotiation
(connection_service.negotiate_security_mode) are untouched.

Serialized chain: directly on top of 0032_egress_allow_internal.

Revision ID: 0033_personal_routing_strategy
Revises: 0032_egress_allow_internal
Create Date: 2026-10-02
"""

from alembic import op
import sqlalchemy as sa

revision = "0033_personal_routing_strategy"
down_revision = "0032_egress_allow_internal"
branch_labels = None
depends_on = None

TABLE_NAME = "personal_scopes"
COLUMN_NAME = "routing_strategy"


def upgrade() -> None:
    op.add_column(
        TABLE_NAME,
        sa.Column(
            COLUMN_NAME,
            sa.String(16),
            nullable=False,
            server_default="normal",
        ),
    )


def downgrade() -> None:
    op.drop_column(TABLE_NAME, COLUMN_NAME)
