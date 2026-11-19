"""Persistent processing queue."""
from alembic import op
from sqlalchemy import DDL

revision = '0004_document_jobs'
down_revision = '0003_economics'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(DDL("""
CREATE TABLE document_jobs (
	asset_id UUID NOT NULL,
	state VARCHAR(16) NOT NULL,
	attempts INTEGER NOT NULL,
	progress INTEGER NOT NULL,
	started_at TIMESTAMP WITH TIME ZONE,
	finished_at TIMESTAMP WITH TIME ZONE,
	error_code VARCHAR(40),
	PRIMARY KEY (asset_id),
	CHECK (state IN ('PENDING','PROCESSING','VALID','INVALID','CANCELLED')),
	CHECK (progress BETWEEN 0 AND 100),
	FOREIGN KEY(asset_id) REFERENCES assets (id)
)
"""))
    op.execute(DDL("""
CREATE INDEX ix_document_jobs_state ON document_jobs (state)
"""))


def downgrade():
    raise RuntimeError('Restaure la copia anterior para revertir esta migración')
