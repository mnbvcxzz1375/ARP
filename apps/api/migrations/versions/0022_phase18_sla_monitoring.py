"""Phase 18: SLA monitoring and metrics

Revision ID: 0022_phase18_sla_monitoring
Revises: 0021_add_route_decision_topology
Create Date: 2026-05-22

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0022_phase18_sla_monitoring'
down_revision = '0021_add_route_decision_topology'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create sla_targets table
    op.create_table(
        'sla_targets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('scope_id', sa.String(128), nullable=False, index=True),
        sa.Column('target_name', sa.String(128), nullable=False),
        sa.Column('metric_type', sa.String(32), nullable=False, index=True),
        sa.Column('target_value', sa.Float(), nullable=False),
        sa.Column('warning_threshold', sa.Float(), nullable=False, server_default='0.9'),
        sa.Column('critical_threshold', sa.Float(), nullable=False, server_default='0.8'),
        sa.Column('measurement_window_seconds', sa.Integer(), nullable=False, server_default='300'),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true', index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Create sla_violations table
    op.create_table(
        'sla_violations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('target_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('violation_time', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('metric_value', sa.Float(), nullable=False),
        sa.Column('severity', sa.String(16), nullable=False, index=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolution_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['target_id'], ['sla_targets.id'], ondelete='CASCADE'),
    )

    # Create route_metrics table
    op.create_table(
        'route_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('route_decision_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('metric_time', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('latency_ms', sa.Integer(), nullable=False),
        sa.Column('success', sa.Boolean(), nullable=False, index=True),
        sa.Column('error_code', sa.String(64), nullable=True),
        sa.Column('relay_node_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('zone_id', sa.String(64), nullable=True, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['route_decision_id'], ['route_decisions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['relay_node_id'], ['relay_nodes.id'], ondelete='SET NULL'),
    )

    # Create time-series indexes for efficient metric queries
    op.create_index(
        'ix_route_metrics_time_success',
        'route_metrics',
        ['metric_time', 'success'],
    )
    op.create_index(
        'ix_route_metrics_zone_time',
        'route_metrics',
        ['zone_id', 'metric_time'],
    )
    op.create_index(
        'ix_sla_violations_target_resolved',
        'sla_violations',
        ['target_id', 'resolved_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_sla_violations_target_resolved', table_name='sla_violations')
    op.drop_index('ix_route_metrics_zone_time', table_name='route_metrics')
    op.drop_index('ix_route_metrics_time_success', table_name='route_metrics')
    op.drop_table('route_metrics')
    op.drop_table('sla_violations')
    op.drop_table('sla_targets')
