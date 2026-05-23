"""Add lease_id to route_decisions

Revision ID: 0015_add_lease_id
Revises: 0014_phase14_personal_routing
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0015_add_lease_id'
down_revision = '0014_phase14_personal_routing'
branch_labels = None
depends_on = None


def upgrade():
    # Add lease_id column to route_decisions
    op.add_column('route_decisions', sa.Column('lease_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_route_decisions_lease_id', 'route_decisions', 'route_leases', ['lease_id'], ['id'], ondelete='SET NULL')


def downgrade():
    op.drop_constraint('fk_route_decisions_lease_id', 'route_decisions', type_='foreignkey')
    op.drop_column('route_decisions', 'lease_id')
