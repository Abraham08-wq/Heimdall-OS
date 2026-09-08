"""
005_add_config_entries_and_device_fields.py
Adds the config_entries table and new columns to the devices table.
Previous revision: f44006ca44e4
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    # ── 1. Create config_entries table ────────────────────────────────────────
    op.create_table(
        'config_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('category', sa.String(64), nullable=False),
        sa.Column('key', sa.String(128), nullable=False),
        sa.Column('label', sa.String(256), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('value', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_config_entries_category', 'config_entries', ['category'])
    op.create_index('ix_config_entries_key', 'config_entries', ['key'])
    op.create_index('ix_config_entries_is_active', 'config_entries', ['is_active'])

    # ── 2. Add missing columns to devices table ───────────────────────────────
    # Core identification
    op.add_column('devices', sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('devices', sa.Column('hostname', sa.String(), nullable=True))
    op.add_column('devices', sa.Column('ip', sa.String(), nullable=True))
    op.add_column('devices', sa.Column('mac', sa.String(), nullable=True))

    # Categorisation
    op.add_column('devices', sa.Column('os', sa.String(), nullable=True))
    op.add_column('devices', sa.Column('department', sa.String(), nullable=True))
    op.add_column('devices', sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    # Posture / risk
    op.add_column('devices', sa.Column('risk_score', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('devices', sa.Column('status', sa.String(), nullable=False, server_default='online'))

    # Discovery data
    op.add_column('devices', sa.Column('ports', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('devices', sa.Column('services', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('devices', sa.Column('cves', postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    # Timestamps
    op.add_column('devices', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()))

    # Indexes on new columns
    op.create_index('ix_devices_hostname', 'devices', ['hostname'])
    op.create_index('ix_devices_ip', 'devices', ['ip'])
    op.create_index('ix_devices_mac', 'devices', ['mac'])
    op.create_index('ix_devices_risk_score', 'devices', ['risk_score'])
    op.create_index('ix_devices_status', 'devices', ['status'])

    # FK to tenants (optional — skip if tenants table doesn't exist yet)
    try:
        op.create_foreign_key(
            'fk_devices_tenant_id',
            'devices', 'tenants',
            ['tenant_id'], ['id'],
        )
    except Exception:
        pass  # Graceful skip if tenants table isn't available


def downgrade():
    # Reverse device columns
    for col in ['created_at', 'cves', 'services', 'ports', 'status', 'risk_score',
                'tags', 'department', 'os', 'mac', 'ip', 'hostname', 'tenant_id']:
        try:
            op.drop_column('devices', col)
        except Exception:
            pass

    # Reverse config_entries
    op.drop_index('ix_config_entries_is_active', table_name='config_entries')
    op.drop_index('ix_config_entries_key', table_name='config_entries')
    op.drop_index('ix_config_entries_category', table_name='config_entries')
    op.drop_table('config_entries')
