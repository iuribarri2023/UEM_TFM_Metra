"""Inventory PostgreSQL/document-volume consistency; recover missing METRA-DEMO IFCs safely.

No files are removed automatically. Use --restore-missing --apply only when the
source SHA equals the immutable recorded SHA-256. --quarantine-orphans --apply
moves unreferenced, aged IFCs to a private backup directory (never deletes them).
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path
from sqlalchemy import create_engine,select
from sqlalchemy.orm import Session

BACKEND=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BACKEND))
from app.models import Asset
from app.asset_staging import promote_if_absent
from scripts.ifc_inventory import expected_sources


def digest(file):
    h=hashlib.sha256()
    with file.open('rb') as inp:
        for block in iter(lambda:inp.read(1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def audit(db,store:Path,*,apply=False,restore=False,quarantine=False,backup=None,age_hours=24):
    store=store.resolve()
    catalogued={key:path for _,_,key,path in expected_sources() if path is not None}
    rows={asset.storage_key:asset for asset in db.scalars(select(Asset))}
    result={'records':len(rows),'missing':[],'wrong_hash':[],'recoverable':[],
            'orphans':[],'quarantined':[],'restored':[],'staged':[]}
    for key,asset in rows.items():
        path=(store/key).resolve()
        if path.parent!=store:
            result['wrong_hash'].append(key+': unsafe path')
            continue
        if not path.is_file():
            result['missing'].append(key)
            source=catalogued.get(key)
            if source and source.is_file() and digest(source)==asset.sha256:
                result['recoverable'].append(key)
                if restore and apply:
                    promote_if_absent(store,key,source.read_bytes(),sha256=asset.sha256)
                    result['restored'].append(key)
            continue
        if digest(path)!=asset.sha256:
            result['wrong_hash'].append(key)
    if store.exists():
        for file in store.iterdir():
            if not file.is_file() or file.is_symlink():continue
            if file.name.startswith('.stage-') or file.name.endswith('.tmp'):
                result['staged'].append(file.name)
            elif file.suffix.lower()=='.ifc' and file.name not in rows:
                result['orphans'].append(file.name)
                if quarantine and apply and time.time()-file.stat().st_mtime>=age_hours*3600:
                    if backup is None:raise ValueError('External backup required for quarantine')
                    safe_backup=backup.resolve()
                    if safe_backup==store or safe_backup.is_relative_to(store) or store.is_relative_to(safe_backup):
                        raise ValueError('Quarantine must be outside storage volume')
                    safe_backup.mkdir(parents=True,exist_ok=True)
                    to=safe_backup/file.name
                    old=digest(file)
                    if to.exists():
                        if digest(to)!=old:raise ValueError('Backup name collision')
                    else:
                        shutil.copy2(file,to)
                    if digest(to)!=old:raise ValueError('Backup verification failed')
                    file.unlink()
                    result['quarantined'].append(file.name)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--restore-missing',action='store_true')
    parser.add_argument('--quarantine-orphans',action='store_true')
    parser.add_argument('--backup-dir',type=Path)
    parser.add_argument('--min-age-hours',type=int,default=24)
    args=parser.parse_args()
    if args.min_age_hours<24:parser.error('At least 24 hours retention required')
    if args.quarantine_orphans and args.apply and args.backup_dir is None:
        parser.error('External --backup-dir required to quarantine')
    if not os.environ.get('DATABASE_URL'):
        parser.error('DATABASE_URL required')
    engine=create_engine(os.environ['DATABASE_URL'],hide_parameters=True)
    with Session(engine) as db:
        output=audit(db,Path(os.getenv('ASSET_DIR','/data/assets')),
            apply=args.apply,restore=args.restore_missing,quarantine=args.quarantine_orphans,
            backup=args.backup_dir,age_hours=args.min_age_hours)
    print(json.dumps(output,indent=2,ensure_ascii=False))
    if output['wrong_hash'] or len(output['missing'])>len(output['restored']):
        raise SystemExit(1)


if __name__=='__main__':main()
