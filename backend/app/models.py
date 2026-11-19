"""PostgreSQL 15+ relational identities and versioned technical JSONB payloads."""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import (Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer,
                        BigInteger, Numeric, String, Text, UniqueConstraint, func)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import text

class Base(DeclarativeBase): pass

def uid(): return uuid4()
def now(): return datetime.now(timezone.utc)

class Record:
    id: Mapped[object] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now, nullable=False)

class System(Record,Base):
    __tablename__='systems'
    code:Mapped[str]=mapped_column(String(60),unique=True,nullable=False)
    name_es:Mapped[str]=mapped_column(String(255),nullable=False)
    archived:Mapped[bool]=mapped_column(Boolean,default=False,nullable=False)

class Subsystem(Record,Base):
    __tablename__='subsystems'
    code:Mapped[str]=mapped_column(String(60),unique=True,nullable=False)
    name_es:Mapped[str]=mapped_column(String(255),nullable=False)
    system_id:Mapped[object]=mapped_column(ForeignKey('systems.id'),nullable=False,index=True)
    archived:Mapped[bool]=mapped_column(Boolean,default=False,nullable=False)

class Archetype(Record,Base):
    __tablename__='archetypes'
    code:Mapped[str]=mapped_column(String(90),unique=True,nullable=False)
    name_es:Mapped[str]=mapped_column(String(255),nullable=False)
    subsystem_id:Mapped[object]=mapped_column(ForeignKey('subsystems.id'),nullable=False,index=True)
    archived:Mapped[bool]=mapped_column(Boolean,default=False,nullable=False)

class GenericSolution(Record,Base):
    __tablename__='generic_solutions'
    code:Mapped[str]=mapped_column(String(110),unique=True,nullable=False)
    name_es:Mapped[str]=mapped_column(String(255),nullable=False)
    archetype_id:Mapped[object]=mapped_column(ForeignKey('archetypes.id'),nullable=False,index=True)
    subsystem_id:Mapped[object]=mapped_column(ForeignKey('subsystems.id'),nullable=False,index=True)
    status:Mapped[str]=mapped_column(String(16),default='DRAFT',nullable=False)
    technical_data:Mapped[dict]=mapped_column(JSONB,default=dict,nullable=False)
    environmental_data:Mapped[dict]=mapped_column(JSONB,default=dict,nullable=False)
    economic_data:Mapped[dict]=mapped_column(JSONB,default=dict,nullable=False)
    composition:Mapped[list]=mapped_column(JSONB,default=list,nullable=False)
    __table_args__=(CheckConstraint("status IN ('DRAFT','PUBLISHED','ARCHIVED')"),)

class GenericSlot(Record,Base):
    __tablename__='generic_solution_slots'
    generic_solution_id:Mapped[object]=mapped_column(ForeignKey('generic_solutions.id'),nullable=False,index=True)
    code:Mapped[str]=mapped_column(String(100),nullable=False)
    name_es:Mapped[str]=mapped_column(String(255),nullable=False)
    slot_order:Mapped[int]=mapped_column(Integer,default=0,nullable=False)
    required:Mapped[bool]=mapped_column(Boolean,default=False,nullable=False)
    properties:Mapped[dict]=mapped_column(JSONB,default=dict,nullable=False)
    archived:Mapped[bool]=mapped_column(Boolean,default=False,nullable=False)
    __table_args__=(UniqueConstraint('generic_solution_id','code'),)

class DataTemplate(Record,Base):
    __tablename__='data_templates'
    subsystem_id:Mapped[object]=mapped_column(ForeignKey('subsystems.id'),nullable=False,index=True)
    version:Mapped[int]=mapped_column(Integer,default=1,nullable=False)
    fields:Mapped[list]=mapped_column(JSONB,default=list,nullable=False)
    __table_args__=(UniqueConstraint('subsystem_id','version'),)

class Manufacturer(Record,Base):
    __tablename__='manufacturers'
    name:Mapped[str]=mapped_column(String(255),nullable=False)
    code:Mapped[str]=mapped_column(String(90),unique=True,nullable=False)
    description:Mapped[str]=mapped_column(Text,default='',nullable=False)
    website:Mapped[str|None]=mapped_column(String(512))
    public_email:Mapped[str|None]=mapped_column(String(255))
    contact_public:Mapped[bool]=mapped_column(Boolean,default=False,nullable=False)
    status:Mapped[str]=mapped_column(String(16),default='ACTIVE',nullable=False)

