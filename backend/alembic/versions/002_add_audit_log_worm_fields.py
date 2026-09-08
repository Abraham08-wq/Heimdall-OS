"""add_audit_log_worm_fields

Revision ID: 002_add_audit_log_worm_fields
Revises: 001_add_devices_table
Create Date: 2026-02-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.

revision = '002'
down_revision = '001'
def upgrade() -> None:
    op.add_column('audit_logs', sa.Column('hash', sa.String(), nullable=True))
    op.add_column('audit_logs', sa.Column('previous_hash', sa.String(), nullable=True))
    op.add_column('audit_logs', sa.Column('signature', sa.String(), nullable=True))
    op.create_index(op.f('ix_audit_logs_hash'), 'audit_logs', ['hash'], unique=False)
    op.create_index(op.f('ix_audit_logs_previous_hash'), 'audit_logs', ['previous_hash'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_audit_logs_previous_hash'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_hash'), table_name='audit_logs')
    op.drop_column('audit_logs', 'signature')
    op.drop_column('audit_logs', 'previous_hash')
    op.drop_column('audit_logs', 'hash')
