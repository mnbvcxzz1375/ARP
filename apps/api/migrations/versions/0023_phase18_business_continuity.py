"""0023_phase18_business_continuity

Revision ID: 0023_phase18_business_continuity
Revises: 0022_phase18_sla_monitoring
Create Date: 2026-05-22 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0023_phase18_business_continuity'
down_revision: Union[str, None] = '0022_phase18_sla_monitoring'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create failover_configs table
    op.create_table(
        'failover_configs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('scope_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('primary_relay_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('backup_relay_ids', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('failover_threshold_seconds', sa.Integer(), nullable=False),
        sa.Column('auto_failover_enabled', sa.Boolean(), nullable=False),
        sa.Column('manual_approval_required', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_failover_configs_scope_id'), 'failover_configs', ['scope_id'], unique=False)
    op.create_index(op.f('ix_failover_configs_primary_relay_id'), 'failover_configs', ['primary_relay_id'], unique=False)

    # Create failover_events table
    op.create_table(
        'failover_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('config_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('trigger_reason', sa.Text(), nullable=False),
        sa.Column('from_relay_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('to_relay_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('affected_task_count', sa.Integer(), nullable=False),
        sa.Column('auto_triggered', sa.Boolean(), nullable=False),
        sa.Column('approval_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rollback_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['config_id'], ['failover_configs.id'], ),
        sa.ForeignKeyConstraint(['approval_id'], ['approvals.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_failover_events_config_id'), 'failover_events', ['config_id'], unique=False)
    op.create_index(op.f('ix_failover_events_event_time'), 'failover_events', ['event_time'], unique=False)
    op.create_index(op.f('ix_failover_events_from_relay_id'), 'failover_events', ['from_relay_id'], unique=False)
    op.create_index(op.f('ix_failover_events_to_relay_id'), 'failover_events', ['to_relay_id'], unique=False)
    op.create_index(op.f('ix_failover_events_status'), 'failover_events', ['status'], unique=False)

    # Create circuit_breakers table
    op.create_table(
        'circuit_breakers',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('relay_node_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('state', sa.String(length=16), nullable=False),
        sa.Column('failure_count', sa.Integer(), nullable=False),
        sa.Column('last_failure_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('open_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('success_threshold', sa.Integer(), nullable=False),
        sa.Column('failure_threshold', sa.Integer(), nullable=False),
        sa.Column('success_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['relay_node_id'], ['relay_nodes.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('relay_node_id')
    )
    op.create_index(op.f('ix_circuit_breakers_relay_node_id'), 'circuit_breakers', ['relay_node_id'], unique=True)
    op.create_index(op.f('ix_circuit_breakers_state'), 'circuit_breakers', ['state'], unique=False)
    op.create_index(op.f('ix_circuit_breakers_open_until'), 'circuit_breakers', ['open_until'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_circuit_breakers_open_until'), table_name='circuit_breakers')
    op.drop_index(op.f('ix_circuit_breakers_state'), table_name='circuit_breakers')
    op.drop_index(op.f('ix_circuit_breakers_relay_node_id'), table_name='circuit_breakers')
    op.drop_table('circuit_breakers')

    op.drop_index(op.f('ix_failover_events_status'), table_name='failover_events')
    op.drop_index(op.f('ix_failover_events_to_relay_id'), table_name='failover_events')
    op.drop_index(op.f('ix_failover_events_from_relay_id'), table_name='failover_events')
    op.drop_index(op.f('ix_failover_events_event_time'), table_name='failover_events')
    op.drop_index(op.f('ix_failover_events_config_id'), table_name='failover_events')
    op.drop_table('failover_events')

    op.drop_index(op.f('ix_failover_configs_primary_relay_id'), table_name='failover_configs')
    op.drop_index(op.f('ix_failover_configs_scope_id'), table_name='failover_configs')
    op.drop_table('failover_configs')
