"""One-time, fail-closed cleanup of 13 independently identified historical generics.

The current distribution has no historical identity manifest. First review the
dry-run candidates against a verified pre-cleanup backup and supply an explicit
JSON manifest of exactly 13 {id, code, sha256} records for --apply.
"""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.orm import Session

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.models import (AuditLog, CatalogueSourceState, GenericAsset, GenericSlot,
                        GenericSolution, RevisionGeneric, Subsystem, System)
from app.source_reconciliation import source_entries


def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda:source.read(1024*1024),b''):value.update(block)
    return value.hexdigest()


def record_digest(row):
    payload={name:getattr(row,name) for name in ('code','name_es','status','technical_data',
                                                  'composition','economic_data','environmental_data')}
    payload.update(archetype_id=str(row.archetype_id),subsystem_id=str(row.subsystem_id))
    return hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,
                                     separators=(',',':')).encode()).hexdigest()


def candidates(db):
    active={key for _,key,*_ in source_entries(Path(__file__).resolve().parents[1]/'data/metra-demo')}
    rows=db.scalars(select(GenericSolution).join(Subsystem,Subsystem.id==GenericSolution.subsystem_id)
                    .join(System,System.id==Subsystem.system_id)
                    .where(System.code=='INS',GenericSolution.status=='ARCHIVED')
                    .order_by(GenericSolution.code)).all()
    result=[]
    for row in rows:
        retirement=db.scalar(select(AuditLog.at).where(
            AuditLog.action=='RETIRE_INSTALLATIONS',AuditLog.entity=='generic_solutions',
            AuditLog.entity_id==str(row.id)).order_by(AuditLog.at.desc()).limit(1))
        result.append({'id':str(row.id),'code':row.code,'sha256':record_digest(row),
                       'retirement_audit':bool(retirement),
                       'modified_since_retirement':bool(retirement and row.updated_at>retirement),
                       'source_marker':row.technical_data.get('legacy_source'),
                       'in_active_source':f'g:{row.code}' in active})
    return result


def dependencies(db, ids):
    return {str(id):{
        'slots':db.scalar(select(func.count()).select_from(GenericSlot).where(GenericSlot.generic_solution_id==id)),
        'asset_links':db.scalar(select(func.count()).select_from(GenericAsset).where(GenericAsset.generic_id==id)),
        'revision_links':db.scalar(select(func.count()).select_from(RevisionGeneric).where(RevisionGeneric.generic_id==id)),
        'audit_records':db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.entity_id==str(id))),
    } for id in ids}


def verify_schema(engine):
    permitted={'generic_solution_slots','generic_solution_assets','revision_generic_solutions'}
    for table in inspect(engine).get_table_names():
        for fk in inspect(engine).get_foreign_keys(table):
            if fk['referred_table']=='generic_solutions' and table not in permitted:
                raise RuntimeError(f'Unreviewed dependency: {table}')


def run(db,engine,manifest=None,backup=None,backup_sha256=None,apply=False):
    rows=candidates(db)
    selected=[row for row in rows if row['retirement_audit'] and row['source_marker']
              and not row['modified_since_retirement'] and not row['in_active_source']]
    excluded=[row for row in rows if row not in selected]
    ids=[UUID(row['id']) for row in selected]
    report={'candidates':selected,'excluded_ins_records':excluded,
            'dependencies':dependencies(db,ids),'applied':False}
    if not apply:return report
    if not selected and db.scalar(select(AuditLog.id).where(AuditLog.action=='ARCHIVED_INSTALLATIONS_CLEANUP').limit(1)):
        report['already_applied']=True
        return report
    if len(selected)!=13 or len({row['code'] for row in selected})!=13:
        raise RuntimeError('Historical identity is ambiguous: expected exactly 13 candidates')
    if manifest is None or not manifest.is_file():raise RuntimeError('Reviewed identity manifest required')
    approved=json.loads(manifest.read_text(encoding='utf-8'))
    if not isinstance(approved,list) or sorted(approved,key=lambda x:x['id'])!=sorted(
        [{key:row[key] for key in ('id','code','sha256')} for row in selected],key=lambda x:x['id']):
        raise RuntimeError('Reviewed identity manifest does not match current database records')
    if backup is None or not backup.is_file() or not backup_sha256 or digest(backup)!=backup_sha256.lower():
        raise RuntimeError('A verified database backup and its SHA-256 are required')
    if any(detail['revision_links'] for detail in report['dependencies'].values()):
        raise RuntimeError('Archived solution is referenced by a commercial revision')
    verify_schema(engine)
    for id in ids:
        db.query(GenericAsset).filter(GenericAsset.generic_id==id).delete(synchronize_session=False)
        db.query(GenericSlot).filter(GenericSlot.generic_solution_id==id).delete(synchronize_session=False)
        db.query(CatalogueSourceState).filter(CatalogueSourceState.key==f'g:{next(r["code"] for r in selected if r["id"]==str(id))}').delete(synchronize_session=False)
        db.query(GenericSolution).filter(GenericSolution.id==id).delete(synchronize_session=False)
    db.add(AuditLog(action='ARCHIVED_INSTALLATIONS_CLEANUP',entity='catalogue',entity_id='historical-ins',
                    detail={'records':[{key:row[key] for key in ('id','code','sha256')} for row in selected],
                            'backup_sha256':backup_sha256.lower()}))
    db.flush()
    if db.scalar(select(func.count()).select_from(GenericSolution).where(GenericSolution.id.in_(ids))):
        raise RuntimeError('Cleanup verification failed')
    report['applied']=True
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--manifest',type=Path)
    parser.add_argument('--backup',type=Path)
    parser.add_argument('--backup-sha256')
    args=parser.parse_args()
    engine=create_engine(os.environ['DATABASE_URL'],hide_parameters=True)
    with Session(engine) as db,db.begin():
        result=run(db,engine,args.manifest,args.backup,args.backup_sha256,args.apply)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
