"""Materialize a parsed BC3 in the same transaction that completes its job."""
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB

from .models import AuditLog, CostImport, PriceBookVersion


def store_cost_import(db, asset, normalized):
    pending = db.get(CostImport, asset.id)
    if not pending or pending.version_id:
        return
    version = PriceBookVersion(book_id=pending.book_id, asset_id=asset.id, sha256=asset.sha256)
    db.add(version)
    db.flush()
    statement = text("""
        INSERT INTO price_concepts (version_id, code, unit, description, "values")
        SELECT CAST(:version_id AS uuid), code, unit, description, payload
        FROM jsonb_to_recordset(:concepts) AS source(code text, unit text, description text, payload jsonb)
    """).bindparams(bindparam('concepts', type_=JSONB))
    concepts = normalized['concepts']
    for start in range(0, len(concepts), 1000):
        rows = [{
            'code': row['code'], 'unit': row['unit'], 'description': row['description'],
            'payload': {key: val for key, val in row.items() if key not in ('code', 'unit', 'description')},
        } for row in concepts[start:start + 1000]]
        db.execute(statement, {'version_id': version.id, 'concepts': rows})
    pending.version_id = version.id
    pending.concept_count = len(concepts)
    db.add(AuditLog(actor_id=pending.actor_id, action='IMPORT_COST_DATABASE',
                    entity='cost-database-version', entity_id=str(version.id),
                    detail={'concept_count': pending.concept_count}))
