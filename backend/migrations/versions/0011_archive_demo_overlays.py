"""Archive historical academic overlays after consolidation in the V3 corpus."""
from alembic import op

revision = '0011_archive_demo_overlays'
down_revision = '0010_catalogue_initializations'
branch_labels = None
depends_on = None


def upgrade():
    op.rename_table('demo_solution_overlays', 'historical_demo_solution_overlays')


def downgrade():
    op.rename_table('historical_demo_solution_overlays', 'demo_solution_overlays')
