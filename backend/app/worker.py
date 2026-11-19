"""PostgreSQL document queue with leased, fenced attempts."""
import hashlib
import logging
import os
import time
from datetime import timedelta
from pathlib import Path

from sqlalchemy import create_engine, or_, select
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session

from .cost_imports import store_cost_import
from .models import Asset, DocumentJob, Extraction, now
from .thumbnail_jobs import queue_thumbnail, enqueue_missing, process_thumbnail
from .parsers import PARSERS, ParseFailure

LOG = logging.getLogger(__name__)
LEASE = timedelta(minutes=15)


def process_next(engine,root):
    with Session(engine) as db, db.begin():
        job=db.scalar(select(DocumentJob).where(or_(DocumentJob.state=='PENDING',
            (DocumentJob.state=='PROCESSING') & (DocumentJob.started_at<now()-LEASE)))
            .order_by(DocumentJob.started_at.asc().nulls_first(),DocumentJob.asset_id)
            .limit(1).with_for_update(skip_locked=True))
        if not job:return False
        asset=db.get(Asset,job.asset_id)
        job.attempts+=1
        attempt=job.attempts
        job.state=asset.processing_status='PROCESSING'
        job.progress=5
        job.started_at=now()
        key,digest,kind,id=asset.storage_key,asset.sha256,asset.file_type,asset.id
    valid=False
    error=None
    try:
        path=(root/key).resolve()
        if path.parent!=root:raise OSError('Ruta inválida')
        original=path.read_bytes()
        if hashlib.sha256(original).hexdigest()!=digest:
            raise ParseFailure('El original no coincide con su huella SHA-256')
        normalized=PARSERS[kind](original)
        valid=True
    except ParseFailure as exc:
        error='PARSE_FAILURE'
        normalized={'warnings':[str(exc)]}
    except Exception:
        LOG.exception('Fallo al procesar documento %s',id)
        error='PROCESSING_FAILURE'
        normalized={'warnings':['No se pudo procesar el original.']}
    with Session(engine) as db, db.begin():
        job=db.get(DocumentJob,id,with_for_update=True)
        if job.attempts!=attempt or job.state!='PROCESSING':return True
        asset=db.get(Asset,id)
        if valid and kind=='BC3':
            try:
                with db.begin_nested():
                    store_cost_import(db, asset, normalized)
            except (DataError, IntegrityError):
                LOG.exception('No se pudo materializar la importación BC3 %s',id)
                valid=False
                error='IMPORT_PERSISTENCE_FAILURE'
                normalized={'warnings':['No se pudieron persistir los conceptos de la base.']}
        job.state=asset.processing_status='VALID' if valid else 'INVALID'
        job.finished_at=now()
        job.progress=100
        job.error_code=error
        previous=db.scalar(select(Extraction).where(Extraction.asset_id==id)
            .order_by(Extraction.created_at.desc(),Extraction.id).limit(1))
        if previous is None or previous.is_valid != valid or previous.normalized != normalized:
            db.add(Extraction(asset_id=id,source_format=kind,normalized=normalized,
                              schema_version=normalized.get('schema_version','1.0'),
                              warnings=normalized.get('warnings',[]),is_valid=valid))
        if valid and kind=='IFC':
            queue_thumbnail(db,asset)
    return True


def main():
    logging.basicConfig(level=logging.INFO)
    engine=create_engine(os.environ['DATABASE_URL'],pool_pre_ping=True,hide_parameters=True)
    root=Path(os.environ.get('ASSET_DIR','/data/assets')).resolve()
    while True:
        try:
            # Parsing remains the first priority; thumbnails are derived asynchronously.
            if process_next(engine,root):continue
            if enqueue_missing(engine):continue
            if process_thumbnail(engine,root):continue
        except Exception:
            LOG.exception('Cola documental/miniaturas no disponible')
        time.sleep(2)


if __name__=='__main__':main()
