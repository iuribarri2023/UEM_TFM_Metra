
import argparse
import hashlib
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.models import Asset, Extraction
from app.parsers import parse_ifc

parser = argparse.ArgumentParser()
parser.add_argument('--apply', action='store_true')
parser.add_argument('--limit', type=int)
args = parser.parse_args()

engine = create_engine(os.environ['DATABASE_URL'], pool_pre_ping=True)
store = Path(os.environ.get('ASSET_DIR', '/data/assets'))

validos = 0
errores = 0

with Session(engine) as db:
    query = select(Asset).where(
        Asset.file_type == 'IFC',
        Asset.processing_status == 'INVALID'
    ).order_by(Asset.created_at, Asset.id)

    if args.limit:
        query = query.limit(args.limit)

    assets = db.scalars(query).all()
    print('Archivos seleccionados:', len(assets), '| Aplicar:', args.apply, flush=True)

    for asset in assets:
        try:
            contenido = (store / asset.storage_key).read_bytes()

            if hashlib.sha256(contenido).hexdigest() != asset.sha256:
                raise ValueError('SHA256 distinto; no se modifica')

            resultado = parse_ifc(contenido)

            extraccion = db.scalar(select(Extraction).where(
                Extraction.asset_id == asset.id,
                Extraction.source_format == 'IFC'
            ).order_by(Extraction.created_at.desc(), Extraction.id.desc()))

            if args.apply:
                anterior = extraccion.normalized if extraccion and isinstance(extraccion.normalized, dict) else {}

                resultado.update({
                    'source_dataset': anterior.get('source_dataset', 'metra-demo'),
                    'source_path': anterior.get('source_path'),
                    'sha256': asset.sha256,
                    'validation_level': 'basic_open_and_guid_uniqueness'
                })

                if extraccion:
                    extraccion.normalized = resultado
                    extraccion.warnings = resultado.get('warnings', [])
                    extraccion.is_valid = True
                else:
                    db.add(Extraction(
                        asset_id=asset.id,
                        schema_version='1.0',
                        source_format='IFC',
                        normalized=resultado,
                        warnings=resultado.get('warnings', []),
                        is_valid=True
                    ))

                asset.processing_status = 'VALID'
                db.commit()

            validos += 1
            print('OK:', asset.original_name, 'entidades:', resultado['entity_count'], flush=True)

        except Exception as exc:
            db.rollback()
            errores += 1
            print('ERROR:', asset.original_name, type(exc).__name__, str(exc), flush=True)

print('RESULTADO: validos=', validos, 'errores=', errores, 'aplicado=', args.apply, flush=True)
