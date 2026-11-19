"""Create a few unpublished source generics before normal isolated bootstrap."""
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.models import GenericSolution, CommercialSolution
from scripts.import_metra_demo import source_documents,import_generic


def main():
    if (os.getenv('METRA_TEST_DB')!='1' or os.getenv('METRA_PARTIAL_E2E')!='1'
            or not os.environ['DATABASE_URL'].endswith('/metra_publication_test')):
        raise SystemExit('Disposable E2E database required')
    root=Path(__file__).resolve().parents[1]/'data/metra-demo'
    path,doc=next(source_documents(root,'generic_solutions'))
    with Session(create_engine(os.environ['DATABASE_URL'],hide_parameters=True)) as db,db.begin():
        assert db.scalar(select(func.count()).select_from(GenericSolution))==0
        assert db.scalar(select(func.count()).select_from(CommercialSolution))==0
        created,_,warnings=import_generic(db,root,path,doc,Path(os.environ['ASSET_DIR']),False)
        assert created>0 and not warnings
    print(f'Partial E2E seed: {created} unpublished generic records, no assets')


if __name__=='__main__':main()
