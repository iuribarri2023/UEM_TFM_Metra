"""Add editable budgets and cost database lifecycle."""
from alembic import op
from sqlalchemy import DDL

revision = '0003_economics'
down_revision = '0002_metra'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('ALTER TABLE price_books ADD COLUMN IF NOT EXISTS archived boolean NOT NULL DEFAULT false')
    op.execute(DDL("""
CREATE TABLE budgets (
	name VARCHAR(180) NOT NULL,
	manufacturer_id UUID,
	revision_id UUID,
	archived BOOLEAN NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(manufacturer_id) REFERENCES manufacturers (id),
	FOREIGN KEY(revision_id) REFERENCES commercial_solution_revisions (id)
)
"""))
    op.execute(DDL("""
CREATE INDEX ix_budgets_manufacturer_id ON budgets (manufacturer_id)
"""))
    op.execute(DDL("""
CREATE INDEX ix_budgets_revision_id ON budgets (revision_id)
"""))
    op.execute(DDL("""
CREATE TABLE budget_items (
	budget_id UUID NOT NULL,
	code VARCHAR(90) NOT NULL,
	description TEXT NOT NULL,
	unit VARCHAR(24) NOT NULL,
	quantity NUMERIC(20, 6) NOT NULL,
	unit_price NUMERIC(20, 6) NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (budget_id, code),
	CHECK (quantity >= 0),
	FOREIGN KEY(budget_id) REFERENCES budgets (id)
)
"""))
    op.execute(DDL("""
CREATE INDEX ix_budget_items_budget_id ON budget_items (budget_id)
"""))


def downgrade():
    raise RuntimeError('Restaure la copia anterior para revertir esta migración')
