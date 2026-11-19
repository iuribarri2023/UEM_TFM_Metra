"""Destructive IFC recovery drill; only for the isolated metra-tfm-e2e volume."""
import hashlib
import os
import sys
import tempfile
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.models import Asset
from scripts import audit_asset_storage as storage_audit
from scripts.ifc_inventory import expected_sources


def main():
    if (os.getenv('METRA_TEST_DB')!='1' or os.getenv('METRA_E2E_PROJECT')!='metra-tfm-e2e'
            or not os.environ['DATABASE_URL'].endswith('/metra_publication_test')):
        raise SystemExit('Only the isolated metra-tfm-e2e database and volume are allowed')
    store=Path(os.environ['ASSET_DIR']).resolve()
    sources=list(expected_sources())
    kind,code,key,source=next(row for row in sources if row[3] and row[3].is_file())
    with Session(create_engine(os.environ['DATABASE_URL'],hide_parameters=True)) as db:
        asset=db.scalar(select(Asset).where(Asset.storage_key==key))
        assert asset and hashlib.sha256(source.read_bytes()).hexdigest()==asset.sha256
        target=store/key
        assert target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest()==asset.sha256
        try:
            target.unlink()
            with tempfile.TemporaryDirectory() as scratch:
                wrong=Path(scratch)/'untrusted.ifc';wrong.write_bytes(b'wrong source')
                original=storage_audit.expected_sources
                storage_audit.expected_sources=lambda:iter([(kind,code,key,wrong)])
                try:
                    refused=storage_audit.audit(db,store,apply=True,restore=True)
                finally:
                    storage_audit.expected_sources=original
                assert key in refused['missing'] and key not in refused['restored'] and not target.exists()
            restored=storage_audit.audit(db,store,apply=True,restore=True)
            assert key in restored['restored'] and hashlib.sha256(target.read_bytes()).hexdigest()==asset.sha256
            target.write_bytes(b'wrong existing bytes')
            corrupt=storage_audit.audit(db,store,apply=True,restore=True)
            assert key in corrupt['wrong_hash'] and target.read_bytes()==b'wrong existing bytes'
        finally:
            if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()!=asset.sha256:
                target.unlink()
            if not target.exists():storage_audit.audit(db,store,apply=True,restore=True)
        assert target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest()==asset.sha256
    print('IFC recovery: verified restore, mismatched-source refusal, no overwrite, cleanup OK')


if __name__=='__main__':main()
