"""Add revision lineage and independent price books."""
from alembic import op
from sqlalchemy import DDL

revision = '0002_metra'
down_revision = '0001_marketplace'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(DDL("""
CREATE TABLE revision_origins (
	revision_id UUID NOT NULL,
	parent_id UUID NOT NULL,
	message TEXT NOT NULL,
	PRIMARY KEY (revision_id),
	FOREIGN KEY(revision_id) REFERENCES commercial_solution_revisions (id),
	FOREIGN KEY(parent_id) REFERENCES commercial_solution_revisions (id)
)
"""))
    op.execute(DDL("""
CREATE TABLE price_books (
	archived BOOLEAN DEFAULT false NOT NULL,
	name VARCHAR(180) NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (name)
)
"""))
    op.execute(DDL("""
CREATE TABLE price_book_versions (
	book_id UUID NOT NULL,
	asset_id UUID NOT NULL,
	sha256 VARCHAR(64) NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (book_id, sha256),
	FOREIGN KEY(book_id) REFERENCES price_books (id),
	FOREIGN KEY(asset_id) REFERENCES assets (id)
)
"""))
    op.execute(DDL("""
CREATE TABLE price_concepts (
	version_id UUID NOT NULL,
	code TEXT NOT NULL,
	unit TEXT NOT NULL,
	description TEXT NOT NULL,
	values JSONB NOT NULL,
	PRIMARY KEY (version_id, code),
	FOREIGN KEY(version_id) REFERENCES price_book_versions (id)
)
"""))


def downgrade():
    raise RuntimeError('Restaure una copia anterior para revertir la migración')
