"""Non-destructive, per-entity source snapshots for V3 three-way reconciliation."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0013_catalogue_source_states'
down_revision = '0012_retire_installations'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('catalogue_source_states',
        sa.Column('key', sa.String(160), primary_key=True),
        sa.Column('dataset', sa.String(30), nullable=False, server_default='v3'),
        sa.Column('baseline', postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('source_hash', sa.String(64), nullable=False),
        sa.Column('status', sa.String(24), nullable=False, server_default='SYNCED'),
        sa.Column('pending', postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('SYNCED','PENDING','CONFLICT','UNBASELINED','ORPHANED')",name='ck_catalogue_source_status'))

def downgrade():
    # Explicit destructive rollback: operator must export pending proposals first.
    raise RuntimeError('Export catalogue_source_states before reversing this migration; no destructive automatic rollback.')
