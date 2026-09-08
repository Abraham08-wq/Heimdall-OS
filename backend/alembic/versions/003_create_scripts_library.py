# Revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'  # Adjust this if your previous migration file has a different ID
branch_labels = None
depends_on = None
"""
Database migration to create scripts_library table.

This migration creates the PostgreSQL table for storing scripts
with their metadata, versions, and approval status.

Run with: alembic upgrade head
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    """Create scripts_library table."""
    op.create_table(
        'scripts_library',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('language', sa.String(50), nullable=False),
        sa.Column('code', sa.Text, nullable=False),
        sa.Column('metadata', postgresql.JSON, nullable=False),
        sa.Column('version', sa.Float, server_default='1.0'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('created_by', sa.String(255), nullable=True),
        sa.Column('is_approved', sa.Boolean, server_default='false'),
        sa.Column('is_disabled', sa.Boolean, server_default='false'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indices for common queries
    op.create_index('idx_scripts_name', 'scripts_library', ['name'])
    op.create_index('idx_scripts_language', 'scripts_library', ['language'])
    op.create_index('idx_scripts_is_approved', 'scripts_library', ['is_approved'])
    op.create_index('idx_scripts_created_at', 'scripts_library', ['created_at'])


def downgrade():
    """Drop scripts_library table."""
    op.drop_index('idx_scripts_created_at')
    op.drop_index('idx_scripts_is_approved')
    op.drop_index('idx_scripts_language')
    op.drop_index('idx_scripts_name')
    op.drop_table('scripts_library')