class User(Record,Base):
    __tablename__='users'
    email:Mapped[str]=mapped_column(String(255),unique=True,nullable=False,index=True)
    password_hash:Mapped[str]=mapped_column(String(255),nullable=False)
    role:Mapped[str]=mapped_column(String(24),nullable=False)
    manufacturer_id:Mapped[object|None]=mapped_column(ForeignKey('manufacturers.id'),index=True)
    active:Mapped[bool]=mapped_column(Boolean,default=True,nullable=False)
    __table_args__=(CheckConstraint("role IN ('ADMIN','MANUFACTURER')"),)

class Invitation(Record,Base):
    __tablename__='manufacturer_invitations'
    manufacturer_id:Mapped[object]=mapped_column(ForeignKey('manufacturers.id'),nullable=False)
    email:Mapped[str]=mapped_column(String(255),nullable=False)
    token_hash:Mapped[str]=mapped_column(String(64),unique=True,nullable=False)
    expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    used_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    created_by:Mapped[object]=mapped_column(ForeignKey('users.id'),nullable=False)

class RefreshSession(Record,Base):
    __tablename__='refresh_sessions'
    user_id:Mapped[object]=mapped_column(ForeignKey('users.id'),nullable=False,index=True)
    token_hash:Mapped[str]=mapped_column(String(64),unique=True,nullable=False)
    expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    revoked_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))

class CommercialSolution(Record,Base):
    __tablename__='commercial_solutions'
    manufacturer_id:Mapped[object]=mapped_column(ForeignKey('manufacturers.id'),nullable=False,index=True)
    subsystem_id:Mapped[object]=mapped_column(ForeignKey('subsystems.id'),nullable=False,index=True)
    code:Mapped[str]=mapped_column(String(100),unique=True,nullable=False)
    availability:Mapped[str]=mapped_column(String(16),default='ACTIVE',nullable=False)
    published_revision_id:Mapped[object|None]=mapped_column(ForeignKey('commercial_solution_revisions.id',use_alter=True,name='fk_published_revision'))
    __table_args__=(CheckConstraint("availability IN ('ACTIVE','SUSPENDED','ARCHIVED')"),)

class Revision(Record,Base):
    __tablename__='commercial_solution_revisions'
    product_id:Mapped[object]=mapped_column(ForeignKey('commercial_solutions.id'),nullable=False,index=True)
    number:Mapped[int]=mapped_column(Integer,nullable=False)
    status:Mapped[str]=mapped_column(String(16),default='DRAFT',nullable=False)
    name_es:Mapped[str]=mapped_column(String(255),nullable=False)
    description:Mapped[str]=mapped_column(Text,default='',nullable=False)
    commercial_reference:Mapped[str]=mapped_column(String(128),default='',nullable=False)
    functional_unit:Mapped[str]=mapped_column(String(24),default='unit',nullable=False)
    template_version:Mapped[int]=mapped_column(Integer,default=1,nullable=False)
    technical_data:Mapped[dict]=mapped_column(JSONB,default=dict,nullable=False)
    economic_data:Mapped[dict]=mapped_column(JSONB,default=dict,nullable=False)
    environmental_data:Mapped[dict]=mapped_column(JSONB,default=dict,nullable=False)
    discrepancies:Mapped[list]=mapped_column(JSONB,default=list,nullable=False)
    rejection_reason:Mapped[str|None]=mapped_column(Text)
    submitted_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    decided_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    created_by:Mapped[object]=mapped_column(ForeignKey('users.id'),nullable=False)
    __table_args__=(UniqueConstraint('product_id','number'),CheckConstraint("status IN ('DRAFT','SUBMITTED','APPROVED','REJECTED')"),
      Index('uq_one_active_revision','product_id',unique=True,postgresql_where=text("status IN ('DRAFT','SUBMITTED')")))

class RevisionGeneric(Base):
    __tablename__='revision_generic_solutions'
    revision_id:Mapped[object]=mapped_column(ForeignKey('commercial_solution_revisions.id'),primary_key=True)
    generic_id:Mapped[object]=mapped_column(ForeignKey('generic_solutions.id'),primary_key=True)

class Asset(Record,Base):
    __tablename__='assets'
    manufacturer_id:Mapped[object|None]=mapped_column(ForeignKey('manufacturers.id'),index=True)
    original_name:Mapped[str]=mapped_column(String(255),nullable=False)
    storage_key:Mapped[str]=mapped_column(String(130),unique=True,nullable=False)
    file_type:Mapped[str]=mapped_column(String(8),nullable=False)
    sha256:Mapped[str]=mapped_column(String(64),nullable=False)
    size:Mapped[int]=mapped_column(BigInteger,nullable=False)
    processing_status:Mapped[str]=mapped_column(String(16),nullable=False)

