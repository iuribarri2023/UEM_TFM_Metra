"""Bounded access to document metadata and domain extracts."""
from pathlib import Path

from flask import current_app, g, request, send_file
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert

from .api_support import api, asset_access, audit, authorized_asset, data, err, fields
from .ifc_thumbnails import thumbnail_path
from .models import Asset, DocumentJob, Extraction, IfcThumbnailJob, now
from .security import get_user

ARRAYS={'IFC':'elements','BC3':'concepts','EPD':'impacts'}


def document(id):
    asset=g.db.get(Asset,id) if not isinstance(id,str) else None
    if asset is None:
        from .api_support import obj
        asset=obj(Asset,id)
    # For an IFC, either permitted distribution mode can authorize inspection.
    if asset.file_type=='IFC':
        from .api_support import ApiError
        try:return authorized_asset(asset.id,'view')
        except ApiError as exc:
            if exc.status!=404:raise
    return authorized_asset(asset.id,'download')


def managed_document(id):
    from .api_support import obj
    u=get_user()
    asset=obj(Asset,id)
    if u.role!='ADMIN' and (not u.manufacturer_id or asset.manufacturer_id!=u.manufacturer_id):
        err('Documento no encontrado','NOT_FOUND',404)
    return asset


def queue_document(asset,force=False):
    created=g.db.scalar(insert(DocumentJob).values(asset_id=asset.id,state='PENDING')
        .on_conflict_do_nothing(index_elements=[DocumentJob.asset_id]).returning(DocumentJob.asset_id))
    job=g.db.get(DocumentJob,asset.id,with_for_update=True)
    if not created:
        if job.state in ('PROCESSING','PENDING'):
            return data({'id':str(asset.id),'processing_status':job.state},status=202)
        if not force and job.state=='VALID':
            err('El documento ya es válido','CONFLICT',409)
        job.state='PENDING';job.progress=0;job.started_at=None;job.finished_at=None;job.error_code=None
    asset.processing_status='PENDING'
    audit('QUEUE_DOCUMENT','asset',asset.id)
    return data({'id':str(asset.id),'processing_status':'PENDING'},status=202)


def extraction_query(asset):
    return select(Extraction.id).where(Extraction.asset_id==asset.id).order_by(
        Extraction.created_at.desc(),Extraction.id).limit(1).scalar_subquery()


@api.get('/documents/<id>')
def document_metadata(id):
    asset=document(id)
    return data(fields(asset,['id','original_name','file_type','size','sha256','processing_status']))


@api.get('/documents/<id>/processing')
def document_processing(id):
    asset=document(id)
    job=g.db.get(DocumentJob,asset.id)
    warnings=g.db.scalar(select(Extraction.warnings).where(Extraction.id==extraction_query(asset))) or []
    return data({'state':job.state if job else asset.processing_status,
                 'progress':job.progress if job else 100,'attempts':job.attempts if job else 0,
                 'started_at':job.started_at.isoformat() if job and job.started_at else None,
                 'finished_at':job.finished_at.isoformat() if job and job.finished_at else None,
                 'error_code':job.error_code if job else None,'warnings':warnings[:50]})


@api.post('/documents/<id>/retry')
def document_retry(id):
    return queue_document(managed_document(id))


@api.post('/documents/<id>/cancel')
def document_cancel(id):
    asset=managed_document(id)
    job=g.db.get(DocumentJob,asset.id,with_for_update=True)
    if not job or job.state!='PENDING':err('Solo se puede cancelar un trabajo en cola','CONFLICT',409)
    job.state='CANCELLED';job.finished_at=now()
    asset.processing_status='INVALID'
    audit('CANCEL_DOCUMENT','asset',asset.id)
    return data({'state':'CANCELLED'})


@api.get('/documents/<id>/summary')
def document_summary(id):
    asset=document(id)
    expression=Extraction.normalized
    for key in ('records','concepts','elements','impacts'):
        from sqlalchemy import literal
        expression=expression.op('-')(literal(key))
    summary=g.db.scalar(select(expression).where(Extraction.id==extraction_query(asset))) or {}
    return data(summary)


@api.get('/documents/<id>/download')
def document_download(id):
    return asset_access(id,'download')


