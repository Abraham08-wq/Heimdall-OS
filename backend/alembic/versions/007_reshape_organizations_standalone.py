"""reshape organizations to standalone tenant-owned asset, add organization_commands

Revision ID: 007
Revises: 006
Create Date: 2026-09-26

Context: migration 006 created `organizations` with an old shape (name,
contact_name, contact_email, legal_agreement_* , notes) back when it was
still overlapping with Tenant, and linked `devices.organization_id` ->
organizations.id. That overlap was resolved by moving the contact/legal
fields onto Tenant instead. Organization is now re-purposed as its own
first-class, tenant-owned, agent-monitored asset type -- a PARALLEL sibling
to Device under Tenant, not a parent of Device. This migration:
  1. Drops devices.organization_id (Device no longer nests under Organization).
  2. Drops the now-redundant contact/legal columns from organizations
     (duplicated on Tenant already).
  3. Adds the new Organization columns: tenant_id, owner_id, domain,
     industry, risk_score, status, and the sensor-agent fields.
  4. Creates organization_commands, mirroring device_commands.

NOTE ON DATA LOSS: step 2 drops contact_name / contact_email /
legal_agreement_signed_at / legal_agreement_reference from `organizations`.
If any real data was ever written to those columns (unlikely, since the
table was only just introduced in 006), it will be lost on upgrade. The
downgrade() below recreates the columns (nullable) but cannot restore the
data. If you need to preserve it, copy it over to the matching Tenant row(s)
manually before running this upgrade.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Devices no longer nest under Organization ─────────────────────────
    op.drop_index("ix_devices_organization_id", table_name="devices")
    op.drop_column("devices", "organization_id")

    # ── 2. Drop the old, now-redundant contact/legal columns on organizations
    op.drop_column("organizations", "contact_name")
    op.drop_column("organizations", "contact_email")
    op.drop_column("organizations", "legal_agreement_signed_at")
    op.drop_column("organizations", "legal_agreement_reference")

    # ── 3. Reshape organizations into the new standalone, tenant-owned,
    #        agent-monitored asset type ────────────────────────────────────
    op.add_column("organizations", sa.Column(
        "tenant_id", postgresql.UUID(as_uuid=True),
        sa.ForeignKey("tenants.id"), nullable=True,
    ))
    op.create_index("ix_organizations_tenant_id", "organizations", ["tenant_id"])

    op.add_column("organizations", sa.Column(
        "owner_id", postgresql.UUID(as_uuid=True),
        sa.ForeignKey("users.id"), nullable=True,
    ))

    op.create_index("ix_organizations_name", "organizations", ["name"])

    op.add_column("organizations", sa.Column("domain", sa.String(), nullable=True))
    op.create_index("ix_organizations_domain", "organizations", ["domain"])

    op.add_column("organizations", sa.Column("industry", sa.String(), nullable=True))
    # `notes` already exists from 006 with the same meaning/type -- left untouched.

    op.add_column("organizations", sa.Column(
        "risk_score", sa.Integer(), nullable=False, server_default="0",
    ))
    op.create_index("ix_organizations_risk_score", "organizations", ["risk_score"])

    op.add_column("organizations", sa.Column(
        "status", sa.String(), nullable=False, server_default="online",
    ))
    op.create_index("ix_organizations_status", "organizations", ["status"])

    # Sensor agent fields -- server/network-level install, mirrors Device's
    # agent fields (see devices.agent_secret_hash etc. from migration 006).
    op.add_column("organizations", sa.Column("agent_secret_hash", sa.String(), nullable=True))
    op.add_column("organizations", sa.Column("agent_enrolled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("organizations", sa.Column("last_heartbeat", sa.DateTime(timezone=True), nullable=True))
    op.add_column("organizations", sa.Column(
        "deployment_mode", sa.String(), nullable=False, server_default="gateway",
        comment="organizations default to gateway-style install (whole network), unlike a single endpoint",
    ))

    # `name` was already NOT NULL from 006 -- leave as-is.
    # `created_at` was already present from 006 -- leave as-is.

    # ── 4. organization_commands: mirrors device_commands exactly ───────────
    op.create_table(
        "organization_commands",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(), nullable=False,
                  comment="e.g. isolate, unisolate, collect_logs -- extend as needed"),
        sa.Column("params", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending",
                  comment="pending | delivered | completed | failed"),
        sa.Column("issued_by", postgresql.UUID(as_uuid=True), nullable=True,
                  comment="The human user (current_user.id) who queued the action"),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_organization_commands_org_id_status", "organization_commands",
                     ["organization_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_organization_commands_org_id_status", table_name="organization_commands")
    op.drop_table("organization_commands")

    op.drop_column("organizations", "deployment_mode")
    op.drop_column("organizations", "last_heartbeat")
    op.drop_column("organizations", "agent_enrolled_at")
    op.drop_column("organizations", "agent_secret_hash")

    op.drop_index("ix_organizations_status", table_name="organizations")
    op.drop_column("organizations", "status")

    op.drop_index("ix_organizations_risk_score", table_name="organizations")
    op.drop_column("organizations", "risk_score")

    op.drop_index("ix_organizations_domain", table_name="organizations")
    op.drop_column("organizations", "domain")

    op.drop_column("organizations", "industry")

    op.drop_index("ix_organizations_name", table_name="organizations")

    op.drop_column("organizations", "owner_id")

    op.drop_index("ix_organizations_tenant_id", table_name="organizations")
    op.drop_column("organizations", "tenant_id")

    # Recreate the old contact/legal columns (structure only -- data is gone)
    op.add_column("organizations", sa.Column("legal_agreement_reference", sa.String(), nullable=True))
    op.add_column("organizations", sa.Column("legal_agreement_signed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("organizations", sa.Column("contact_email", sa.String(), nullable=True))
    op.add_column("organizations", sa.Column("contact_name", sa.String(), nullable=True))

    op.add_column("devices", sa.Column(
        "organization_id", postgresql.UUID(as_uuid=True),
        sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True,
    ))
    op.create_index("ix_devices_organization_id", "devices", ["organization_id"])