"""Record successful, one-time catalogue initialization."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '0010_catalogue_initializations'
down_revision = '0009_demo_solution_overlays'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('catalogue_initializations',
                    sa.Column('key', sa.String(60), primary_key=True),
                    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=False),
                    sa.Column('report', JSONB(), nullable=False))


def downgrade():
    raise RuntimeError('Conservar el historial de inicialización. Restaurar una copia de ensayo.')