class RevisionAsset(Base):
    __tablename__='revision_assets'
    revision_id:Mapped[object]=mapped_column(ForeignKey('commercial_solution_revisions.id'),primary_key=True)
    asset_id:Mapped[object]=mapped_column(ForeignKey('assets.id'),primary_key=True)
    public_download_allowed:Mapped[bool]=mapped_column(Boolean,default=False,nullable=False)
    public_view_allowed:Mapped[bool]=mapped_column(Boolean,default=False,nullable=False)

class GenericAsset(Base):
    __tablename__='generic_solution_assets'
    generic_id:Mapped[object]=mapped_column(ForeignKey('generic_solutions.id'),primary_key=True)
    asset_id:Mapped[object]=mapped_column(ForeignKey('assets.id'),primary_key=True)
    public_download_allowed:Mapped[bool]=mapped_column(Boolean,default=False,nullable=False)
    public_view_allowed:Mapped[bool]=mapped_column(Boolean,default=False,nullable=False)

class Extraction(Record,Base):
    __tablename__='asset_extractions'
    asset_id:Mapped[object]=mapped_column(ForeignKey('assets.id'),nullable=False,index=True)
    schema_version:Mapped[str]=mapped_column(String(12),default='1.0',nullable=False)
    source_format:Mapped[str]=mapped_column(String(32),nullable=False)
    normalized:Mapped[dict]=mapped_column(JSONB,default=dict,nullable=False)
    warnings:Mapped[list]=mapped_column(JSONB,default=list,nullable=False)
    is_valid:Mapped[bool]=mapped_column(Boolean,nullable=False)

class ReviewDecision(Record,Base):
    __tablename__='review_decisions'
    revision_id:Mapped[object]=mapped_column(ForeignKey('commercial_solution_revisions.id'),nullable=False)
    admin_id:Mapped[object]=mapped_column(ForeignKey('users.id'),nullable=False)
    decision:Mapped[str]=mapped_column(String(16),nullable=False)
    reason:Mapped[str|None]=mapped_column(Text)

class Notification(Record,Base):
    __tablename__='notifications'
    user_id:Mapped[object]=mapped_column(ForeignKey('users.id'),nullable=False,index=True)
    event:Mapped[str]=mapped_column(String(32),nullable=False)
    message:Mapped[str]=mapped_column(Text,nullable=False)
    read_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))

class AuditLog(Base):
    __tablename__='audit_logs'
    id:Mapped[object]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uid)
    at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,nullable=False)
    actor_id:Mapped[object|None]=mapped_column(ForeignKey('users.id'))
    action:Mapped[str]=mapped_column(String(80),nullable=False)
    entity:Mapped[str]=mapped_column(String(70),nullable=False)
    entity_id:Mapped[str]=mapped_column(String(36),nullable=False)
    detail:Mapped[dict]=mapped_column(JSONB,default=dict,nullable=False)

class RevisionOrigin(Base):
    __tablename__ = 'revision_origins'
    revision_id: Mapped[object] = mapped_column(ForeignKey('commercial_solution_revisions.id'), primary_key=True)
    parent_id: Mapped[object] = mapped_column(ForeignKey('commercial_solution_revisions.id'), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)


class PriceBook(Record, Base):
    __tablename__ = 'price_books'
    archived: Mapped[bool] = mapped_column(Boolean,nullable=False,default=False,server_default=text("false"))
    name: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)


