"""Create 13 marked historical fixtures and one unrelated INS record in E2E DB."""
import os
import sys
from datetime import timedelta
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.models import (Asset, AuditLog, GenericAsset, GenericSlot, GenericSolution,
                        System, Subsystem, Archetype, now)


def main():
    if (os.getenv('METRA_TEST_DB')!='1' or os.getenv('METRA_CLEANUP_E2E')!='1'
            or not os.environ['DATABASE_URL'].endswith('/metra_publication_test')):
        raise SystemExit('Disposable E2E database required')
    with Session(create_engine(os.environ['DATABASE_URL'],hide_parameters=True)) as db,db.begin():
        assert not db.scalar(select(GenericSolution.id).where(GenericSolution.code.like('INS.HIST.E2E.%')).limit(1))
        system=System(code='INS',name_es='Instalaciones históricas');db.add(system);db.flush()
        sub=Subsystem(code='INS.GEN',name_es='Instalaciones genéricas',system_id=system.id,archived=True)
        db.add(sub);db.flush()
        arch=Archetype(code='INS.GEN.OLD',name_es='Fichas históricas',subsystem_id=sub.id,archived=True)
        db.add(arch);db.flush()
        shared=db.scalar(select(Asset).where(Asset.file_type=='IFC').limit(1))
        assert shared
        for number in range(1,14):
            code=f'INS.HIST.E2E.{number:02d}'
            row=GenericSolution(code=code,name_es=f'Histórica {number}',subsystem_id=sub.id,
                archetype_id=arch.id,status='ARCHIVED',updated_at=now()-timedelta(days=1),
                technical_data={'legacy_source':f'generic_solutions/historical/{code}.json'})
            db.add(row);db.flush()
            db.add(AuditLog(action='RETIRE_INSTALLATIONS',entity='generic_solutions',
                            entity_id=str(row.id),detail={'previous':'DRAFT'}))
            db.add(GenericSlot(generic_solution_id=row.id,code='LAYER',name_es='Capa histórica'))
            if number==1:db.add(GenericAsset(generic_id=row.id,asset_id=shared.id))
        db.add(GenericSolution(code='INS.USER.CREATED',name_es='Ficha ajena',subsystem_id=sub.id,
            archetype_id=arch.id,status='ARCHIVED',technical_data={'user_created':True}))
    print('Cleanup E2E fixtures: 13 historical, one unrelated INS, one shared IFC link')


if __name__=='__main__':main()
