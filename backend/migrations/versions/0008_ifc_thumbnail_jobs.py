"""Record independently retriable IFC previews, without changing existing assets."""
from alembic import op
import sqlalchemy as sa

revision = '0008_ifc_thumbnail_jobs'
down_revision = '0007_cost_imports'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'ifc_thumbnail_jobs',
        sa.Column('asset_id', sa.Uuid(), sa.ForeignKey('assets.id'), primary_key=True),
        sa.Column('source_sha256', sa.String(length=64), nullable=False),
        sa.Column('state', sa.String(length=16), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True)),
        sa.Column('finished_at', sa.DateTime(timezone=True)),
        sa.Column('next_retry_at', sa.DateTime(timezone=True)),
        sa.Column('error_code', sa.String(length=40)),
        sa.CheckConstraint("state IN ('PENDING','PROCESSING','READY','FAILED')"),
    )
    op.create_index('ix_ifc_thumbnail_jobs_state', 'ifc_thumbnail_jobs', ['state'])


def downgrade():
    raise RuntimeError('Esta migración es aditiva; utilice una copia restaurada para revertir.')
