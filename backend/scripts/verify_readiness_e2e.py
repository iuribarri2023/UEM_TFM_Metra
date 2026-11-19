"""Exercise DEGRADED and BLOCKED on the isolated E2E installation only."""
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.models import CatalogueSourceState
from scripts.audit_asset_storage import audit
from scripts.ifc_inventory import expected_sources


def ready():
    try:
        with urlopen('http://127.0.0.1:8000/ready',timeout=20) as response:
            return response.status,json.load(response)
    except HTTPError as error:
        return error.code,json.load(error)


def main():
    if (os.getenv('METRA_TEST_DB')!='1' or os.getenv('METRA_E2E_PROJECT')!='metra-tfm-e2e'
            or not os.environ['DATABASE_URL'].endswith('/metra_publication_test')):
        raise SystemExit('Only the isolated metra-tfm-e2e environment is allowed')
    engine=create_engine(os.environ['DATABASE_URL'],hide_parameters=True)
    with Session(engine) as db:
        state=db.scalar(select(CatalogueSourceState).where(CatalogueSourceState.status=='SYNCED').limit(1))
        assert state is not None
        previous=state.status,dict(state.pending)
        try:
            state.status='CONFLICT';state.pending={'e2e_probe':{'operation':'CONFLICT'}};db.commit()
            code,result=ready()
            assert code==200 and result['state']=='DEGRADED' and result['reconciliation']['conflicts']>=1
        finally:
            state.status,state.pending=previous;db.commit()
        key=next(key for _,_,key,source in expected_sources() if source and source.is_file())
        target=Path(os.environ['ASSET_DIR'])/key
        assert target.is_file()
        try:
            target.unlink()
            code,result=ready()
            assert code==503 and result['state']=='BLOCKED' and result['ifc']['missing']>=1
        finally:
            if not target.exists():audit(db,Path(os.environ['ASSET_DIR']),apply=True,restore=True)
        code,result=ready()
        assert code==200 and result['state']!='BLOCKED'
    print('Readiness: DEGRADED conflict, BLOCKED missing original, verified recovery OK')


if __name__=='__main__':main()
