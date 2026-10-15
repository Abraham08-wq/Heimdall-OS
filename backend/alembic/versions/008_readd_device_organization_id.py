"""re-add organization_id to devices as optional grouping under Organization

Revision ID: 008
Revises: 007
Create Date: 2026-09-26

Context: 007 dropped devices.organization_id when Organization was thought
to be tenant-direct-only with no relation to Device. It turns out the
existing devices.py (list filter ?organization_id=..., device_count on
organizations) already depends on Devices optionally grouping under an
Organization. This migration re-adds it, nullable -- a Device can still be
standalone under just a Tenant, or additionally grouped under an
Organization. Both Device and Organization continue to belong directly to
Tenant independently; Organization is not required to have any Devices.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("devices", sa.Column(
        "organization_id", postgresql.UUID(as_uuid=True),
        sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True,
    ))
    op.create_index("ix_devices_organization_id", "devices", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_devices_organization_id", table_name="devices")
    op.drop_column("devices", "organization_id")