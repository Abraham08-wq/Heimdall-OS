"""add_execution_nodes_table

Revision ID: 004
Revises: 003
Create Date: 2026-04-14 12:40:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'execution_nodes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenants.id'), index=True, nullable=False),
        sa.Column('name', sa.String(), index=True),
        sa.Column('api_key_hash', sa.String(), unique=True, index=True),
        sa.Column('is_online', sa.Boolean(), default=False),
        sa.Column('last_ping', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )

def downgrade():
    op.drop_table('execution_nodes')
