"""Clean standalone schema; never run on legacy production DB without staging migration.

Revision ID: 0001_marketplace
Revises:
"""
from alembic import op
from sqlalchemy import DDL
revision='0001_marketplace'
down_revision=None
branch_labels=None
depends_on=None


def upgrade():
    op.execute(DDL("""
CREATE TABLE manufacturers (
	name VARCHAR(255) NOT NULL,
	code VARCHAR(90) NOT NULL,
	description TEXT NOT NULL,
	website VARCHAR(512),
	public_email VARCHAR(255),
	contact_public BOOLEAN NOT NULL,
	status VARCHAR(16) NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (code)
)
"""))
    op.execute(DDL("""
CREATE TABLE systems (
	code VARCHAR(60) NOT NULL,
	name_es VARCHAR(255) NOT NULL,
	archived BOOLEAN NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (code)
)
"""))
    op.execute(DDL("""
CREATE TABLE assets (
	manufacturer_id UUID,
	original_name VARCHAR(255) NOT NULL,
	storage_key VARCHAR(130) NOT NULL,
	file_type VARCHAR(8) NOT NULL,
	sha256 VARCHAR(64) NOT NULL,
	size BIGINT NOT NULL,
	processing_status VARCHAR(16) NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(manufacturer_id) REFERENCES manufacturers (id),
	UNIQUE (storage_key)
)
"""))
    op.execute(DDL("""
CREATE INDEX ix_assets_manufacturer_id ON assets (manufacturer_id)
"""))
    op.execute(DDL("""
CREATE TABLE subsystems (
	code VARCHAR(60) NOT NULL,
	name_es VARCHAR(255) NOT NULL,
	system_id UUID NOT NULL,
	archived BOOLEAN NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (code),
	FOREIGN KEY(system_id) REFERENCES systems (id)
)
"""))
    op.execute(DDL("""
CREATE INDEX ix_subsystems_system_id ON subsystems (system_id)
"""))
    op.execute(DDL("""
CREATE TABLE users (
	email VARCHAR(255) NOT NULL,
	password_hash VARCHAR(255) NOT NULL,
	role VARCHAR(24) NOT NULL,
	manufacturer_id UUID,
	active BOOLEAN NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CHECK (role IN ('ADMIN','MANUFACTURER')),
	FOREIGN KEY(manufacturer_id) REFERENCES manufacturers (id)
)
"""))
    op.execute(DDL("""
CREATE UNIQUE INDEX ix_users_email ON users (email)
"""))
    op.execute(DDL("""
CREATE INDEX ix_users_manufacturer_id ON users (manufacturer_id)
"""))
    op.execute(DDL("""
CREATE TABLE archetypes (
	code VARCHAR(90) NOT NULL,
	name_es VARCHAR(255) NOT NULL,
	subsystem_id UUID NOT NULL,
	archived BOOLEAN NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (code),
	FOREIGN KEY(subsystem_id) REFERENCES subsystems (id)
)
"""))
    op.execute(DDL("""
CREATE INDEX ix_archetypes_subsystem_id ON archetypes (subsystem_id)
"""))
    op.execute(DDL("""
CREATE TABLE asset_extractions (
	asset_id UUID NOT NULL,
	schema_version VARCHAR(12) NOT NULL,
	source_format VARCHAR(32) NOT NULL,
	normalized JSONB NOT NULL,
	warnings JSONB NOT NULL,
	is_valid BOOLEAN NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(asset_id) REFERENCES assets (id)
)
"""))
    op.execute(DDL("""
CREATE INDEX ix_asset_extractions_asset_id ON asset_extractions (asset_id)
"""))
    op.execute(DDL("""
CREATE TABLE audit_logs (
	id UUID NOT NULL,
	at TIMESTAMP WITH TIME ZONE NOT NULL,
	actor_id UUID,
	action VARCHAR(80) NOT NULL,
	entity VARCHAR(70) NOT NULL,
	entity_id VARCHAR(36) NOT NULL,
	detail JSONB NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(actor_id) REFERENCES users (id)
)
"""))
    op.execute(DDL("""
CREATE TABLE commercial_solutions (
	manufacturer_id UUID NOT NULL,
	subsystem_id UUID NOT NULL,
	code VARCHAR(100) NOT NULL,
	availability VARCHAR(16) NOT NULL,
	published_revision_id UUID,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CHECK (availability IN ('ACTIVE','SUSPENDED','ARCHIVED')),
	FOREIGN KEY(manufacturer_id) REFERENCES manufacturers (id),
	FOREIGN KEY(subsystem_id) REFERENCES subsystems (id),
	UNIQUE (code)
)
"""))
    op.execute(DDL("""
CREATE INDEX ix_commercial_solutions_manufacturer_id ON commercial_solutions (manufacturer_id)
"""))
    op.execute(DDL("""
CREATE INDEX ix_commercial_solutions_subsystem_id ON commercial_solutions (subsystem_id)
"""))
    op.execute(DDL("""
CREATE TABLE data_templates (
	subsystem_id UUID NOT NULL,
	version INTEGER NOT NULL,
	fields JSONB NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (subsystem_id, version),
	FOREIGN KEY(subsystem_id) REFERENCES subsystems (id)
)
"""))
    op.execute(DDL("""
CREATE INDEX ix_data_templates_subsystem_id ON data_templates (subsystem_id)
"""))
    op.execute(DDL("""
CREATE TABLE manufacturer_invitations (
	manufacturer_id UUID NOT NULL,
	email VARCHAR(255) NOT NULL,
	token_hash VARCHAR(64) NOT NULL,
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
	used_at TIMESTAMP WITH TIME ZONE,
	created_by UUID NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(manufacturer_id) REFERENCES manufacturers (id),
	UNIQUE (token_hash),
	FOREIGN KEY(created_by) REFERENCES users (id)
)
"""))
    op.execute(DDL("""
CREATE TABLE notifications (
	user_id UUID NOT NULL,
	event VARCHAR(32) NOT NULL,
	message TEXT NOT NULL,
	read_at TIMESTAMP WITH TIME ZONE,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES users (id)
)
"""))
    op.execute(DDL("""
CREATE INDEX ix_notifications_user_id ON notifications (user_id)
"""))
    op.execute(DDL("""
CREATE TABLE refresh_sessions (
	user_id UUID NOT NULL,
	token_hash VARCHAR(64) NOT NULL,
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
	revoked_at TIMESTAMP WITH TIME ZONE,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES users (id),
	UNIQUE (token_hash)
)
"""))
    op.execute(DDL("""
CREATE INDEX ix_refresh_sessions_user_id ON refresh_sessions (user_id)
"""))
    op.execute(DDL("""
CREATE TABLE commercial_solution_revisions (
	product_id UUID NOT NULL,
	number INTEGER NOT NULL,
	status VARCHAR(16) NOT NULL,
	name_es VARCHAR(255) NOT NULL,
	description TEXT NOT NULL,
	commercial_reference VARCHAR(128) NOT NULL,
	functional_unit VARCHAR(24) NOT NULL,
	template_version INTEGER NOT NULL,
	technical_data JSONB NOT NULL,
	economic_data JSONB NOT NULL,
	environmental_data JSONB NOT NULL,
	discrepancies JSONB NOT NULL,
	rejection_reason TEXT,
	submitted_at TIMESTAMP WITH TIME ZONE,
	decided_at TIMESTAMP WITH TIME ZONE,
	created_by UUID NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (product_id, number),
	CHECK (status IN ('DRAFT','SUBMITTED','APPROVED','REJECTED')),
	FOREIGN KEY(product_id) REFERENCES commercial_solutions (id),
	FOREIGN KEY(created_by) REFERENCES users (id)
)
"""))
    op.execute(DDL("""
CREATE INDEX ix_commercial_solution_revisions_product_id ON commercial_solution_revisions (product_id)
"""))
    op.execute(DDL("""
CREATE UNIQUE INDEX uq_one_active_revision ON commercial_solution_revisions (product_id) WHERE status IN ('DRAFT','SUBMITTED')
"""))
    op.execute(DDL("""
CREATE TABLE generic_solutions (
	code VARCHAR(110) NOT NULL,
	name_es VARCHAR(255) NOT NULL,
	archetype_id UUID NOT NULL,
	subsystem_id UUID NOT NULL,
	status VARCHAR(16) NOT NULL,
	technical_data JSONB NOT NULL,
	environmental_data JSONB NOT NULL,
	economic_data JSONB NOT NULL,
	composition JSONB NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CHECK (status IN ('DRAFT','PUBLISHED','ARCHIVED')),
	UNIQUE (code),
	FOREIGN KEY(archetype_id) REFERENCES archetypes (id),
	FOREIGN KEY(subsystem_id) REFERENCES subsystems (id)
)
"""))
    op.execute(DDL("""
CREATE INDEX ix_generic_solutions_archetype_id ON generic_solutions (archetype_id)
"""))
    op.execute(DDL("""
CREATE INDEX ix_generic_solutions_subsystem_id ON generic_solutions (subsystem_id)
"""))
    op.execute(DDL("""
CREATE TABLE generic_solution_assets (
	generic_id UUID NOT NULL,
	asset_id UUID NOT NULL,
	public_download_allowed BOOLEAN NOT NULL,
	public_view_allowed BOOLEAN NOT NULL,
	PRIMARY KEY (generic_id, asset_id),
	FOREIGN KEY(generic_id) REFERENCES generic_solutions (id),
	FOREIGN KEY(asset_id) REFERENCES assets (id)
)
"""))
    op.execute(DDL("""
CREATE TABLE generic_solution_slots (
	generic_solution_id UUID NOT NULL,
	code VARCHAR(100) NOT NULL,
	name_es VARCHAR(255) NOT NULL,
	slot_order INTEGER NOT NULL,
	required BOOLEAN NOT NULL,
	properties JSONB NOT NULL,
	archived BOOLEAN NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (generic_solution_id, code),
	FOREIGN KEY(generic_solution_id) REFERENCES generic_solutions (id)
)
"""))
    op.execute(DDL("""
CREATE INDEX ix_generic_solution_slots_generic_solution_id ON generic_solution_slots (generic_solution_id)
"""))
    op.execute(DDL("""
CREATE TABLE review_decisions (
	revision_id UUID NOT NULL,
	admin_id UUID NOT NULL,
	decision VARCHAR(16) NOT NULL,
	reason TEXT,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(revision_id) REFERENCES commercial_solution_revisions (id),
	FOREIGN KEY(admin_id) REFERENCES users (id)
)
"""))
    op.execute(DDL("""
CREATE TABLE revision_assets (
	revision_id UUID NOT NULL,
	asset_id UUID NOT NULL,
	public_download_allowed BOOLEAN NOT NULL,
	public_view_allowed BOOLEAN NOT NULL,
	PRIMARY KEY (revision_id, asset_id),
	FOREIGN KEY(revision_id) REFERENCES commercial_solution_revisions (id),
	FOREIGN KEY(asset_id) REFERENCES assets (id)
)
"""))
    op.execute(DDL("""
CREATE TABLE revision_generic_solutions (
	revision_id UUID NOT NULL,
	generic_id UUID NOT NULL,
	PRIMARY KEY (revision_id, generic_id),
	FOREIGN KEY(revision_id) REFERENCES commercial_solution_revisions (id),
	FOREIGN KEY(generic_id) REFERENCES generic_solutions (id)
)
"""))
    op.execute(DDL("""
ALTER TABLE commercial_solutions ADD CONSTRAINT fk_published_revision FOREIGN KEY(published_revision_id) REFERENCES commercial_solution_revisions (id)
"""))


def downgrade():
    raise RuntimeError('Destructive downgrade intentionally forbidden; restore a database backup instead')
