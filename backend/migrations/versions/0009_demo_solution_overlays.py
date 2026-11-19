"""Separate optional teaching overlays, no changes to versioned technical data."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision='0009_demo_solution_overlays'
down_revision='0008_ifc_thumbnail_jobs'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('demo_solution_overlays',
      sa.Column('kind',sa.String(1),primary_key=True),
      sa.Column('code',sa.String(110),primary_key=True),
      sa.Column('generator_version',sa.String(60),nullable=False),
      sa.Column('payload',JSONB(),nullable=False),
      sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
      sa.CheckConstraint("kind IN ('g','p')",name='ck_demo_kind'))

def downgrade():
    raise RuntimeError('Migración aditiva: usar base de ensayo restaurada para revertir')
