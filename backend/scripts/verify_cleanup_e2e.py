"""Controlled historical cleanup drill, restricted to disposable E2E data."""
import argparse
import json
import os
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.models import Asset, AuditLog, CommercialSolution, GenericAsset, GenericSolution, Revision, RevisionGeneric
from scripts.cleanup_archived_installations import run


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--backup',type=Path,required=True)
    parser.add_argument('--backup-sha256',required=True)
    args=parser.parse_args()
    if (os.getenv('METRA_TEST_DB')!='1' or os.getenv('METRA_CLEANUP_E2E')!='1'
            or not os.environ['DATABASE_URL'].endswith('/metra_publication_test')):
        raise SystemExit('Disposable E2E database required')
    engine=create_engine(os.environ['DATABASE_URL'],hide_parameters=True)
    with Session(engine) as db:
        preview=run(db,engine)
        candidates=preview['candidates']
        assert len(candidates)==13 and len(preview['excluded_ins_records'])==1
        shared=db.scalar(select(Asset).join(GenericAsset,GenericAsset.asset_id==Asset.id)
            .join(GenericSolution,GenericSolution.id==GenericAsset.generic_id)
            .where(GenericSolution.code=='INS.HIST.E2E.01'))
        assert shared and (Path(os.environ['ASSET_DIR'])/shared.storage_key).is_file()
        manifest=Path('/tmp/historical-ins-reviewed.json')
        manifest.write_text(json.dumps([{key:row[key] for key in ('id','code','sha256')}
                                        for row in candidates]),encoding='utf-8')
        first=next(row for row in candidates if row['code']=='INS.HIST.E2E.01')
        revision=db.scalar(select(Revision).limit(1))
        assert revision
        link=RevisionGeneric(revision_id=revision.id,generic_id=UUID(first['id']))
        db.add(link);db.commit()
        try:
            run(db,engine,manifest,args.backup,args.backup_sha256,True)
        except RuntimeError as error:
            assert 'referenced by a commercial revision' in str(error)
            db.rollback()
        else:
            raise AssertionError('Cleanup accepted an active revision dependency')
        db.delete(db.get(RevisionGeneric,{'revision_id':revision.id,'generic_id':UUID(first['id'])}));db.commit()
        result=run(db,engine,manifest,args.backup,args.backup_sha256,True)
        assert result['applied'];db.commit()
        assert db.scalar(select(func.count()).select_from(GenericSolution).where(
            GenericSolution.code.like('INS.HIST.E2E.%')))==0
        assert db.scalar(select(GenericSolution.id).where(GenericSolution.code=='INS.USER.CREATED'))
        assert db.scalar(select(func.count()).select_from(GenericSolution))==95
        assert db.scalar(select(func.count()).select_from(CommercialSolution))==91
        assert db.get(Asset,shared.id) and (Path(os.environ['ASSET_DIR'])/shared.storage_key).is_file()
        assert db.scalar(select(AuditLog.id).where(AuditLog.action=='ARCHIVED_INSTALLATIONS_CLEANUP'))
        assert run(db,engine,manifest,args.backup,args.backup_sha256,True)['already_applied']
    print('Cleanup E2E: dependency blocked, exact 13 removed, unrelated INS and shared IFC retained, idempotent')


if __name__=='__main__':main()