class PriceBookVersion(Record, Base):
    __tablename__ = 'price_book_versions'
    book_id: Mapped[object] = mapped_column(ForeignKey('price_books.id'), nullable=False)
    asset_id: Mapped[object] = mapped_column(ForeignKey('assets.id'), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    __table_args__ = (UniqueConstraint('book_id','sha256'),)


class PriceConcept(Base):
    __tablename__ = 'price_concepts'
    version_id: Mapped[object] = mapped_column(ForeignKey('price_book_versions.id'), primary_key=True)
    code: Mapped[str] = mapped_column(Text, primary_key=True)
    unit: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    values: Mapped[dict] = mapped_column(JSONB, nullable=False)

class Budget(Record, Base):
    __tablename__ = 'budgets'
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    manufacturer_id: Mapped[object | None] = mapped_column(ForeignKey('manufacturers.id'),index=True)
    revision_id: Mapped[object | None] = mapped_column(ForeignKey('commercial_solution_revisions.id'),index=True)
    archived: Mapped[bool] = mapped_column(Boolean,nullable=False,default=False)


class BudgetItem(Record, Base):
    __tablename__ = 'budget_items'
    budget_id: Mapped[object] = mapped_column(ForeignKey('budgets.id'),index=True,nullable=False)
    code: Mapped[str] = mapped_column(String(90),nullable=False)
    description: Mapped[str] = mapped_column(Text,nullable=False)
    unit: Mapped[str] = mapped_column(String(24),nullable=False)
    quantity: Mapped[object] = mapped_column(Numeric(20,6),nullable=False)
    unit_price: Mapped[object] = mapped_column(Numeric(20,6),nullable=False)
    __table_args__ = (UniqueConstraint('budget_id','code'),CheckConstraint('quantity >= 0'),)

class DocumentJob(Base):
    __tablename__ = 'document_jobs'
    asset_id: Mapped[object] = mapped_column(ForeignKey('assets.id'),primary_key=True)
    state: Mapped[str] = mapped_column(String(16),nullable=False,index=True)
    attempts: Mapped[int] = mapped_column(Integer,nullable=False,default=0)
    progress: Mapped[int] = mapped_column(Integer,nullable=False,default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(40))
    __table_args__ = (CheckConstraint("state IN ('PENDING','PROCESSING','VALID','INVALID','CANCELLED')"),
                      CheckConstraint('progress BETWEEN 0 AND 100'))


class IfcThumbnailJob(Base):
    """Derived IFC preview; independent of document validation and public rights."""
    __tablename__ = 'ifc_thumbnail_jobs'
    asset_id: Mapped[object] = mapped_column(ForeignKey('assets.id'), primary_key=True)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default='PENDING', index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(40))
    __table_args__ = (CheckConstraint("state IN ('PENDING','PROCESSING','READY','FAILED')"),)


class ComponentDocumentLink(Record, Base):
    __tablename__ = 'component_document_links'
    revision_id: Mapped[object] = mapped_column(UUID(as_uuid=True), nullable=False)
    ifc_asset_id: Mapped[object] = mapped_column(UUID(as_uuid=True), nullable=False)
    ifc_global_id: Mapped[str] = mapped_column(String(22), nullable=False)
    target_asset_id: Mapped[object] = mapped_column(UUID(as_uuid=True), nullable=False)
    concept_code: Mapped[str] = mapped_column(String(120), nullable=False, default='')
    material: Mapped[str] = mapped_column(String(255), nullable=False, default='')
    unit: Mapped[str] = mapped_column(String(100), nullable=False, default='')
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[object] = mapped_column(ForeignKey('users.id'), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(('revision_id', 'ifc_asset_id'), ('revision_assets.revision_id', 'revision_assets.asset_id'), ondelete='CASCADE'),
        ForeignKeyConstraint(('revision_id', 'target_asset_id'), ('revision_assets.revision_id', 'revision_assets.asset_id'), ondelete='CASCADE'),
        UniqueConstraint('revision_id', 'ifc_asset_id', 'ifc_global_id', 'target_asset_id', 'concept_code', 'material'),
    )


class CostImport(Base):
    __tablename__ = 'cost_imports'
    asset_id: Mapped[object] = mapped_column(ForeignKey('assets.id'), primary_key=True)
    book_id: Mapped[object] = mapped_column(ForeignKey('price_books.id'), nullable=False, index=True)
    actor_id: Mapped[object] = mapped_column(ForeignKey('users.id'), nullable=False)
    version_id: Mapped[object | None] = mapped_column(ForeignKey('price_book_versions.id'))
    concept_count: Mapped[int | None] = mapped_column(Integer)


class CatalogueInitialization(Base):
    __tablename__ = 'catalogue_initializations'
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    report: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class CatalogueSourceState(Base):
    """Last accepted source snapshot; pending proposals never overwrite editorial data."""
    __tablename__ = 'catalogue_source_states'
    key: Mapped[str] = mapped_column(String(160), primary_key=True)
    dataset: Mapped[str] = mapped_column(String(30), default='metra-demo', nullable=False)
    baseline: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default='SYNCED', nullable=False)
    pending: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now, nullable=False)
    __table_args__ = (CheckConstraint("status IN ('SYNCED','PENDING','CONFLICT','UNBASELINED','ORPHANED')"),)
