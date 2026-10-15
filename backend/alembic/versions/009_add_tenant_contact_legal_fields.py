"""add missing contact/legal columns to tenants

Revision ID: 009
Revises: 008
Create Date: 2026-09-30

Context: the Tenant model has had contact_name, contact_email,
legal_agreement_signed_at, legal_agreement_reference, and notes since these
fields were merged in from the old, now-retired Organization table (back
when Organization duplicated Tenant's contact/legal concept). No migration
ever actually added these columns to the real `tenants` table -- it went
unnoticed until seed.py ran the first query that selects every column.
"""
from alembic import op
import sqlalchemy as sa

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("contact_name", sa.String(), nullable=True))
    op.add_column("tenants", sa.Column("contact_email", sa.String(), nullable=True))
    op.add_column("tenants", sa.Column("legal_agreement_signed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tenants", sa.Column("legal_agreement_reference", sa.String(), nullable=True))
    op.add_column("tenants", sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "notes")
    op.drop_column("tenants", "legal_agreement_reference")
    op.drop_column("tenants", "legal_agreement_signed_at")
    op.drop_column("tenants", "contact_email")
    op.drop_column("tenants", "contact_name")