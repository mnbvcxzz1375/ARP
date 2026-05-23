"""phase17_dedicated_channels

Revision ID: 0019_phase17_dedicated_channels
Revises: 0018_phase15_route_policy
Create Date: 2026-05-22 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0019_phase17_dedicated_channels'
down_revision: Union[str, None] = '0018_phase15_route_policy'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create dedicated_channels table
    op.create_table(
        'dedicated_channels',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('scope_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('channel_name', sa.String(length=128), nullable=False),
        sa.Column('channel_type', sa.String(length=32), nullable=False),
        sa.Column('source_agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('target_agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('connection_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('encryption_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('bandwidth_mbps', sa.Float(), nullable=True),
        sa.Column('latency_target_ms', sa.Float(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['scope_id'], ['network_scopes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_agent_id'], ['agents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['target_agent_id'], ['agents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_dedicated_channels_channel_name'), 'dedicated_channels', ['channel_name'], unique=False)
    op.create_index(op.f('ix_dedicated_channels_channel_type'), 'dedicated_channels', ['channel_type'], unique=False)
    op.create_index(op.f('ix_dedicated_channels_scope_id'), 'dedicated_channels', ['scope_id'], unique=False)
    op.create_index(op.f('ix_dedicated_channels_source_agent_id'), 'dedicated_channels', ['source_agent_id'], unique=False)
    op.create_index(op.f('ix_dedicated_channels_target_agent_id'), 'dedicated_channels', ['target_agent_id'], unique=False)

    # Create channel_health_checks table
    op.create_table(
        'channel_health_checks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('channel_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('check_time', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('latency_ms', sa.Float(), nullable=True),
        sa.Column('packet_loss_percent', sa.Float(), nullable=True),
        sa.Column('bandwidth_mbps', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('error_message', sa.String(length=512), nullable=True),
        sa.ForeignKeyConstraint(['channel_id'], ['dedicated_channels.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_channel_health_checks_channel_id'), 'channel_health_checks', ['channel_id'], unique=False)
    op.create_index(op.f('ix_channel_health_checks_check_time'), 'channel_health_checks', ['check_time'], unique=False)
    op.create_index(op.f('ix_channel_health_checks_status'), 'channel_health_checks', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_channel_health_checks_status'), table_name='channel_health_checks')
    op.drop_index(op.f('ix_channel_health_checks_check_time'), table_name='channel_health_checks')
    op.drop_index(op.f('ix_channel_health_checks_channel_id'), table_name='channel_health_checks')
    op.drop_table('channel_health_checks')

    op.drop_index(op.f('ix_dedicated_channels_target_agent_id'), table_name='dedicated_channels')
    op.drop_index(op.f('ix_dedicated_channels_source_agent_id'), table_name='dedicated_channels')
    op.drop_index(op.f('ix_dedicated_channels_scope_id'), table_name='dedicated_channels')
    op.drop_index(op.f('ix_dedicated_channels_channel_type'), table_name='dedicated_channels')
    op.drop_index(op.f('ix_dedicated_channels_channel_name'), table_name='dedicated_channels')
    op.drop_table('dedicated_channels')
