"""Track background imports of cost databases."""
from alembic import op
import sqlalchemy as sa

revision = '0007_cost_imports'
down_revision = '0006_repair_legacy_data'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'cost_imports',
        sa.Column('asset_id', sa.Uuid(), sa.ForeignKey('assets.id'), primary_key=True),
        sa.Column('book_id', sa.Uuid(), sa.ForeignKey('price_books.id'), nullable=False),
        sa.Column('actor_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('version_id', sa.Uuid(), sa.ForeignKey('price_book_versions.id')),
        sa.Column('concept_count', sa.Integer()),
    )
    op.create_index('ix_cost_imports_book_id', 'cost_imports', ['book_id'])


def downgrade():
    raise RuntimeError('Restaure la copia anterior para revertir esta migración')
