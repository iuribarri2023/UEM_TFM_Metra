"""Add explicit IFC component links to revision documents."""
from alembic import op
from sqlalchemy import DDL

revision = '0005_component_links'
down_revision = '0004_document_jobs'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(DDL("""
CREATE TABLE component_document_links (
	revision_id UUID NOT NULL,
	ifc_asset_id UUID NOT NULL,
	ifc_global_id VARCHAR(22) NOT NULL,
	target_asset_id UUID NOT NULL,
	concept_code VARCHAR(120) NOT NULL,
	material VARCHAR(255) NOT NULL,
	unit VARCHAR(100) NOT NULL,
	evidence TEXT NOT NULL,
	author_id UUID NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(revision_id, ifc_asset_id) REFERENCES revision_assets (revision_id, asset_id) ON DELETE CASCADE,
	FOREIGN KEY(revision_id, target_asset_id) REFERENCES revision_assets (revision_id, asset_id) ON DELETE CASCADE,
	UNIQUE (revision_id, ifc_asset_id, ifc_global_id, target_asset_id, concept_code, material),
	FOREIGN KEY(author_id) REFERENCES users (id)
)
"""))


def downgrade():
    raise RuntimeError('Restaure la copia anterior para revertir esta migración')
