"""Rename catalogue source-state labels without modifying editorial data.

Revision ID: 0014_metra_demo_source
Revises: 0013_catalogue_source_states
"""
from alembic import op
import sqlalchemy as sa

revision='0014_metra_demo_source'
down_revision='0013_catalogue_source_states'
branch_labels=None
depends_on=None


def upgrade():
    op.alter_column('catalogue_source_states','dataset',
        existing_type=sa.String(length=30),server_default='metra-demo',existing_nullable=False)
    op.execute("UPDATE catalogue_source_states SET dataset = 'metra-demo' WHERE dataset IN ('v3', 'demo_metra')")


def downgrade():
    op.alter_column('catalogue_source_states','dataset',
        existing_type=sa.String(length=30),server_default='v3',existing_nullable=False)
    # Do not revert per-record labels: this could reclassify genuine future catalogues.