@api.get('/documents/<id>/thumbnail')
def document_thumbnail(id):
    asset = authorized_asset(id, 'view')
    if asset.file_type != 'IFC' or asset.processing_status != 'VALID':
        err('Miniatura no disponible', 'NOT_FOUND', 404)
    root = Path(current_app.config['ASSET_DIR']).resolve()
    try:
        path = thumbnail_path(root, asset.sha256).resolve()
    except ValueError:
        err('Miniatura no disponible', 'NOT_FOUND', 404)
    if path.parent != root / '.ifc-thumbnails' or not path.is_file():
        err('Miniatura no disponible', 'NOT_FOUND', 404)
    response = send_file(path, mimetype='image/svg+xml', conditional=False)
    response.headers['Cache-Control'] = 'private, no-store'
    return response


@api.get('/documents/<id>/thumbnail-processing')
def document_thumbnail_processing(id):
    """Authorized users can check derived-preview progress; never changes view rights."""
    asset=authorized_asset(id,'view')
    if asset.file_type != 'IFC':
        err('Se requiere un IFC', 'VALIDATION', 422)
    job=g.db.get(IfcThumbnailJob,asset.id)
    root=Path(current_app.config['ASSET_DIR']).resolve()
    available=asset.processing_status=='VALID' and thumbnail_path(root,asset.sha256).is_file()
    return data({'available':available,'state':job.state if job else 'NOT_QUEUED',
                 'attempts':job.attempts if job else 0,
                 'error_code':job.error_code if job else None,
                 'source_current':bool(job and job.source_sha256==asset.sha256)})


@api.get('/documents/<id>/ifc-tree')
def document_ifc_tree(id):
    asset = authorized_asset(id, 'view')
    if asset.file_type != 'IFC' or asset.processing_status != 'VALID':
        err('Se requiere un IFC válido', 'VALIDATION', 422)
    extraction_id = g.db.scalar(select(extraction_query(asset)))
    truncated = g.db.scalar(select(Extraction.normalized['index_truncated'].as_boolean())
                            .where(Extraction.id==extraction_id))
    rows = list(g.db.scalars(text("""
        SELECT jsonb_build_object(
            'id', value->'id', 'global_id', value->'global_id',
            'name', value->'name', 'ifc_class', value->'ifc_class',
            'composition_parent_id', value->'composition_parent_id',
            'composition_relation', value->'composition_relation',
            'has_representation', value->'has_representation')
        FROM asset_extractions
        CROSS JOIN LATERAL jsonb_array_elements(normalized -> 'elements')
            WITH ORDINALITY AS entry(value,n)
        WHERE id=:id AND is_valid ORDER BY n LIMIT 10001
    """), {'id': extraction_id}))
    return data(rows[:10000], {'truncated': bool(truncated) or len(rows) > 10000})


@api.get('/documents/<id>/data')
def document_data(id):
    asset=document(id)
    if asset.processing_status!='VALID':
        return data([],{'total':0,'page':1,'page_size':0})
    try:page=int(request.args.get('page',1));size=int(request.args.get('page_size',50))
    except ValueError:err('Paginación inválida','VALIDATION',422)
    if not 1<=page<=10000 or not 1<=size<=100:err('Paginación inválida','VALIDATION',422)
    key=ARRAYS[asset.file_type]
    term=request.args.get('q','').strip()[:150]
    params={'id':g.db.scalar(select(extraction_query(asset))),'key':key,'q':term,
            'size':size,'offset':(page-1)*size}
    condition="""WHERE position(lower(:q) in lower(concat_ws(' ',
         value->>'name',value->>'global_id',value->>'code',value->>'description',
         value->>'indicator',value->>'module'))) > 0"""
    if not term:
        count=g.db.scalar(text("""SELECT jsonb_array_length(normalized -> CAST(:key AS text))
                                 FROM asset_extractions WHERE id=:id"""),params) or 0
        rows=g.db.scalars(text("""
            SELECT value FROM asset_extractions
            CROSS JOIN LATERAL jsonb_array_elements(normalized -> CAST(:key AS text))
            WITH ORDINALITY AS entry(value,n) WHERE id=:id ORDER BY n LIMIT :size OFFSET :offset
            """),params)
    else:
        source=""" FROM (SELECT value,n FROM asset_extractions CROSS JOIN LATERAL
          jsonb_array_elements(normalized -> CAST(:key AS text)) WITH ORDINALITY AS entry(value,n)
          WHERE id=:id) entries """
        count=g.db.scalar(text('SELECT count(*)'+source+condition),params)
        rows=g.db.scalars(text('SELECT value'+source+condition+' ORDER BY n LIMIT :size OFFSET :offset'),params)
    return data(list(rows),{'total':count,'page':page,'page_size':size})
