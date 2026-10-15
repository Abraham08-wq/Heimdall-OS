"""add organizations, sensor agent auth, and device command queue

Revision ID: REPLACE_WITH_NEW_ID
Revises: REPLACE_WITH_YOUR_CURRENT_HEAD
Create Date: 2026-09-25

HOW TO FILL IN THE TWO IDs ABOVE, AND THE FILENAME:
    docker compose exec backend alembic heads
This prints your current head revision ID. Put that value into `down_revision`
below. Then generate a real revision id for THIS file (any unique string works,
but the alembic-generated style is a 12-char hex, e.g. via
`python3 -c "import uuid; print(uuid.uuid4().hex[:12])"`) and put it in both
`revision` below AND rename this file to
    <that_same_id>_add_organizations_and_sensor_agent.py
so Alembic's filename-based ordering matches its internal revision graph.
I can't safely guess your current head from here — guessing wrong would
silently corrupt your migration history.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# --- EDIT THESE TWO LINES (see instructions above) --------------------------
revision = "006"
down_revision = "005"
# -----------------------------------------------------------------------------
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Organizations: the entity a device/server-room install belongs to ────
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("contact_name", sa.String(), nullable=True),
        sa.Column("contact_email", sa.String(), nullable=True),
        # ADDED per the explicit requirement that installs only happen after a
        # signed legal agreement -- this is queryable, not just a comment.
        sa.Column("legal_agreement_signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("legal_agreement_reference", sa.String(), nullable=True,
                  comment="Contract/document ID or link, for audit purposes"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ── devices: link to organizations, and everything the sensor agent needs ─
    op.add_column("devices", sa.Column(
        "organization_id", postgresql.UUID(as_uuid=True),
        sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True,
    ))
    op.create_index("ix_devices_organization_id", "devices", ["organization_id"])

    # Sensor agent auth: a per-device secret, stored HASHED (never plaintext),
    # checked by the new /sensor endpoints -- entirely separate from human JWT
    # auth (see backend/app/api/agent_deps.py).
    op.add_column("devices", sa.Column("agent_secret_hash", sa.String(), nullable=True))
    op.add_column("devices", sa.Column("agent_enrolled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("devices", sa.Column("last_heartbeat", sa.DateTime(timezone=True), nullable=True))
    # Deployment mode distinguishes a single-endpoint install (one phone/laptop)
    # from a server-room install acting as an internal-network gateway, per the
    # "protect a whole organization, not just one device" requirement.
    op.add_column("devices", sa.Column(
        "deployment_mode", sa.String(), nullable=False, server_default="endpoint",
        comment="endpoint | gateway -- gateway installs discover + report on their whole internal network",
    ))

    # ── device_commands: the queue BlueSOC writes to and the agent polls ──────
    # A dedicated table (not just a JSON blob on Device) so every command has a
    # real history: who queued it, when, what happened, never overwritten.
    op.create_table(
        "device_commands",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("device_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(), nullable=False,
                  comment="e.g. isolate, unisolate, collect_logs -- extend as needed"),
        sa.Column("params", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending",
                  comment="pending | delivered | completed | failed"),
        sa.Column("issued_by", postgresql.UUID(as_uuid=True), nullable=True,
                  comment="The human user (current_user.id) who clicked the action in BlueSOC"),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_device_commands_device_id_status", "device_commands", ["device_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_device_commands_device_id_status", table_name="device_commands")
    op.drop_table("device_commands")
    op.drop_index("ix_devices_organization_id", table_name="devices")
    op.drop_column("devices", "deployment_mode")
    op.drop_column("devices", "last_heartbeat")
    op.drop_column("devices", "agent_enrolled_at")
    op.drop_column("devices", "agent_secret_hash")
    op.drop_column("devices", "organization_id")
    op.drop_table("organizations")
