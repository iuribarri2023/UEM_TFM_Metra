"""Three-way reconciliation against a disposable PostgreSQL database."""
from copy import deepcopy
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import source_reconciliation as source_reconciliation
from app.models import Base, Archetype, GenericSolution, Subsystem, System

pytestmark=pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'),reason='Requires disposable test PostgreSQL')


def test_nested_merge_conflict_baseline_and_published_proposal(tmp_path,monkeypatch):
    engine=create_engine(os.environ['TEST_DATABASE_URL'],hide_parameters=True)
    Base.metadata.drop_all(engine);Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            system=System(code='REC',name_es='Reconciliación');db.add(system);db.flush()
            sub=Subsystem(code='REC.FAC',name_es='Fachada',system_id=system.id);db.add(sub);db.flush()
            archetype=Archetype(code='REC.FAC.A',name_es='Arquetipo',subsystem_id=sub.id)
            db.add(archetype);db.flush()
            item=GenericSolution(code='REC.GS001',name_es='Ensayo',subsystem_id=sub.id,
                archetype_id=archetype.id,status='DRAFT',composition=[],economic_data={},environmental_data={},
                technical_data={'thermal':{'value':1,'unit':'W'},'acoustic':{'value':30,'unit':'dB'}})
            db.add(item);db.flush()
            _,_,baseline=source_reconciliation.persisted_values(db,'g',item.code)
            source_reconciliation.store_baseline(db,'g:'+item.code,baseline)
            db.commit()
            source=deepcopy(baseline)
            source['technical_data']['thermal']['value']=2
            target=deepcopy(item.technical_data)
            target['acoustic']['value']=40
            item.technical_data=target;db.commit()
            entry=lambda root:iter([('g','g:'+item.code,root/'source.json',{},
                                     {'code':item.code,'assets':[]},source)])
            monkeypatch.setattr(source_reconciliation,'source_entries',entry)
            report=source_reconciliation.reconcile(db,tmp_path,tmp_path,apply=True)
            assert report['counts']['updated']==1 and report['counts']['conflicts']==0
            db.commit();db.refresh(item)
            assert item.technical_data['thermal']['value']==2
            assert item.technical_data['acoustic']['value']==40
            state=source_reconciliation.get_state(db,'g:'+item.code)
            assert state.baseline['technical_data']['thermal']['value']==2
            source['technical_data']['thermal']['value']=3
            target=deepcopy(item.technical_data);target['thermal']['value']=4
            item.technical_data=target;db.commit()
            report=source_reconciliation.reconcile(db,tmp_path,tmp_path,apply=True)
            assert report['counts']['conflicts']==1
            assert 'technical_data/thermal/value' in state.pending
            assert state.baseline['technical_data']['thermal']['value']==2
            db.rollback();db.refresh(item);db.refresh(state)
            item.status='PUBLISHED'
            source['technical_data']['thermal']['value']=5
            item.technical_data={**item.technical_data,'thermal':{'value':2,'unit':'W'}}
            db.commit()
            report=source_reconciliation.reconcile(db,tmp_path,tmp_path,apply=True)
            assert report['counts']['proposed']==1 and report['counts']['updated']==0
            assert item.technical_data['thermal']['value']==2
            assert state.baseline['technical_data']['thermal']['value']==2
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
