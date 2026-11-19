"""Persistent, idempotent thumbnail queue and opt-in administrative backfill.

No permission flag is changed here. Serving a preview still requires the original
IFC's authorized VIEW policy in documents.py.
"""
import logging
from datetime import timedelta
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from .ifc_thumbnails import cache_thumbnail, thumbnail_path
from .models import Asset, IfcThumbnailJob, now

LOG = logging.getLogger(__name__)
MAX_THUMBNAIL_ATTEMPTS = 3
LEASE = timedelta(minutes=15)


def queue_thumbnail(db, asset: Asset, *, force=False):
    """Add a job for a validated IFC; requeue if content changed or forced."""
    if asset.file_type != 'IFC' or asset.processing_status != 'VALID':
        return False
    db.execute(insert(IfcThumbnailJob).values(
        asset_id=asset.id, source_sha256=asset.sha256, state='PENDING', attempts=0,
    ).on_conflict_do_nothing(index_elements=[IfcThumbnailJob.asset_id]))
    job = db.get(IfcThumbnailJob, asset.id, with_for_update=True)
    if job.source_sha256 != asset.sha256 or force:
        job.source_sha256=asset.sha256
        job.state='PENDING';job.attempts=0;job.started_at=None
        job.finished_at=None;job.next_retry_at=None;job.error_code=None
    return True


def enqueue_missing(engine, *, limit=25):
    """Progressive full-catalogue backfill, without first-page starvation."""
    with Session(engine) as db, db.begin():
        rows=db.scalars(select(Asset).outerjoin(IfcThumbnailJob,
            IfcThumbnailJob.asset_id==Asset.id).where(
            Asset.file_type=='IFC', Asset.processing_status=='VALID',
            or_(IfcThumbnailJob.asset_id.is_(None), IfcThumbnailJob.source_sha256!=Asset.sha256))
            .order_by(Asset.created_at,Asset.id).limit(limit)).all()
        for asset in rows:queue_thumbnail(db,asset)
        return len(rows)


def repair_missing(engine, root: Path, *, limit=200, retry_failed=False):
    """Explicit maintenance tool: requeue vanished cached files and failed jobs."""
    with Session(engine) as db, db.begin():
        candidates=db.scalars(select(Asset).join(IfcThumbnailJob).where(
            Asset.file_type=='IFC',Asset.processing_status=='VALID',
            IfcThumbnailJob.state.in_(['READY','FAILED'] if retry_failed else ['READY']))
            .order_by(Asset.created_at,Asset.id).limit(limit)).all()
        count=0
        for asset in candidates:
            state=db.get(IfcThumbnailJob,asset.id).state
            if (state=='FAILED' and retry_failed) or not thumbnail_path(root,asset.sha256).is_file():
                queue_thumbnail(db,asset,force=True)
                count+=1
        return count


def process_thumbnail(engine, root: Path):
    """Claim one job with PostgreSQL row locking, attempt fencing and bounded retries."""
    with Session(engine) as db, db.begin():
        job=db.scalar(select(IfcThumbnailJob).where(
            or_((IfcThumbnailJob.state=='PENDING') & or_(
                IfcThumbnailJob.next_retry_at.is_(None), IfcThumbnailJob.next_retry_at<=now()),
                (IfcThumbnailJob.state=='PROCESSING') & (IfcThumbnailJob.started_at<now()-LEASE)))
            .order_by(IfcThumbnailJob.started_at.asc().nulls_first(),IfcThumbnailJob.asset_id)
            .limit(1).with_for_update(skip_locked=True))
        if not job:return False
        asset=db.get(Asset,job.asset_id)
        if not asset or asset.file_type!='IFC' or asset.processing_status!='VALID':
            job.state='FAILED';job.error_code='ASSET_NOT_VALID';job.finished_at=now()
            return True
        job.attempts+=1
        attempt=job.attempts
        job.state='PROCESSING';job.started_at=now()
        digest=job.source_sha256
        asset_id=asset.id
        key=asset.storage_key
    success=False;error='GEOMETRY_UNAVAILABLE'
    try:
        source=(root/key).resolve()
        success=cache_thumbnail(root,source,digest)
        if not success:error='GEOMETRY_OR_SHA_MISMATCH'
    except Exception:
        error='THUMBNAIL_RENDER_FAILURE'
        LOG.exception('No se pudo generar la miniatura del IFC %s',asset_id)
    with Session(engine) as db, db.begin():
        job=db.get(IfcThumbnailJob,asset_id,with_for_update=True)
        # Do not overwrite a newer attempt or a requeued changed-source asset.
        if not job or job.state!='PROCESSING' or job.attempts!=attempt or job.source_sha256!=digest:
            return True
        job.finished_at=now()
        job.error_code=None if success else error
        if success:
            job.state='READY';job.next_retry_at=None
        elif attempt>=MAX_THUMBNAIL_ATTEMPTS:
            job.state='FAILED';job.next_retry_at=None
        else:
            job.state='PENDING'
            job.next_retry_at=now()+timedelta(minutes=2**attempt)
    return True
