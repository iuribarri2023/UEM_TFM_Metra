"""Versioned HTTP endpoints for cost imports."""
from ..api_support import (
    Asset,
    CostImport,
    DocumentJob,
    PriceBook,
    PriceBookVersion,
    api,
    audit,
    create_asset,
    data,
    err,
    g,
    get_user,
    page_query,
    request,
    role,
    select,
)


@api.post('/cost-databases/imports')
@role('ADMIN')
def import_cost_database():
    name = request.form.get('name','').strip()
    if not 1 <= len(name) <= 180:
        err('Nombre de base de costes obligatorio')
    from sqlalchemy.dialects.postgresql import insert
    g.db.execute(insert(PriceBook).values(name=name).on_conflict_do_nothing(index_elements=['name']))
    book = g.db.scalar(select(PriceBook).where(PriceBook.name==name).with_for_update())
    if book.archived:err('Base de costes archivada','CONFLICT',409)
    asset = create_asset(expected_type='BC3',return_asset=True)
    version = g.db.scalar(select(PriceBookVersion.id).where(
        PriceBookVersion.book_id==book.id, PriceBookVersion.sha256==asset.sha256))
    queued = g.db.scalar(select(CostImport.asset_id).join(Asset).where(
        CostImport.book_id==book.id, Asset.sha256==asset.sha256))
    if version or queued:
        err('La base ya contiene este original o su trabajo de importación','CONFLICT',409)
    g.db.add(CostImport(asset_id=asset.id,book_id=book.id,actor_id=get_user().id))
    audit('QUEUE_COST_IMPORT','cost-database',book.id,{'asset_id':str(asset.id)})
    return data({'id':str(book.id),'asset_id':str(asset.id),'state':'PENDING'},status=202)



@api.get('/cost-databases/imports')
@role('ADMIN')
def list_cost_imports():
    query = (select(CostImport)
             .join(Asset, Asset.id == CostImport.asset_id)
             .order_by(Asset.created_at.desc(), CostImport.asset_id))
    jobs,meta=page_query(query)
    result=[]
    for job in jobs:
        book=g.db.get(PriceBook,job.book_id)
        asset=g.db.get(Asset,job.asset_id)
        state=g.db.get(DocumentJob,job.asset_id)
        result.append({'id':str(book.id),'name':book.name,'asset_id':str(asset.id),
                       'original_name':asset.original_name,'state':state.state,
                       'progress':state.progress,'attempts':state.attempts,'error_code':state.error_code,
                       'version_id':str(job.version_id) if job.version_id else None,
                       'concept_count':job.concept_count})
    return data(result,meta)

