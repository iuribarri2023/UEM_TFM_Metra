"""Explicit, reversible-by-backup reconciliation of IFC header metadata in existing volumes.

New installations ingest the normalized metra-demo IFCs directly. An existing database
has stable storage keys and old hashes until the administrator deliberately applies
this migration. No `.env` files are created, read as files, or modified here.

  python scripts/reconcile_metra_demo_ifc.py --backup-dir /safe/external/directory
  python scripts/reconcile_metra_demo_ifc.py --backup-dir /safe/external/directory --apply

Keep the backup directory outside any publicly distributed repository.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.models import Asset, Extraction
from app.parsers import ParseFailure, parse_ifc
from scripts.ifc_inventory import expected_sources

BACKEND=Path(__file__).resolve().parents[1]
CATALOGUE=BACKEND/'data/metra-demo'
COMPATIBILITY=BACKEND/'data/integrity/ifc-metadata-compatibility.json'


def sha256(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()


def candidates():
    mapping=json.loads(COMPATIBILITY.read_text(encoding='utf-8'))
    for _kind, code, key, path in expected_sources():
        if path is None:
            continue
        relative=path.relative_to(CATALOGUE).as_posix()
        pair=mapping.get(relative)
        if pair:
            yield code, key, path, pair[0], pair[1]


def reconcile(db:Session,store:Path,backup:Path,apply:bool)->dict:
    report={'candidates':0,'migrated':0,'already_current':0,'not_imported':0,'errors':[]}
    for code,key,source,old_digest,new_digest in candidates():
        report['candidates']+=1
        asset=db.scalar(select(Asset).where(Asset.storage_key==key))
        if asset is None:
            report['not_imported']+=1
            continue
        target=(store/key).resolve()
        if not target.is_relative_to(store.resolve()) or not target.is_file():
            report['errors'].append(f'{code}: original ausente del volumen')
            continue
        raw=target.read_bytes(); current=sha256(raw)
        if asset.sha256==new_digest and current==new_digest:
            report['already_current']+=1
            continue
        if current!=old_digest or asset.sha256!=old_digest or sha256(source.read_bytes())!=new_digest:
            report['errors'].append(f'{code}: huella inesperada; no se modifica')
            continue
        # Fully parse the new IFC before altering volume or database.
        try:
            normalized=parse_ifc(source.read_bytes())
        except ParseFailure as exc:
            report['errors'].append(f'{code}: IFC normalizado inválido: {exc}')
            continue
        if not apply:
            report['migrated']+=1  # planned, not yet applied
            continue
        backup.mkdir(parents=True, exist_ok=True)
        saved=backup/key
        if saved.exists() and sha256(saved.read_bytes())!=old_digest:
            report['errors'].append(f'{code}: respaldo existente con contenido distinto')
            continue
        if not saved.exists():
            saved.write_bytes(raw)
        if sha256(saved.read_bytes())!=old_digest:
            report['errors'].append(f'{code}: respaldo no verificable')
            continue
        updated=source.read_bytes()
        try:
            staging=store/(key+'.metra-demo.tmp')
            staging.write_bytes(updated)
            os.replace(staging,target)
            asset.sha256=new_digest
            asset.size=len(updated)
            normalized.update(source_dataset='metra-demo',source_path=source.relative_to(CATALOGUE).as_posix(),sha256=new_digest,validation_level='basic_open_and_guid_uniqueness')
            row=db.scalar(select(Extraction).where(Extraction.asset_id==asset.id).order_by(Extraction.created_at.desc(), Extraction.id.desc()))
            if row is None:
                db.add(Extraction(asset_id=asset.id,schema_version='1.0',source_format='IFC',normalized=normalized,warnings=normalized.get('warnings',[]),is_valid=True))
            else:
                row.normalized=normalized
                row.warnings=normalized.get('warnings',[])
                row.is_valid=True
            asset.processing_status='VALID'
            db.commit()
            report['migrated']+=1
        except Exception as exc:
            db.rollback()
            rollback=store/(key+'.rollback.tmp')
            rollback.write_bytes(raw)
            os.replace(rollback,target)
            report['errors'].append(f'{code}: revertido tras error {type(exc).__name__}')
        finally:
            (store/(key+'.metra-demo.tmp')).unlink(missing_ok=True)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup-dir',required=True,type=Path,help='Carpeta externa privada para originales persistentes')
    parser.add_argument('--apply',action='store_true',help='Aplicar; por defecto solo verifica y muestra recuentos')
    args=parser.parse_args()
    store=Path(os.environ.get('ASSET_DIR','/data/assets')).resolve()
    backup=args.backup_dir.resolve()
    if backup.is_relative_to(BACKEND.parents[0].resolve()):
        raise SystemExit('Utiliza una carpeta de respaldo fuera del repositorio METRA')
    if not os.getenv('DATABASE_URL'):
        raise SystemExit('DATABASE_URL requerido')
    engine=create_engine(os.environ['DATABASE_URL'],hide_parameters=True)
    with Session(engine) as db:
        result=reconcile(db,store,backup,args.apply)
    print(json.dumps({'mode':'apply' if args.apply else 'dry-run',**result},ensure_ascii=False,indent=2))
    if result['errors']:
        raise SystemExit(1)


if __name__=='__main__':
    main()
