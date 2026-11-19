"""Historical Data Template fallback drill in the isolated E2E database."""
import json
import os
import sys
from pathlib import Path
from urllib.request import urlopen

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.models import CommercialSolution, Revision


def main():
    if (os.getenv('METRA_TEST_DB')!='1' or os.getenv('METRA_E2E_PROJECT')!='metra-tfm-e2e'
            or not os.environ['DATABASE_URL'].endswith('/metra_publication_test')):
        raise SystemExit('Only the isolated metra-tfm-e2e environment is allowed')
    engine=create_engine(os.environ['DATABASE_URL'],hide_parameters=True)
    with Session(engine) as db:
        item=db.scalar(select(CommercialSolution).where(CommercialSolution.code=='E2E.IFC.P001'))
        assert item and item.published_revision_id
        revision=db.get(Revision,item.published_revision_id)
        original=revision.template_version
        try:
            revision.template_version=999;db.commit()
            with urlopen(f'http://127.0.0.1:8000/api/v1/products/{item.id}',timeout=20) as response:
                projected=json.load(response)['data']['published']['canonical']
            warning=projected['quality']['warnings'][0]
            assert warning['code']=='HISTORICAL_TEMPLATE_FALLBACK'
            assert warning['requested_version']==999 and warning['effective_version']==original
            db.refresh(revision)
            assert revision.template_version==999
        finally:
            revision.template_version=original;db.commit()
    print('Historical template: explicit fallback metadata and immutable stored version OK')


if __name__=='__main__':main()
