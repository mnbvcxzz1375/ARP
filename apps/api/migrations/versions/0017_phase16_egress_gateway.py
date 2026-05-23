"""Phase 16: Egress Gateway foundation

Revision ID: 0017_phase16_egress_gateway
Revises: 0016_phase15_network_topology
Create Date: 2026-05-22

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0017_phase16_egress_gateway'
down_revision = '0016_phase15_network_topology'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create egress_gateways table
    op.create_table(
        'egress_gateways',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('scope_id', postgresql.UUID(as_uuid=True), nullable=False, comment='User/org scope'),
        sa.Column('gateway_name', sa.String(length=128), nullable=False),
        sa.Column('gateway_type', sa.String(length=32), nullable=False, comment='api/model/github/deployment/mcp'),
        sa.Column('domain_allowlist', postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment='Allowed domains/endpoints'),
        sa.Column('secret_store_ref', sa.String(length=256), nullable=True, comment='Reference to secret store (not the secret itself)'),
        sa.Column('rate_limit_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Rate limit rules per gateway'),
        sa.Column('cache_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Cache TTL and rules'),
        sa.Column('cost_tracking', sa.Boolean(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_egress_gateways_scope_id'), 'egress_gateways', ['scope_id'], unique=False)

    # Create egress_logs table
    op.create_table(
        'egress_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('gateway_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('request_type', sa.String(length=32), nullable=False, comment='GET/POST/PUT/DELETE/etc'),
        sa.Column('target_domain', sa.String(length=256), nullable=False),
        sa.Column('request_size_bytes', sa.Integer(), nullable=False),
        sa.Column('response_size_bytes', sa.Integer(), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('cost_estimate', sa.Integer(), nullable=True, comment='Cost in cents'),
        sa.Column('approval_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['approval_id'], ['approvals.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['gateway_id'], ['egress_gateways.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_egress_logs_agent_id'), 'egress_logs', ['agent_id'], unique=False)
    op.create_index(op.f('ix_egress_logs_created_at'), 'egress_logs', ['created_at'], unique=False)
    op.create_index(op.f('ix_egress_logs_gateway_id'), 'egress_logs', ['gateway_id'], unique=False)
    op.create_index(op.f('ix_egress_logs_target_domain'), 'egress_logs', ['target_domain'], unique=False)
    op.create_index(op.f('ix_egress_logs_task_id'), 'egress_logs', ['task_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_egress_logs_task_id'), table_name='egress_logs')
    op.drop_index(op.f('ix_egress_logs_target_domain'), table_name='egress_logs')
    op.drop_index(op.f('ix_egress_logs_gateway_id'), table_name='egress_logs')
    op.drop_index(op.f('ix_egress_logs_created_at'), table_name='egress_logs')
    op.drop_index(op.f('ix_egress_logs_agent_id'), table_name='egress_logs')
    op.drop_table('egress_logs')
    op.drop_index(op.f('ix_egress_gateways_scope_id'), table_name='egress_gateways')
    op.drop_table('egress_gateways')
