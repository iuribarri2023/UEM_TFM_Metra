"""Versioned HTTP endpoints for assets."""
from ..api_support import (
    ApiError,
    Asset,
    AuditLog,
    CommercialSolution,
    Extraction,
    GenericAsset,
    GenericSolution,
    IntegrityError,
    Manufacturer,
    Path,
    Revision,
    RevisionAsset,
    api,
    audit,
    create_asset,
    current_app,
    data,
    document_policy,
    err,
    func,
    g,
    hashlib,
    ifc_page,
    ifc_row,
    obj,
    or_,
    page_query,
    pk,
    public_query,
    request,
    revision_owned,
    revision_policies,
    role,
    select,
    serialize_generic,
    serialize_revision,
)
from ..documents import queue_document


@api.post('/manufacturer/revisions/<id>/assets')
@role('MANUFACTURER')
def upload_revision_asset(id):
    r,p=revision_owned(id,True)
    if r.status!='DRAFT':err('La revisión está bloqueada','IMMUTABLE',409)
    return create_asset(revision_id=r.id,manufacturer_id=p.manufacturer_id)



@api.patch('/manufacturer/revisions/<id>/assets/<asset_id>')
@role('MANUFACTURER')
def permissions(id,asset_id):
    r,p=revision_owned(id,True)
    if r.status!='DRAFT':err('Revisión inmutable','IMMUTABLE',409)
    link=g.db.get(RevisionAsset,{'revision_id':r.id,'asset_id':pk(asset_id)})
    if not link:err('No encontrado','NOT_FOUND',404)
    document_policy(link,obj(Asset,asset_id),'revision',r.id,request.get_json(silent=True))
    return data({'public_download_allowed':link.public_download_allowed,'public_view_allowed':link.public_view_allowed})



@api.delete('/manufacturer/revisions/<id>/assets/<asset_id>')
@role('MANUFACTURER')
def unlink_asset(id,asset_id):
    r,p=revision_owned(id,True)
    if r.status!='DRAFT':err('Revisión inmutable','IMMUTABLE',409)
    link=g.db.get(RevisionAsset,{'revision_id':r.id,'asset_id':pk(asset_id)})
    if not link:err('No encontrado','NOT_FOUND',404)
    g.db.delete(link);audit('UNLINK_ASSET','revision',r.id)
    return data({'removed':True})



@api.post('/admin/assets/<id>/reprocess')
@role('ADMIN')
def reprocess_asset(id):
    return queue_document(obj(Asset,id),force=True)



@api.post('/admin/generic-solutions/<id>/assets')
@role('ADMIN')
def generic_upload(id):
    x=obj(GenericSolution,id,True)
    if x.status!='DRAFT':err('Solo borradores admiten archivos','IMMUTABLE',409)
    return create_asset(generic_id=x.id)



@api.get('/admin/document-targets')
@role('ADMIN')
def document_targets():
    kind=request.args.get('kind','commercial')
    if kind=='generic':
        query=select(GenericSolution).where(GenericSolution.status.in_(['DRAFT','PUBLISHED']))
        term=request.args.get('q','').strip()[:120]
        if term:query=query.where(or_(GenericSolution.name_es.icontains(term,autoescape=True),
                                      GenericSolution.code.icontains(term,autoescape=True)))
        rows,meta=page_query(query.order_by(GenericSolution.code))
        return data([serialize_generic(row,True,include_extraction=False) for row in rows],meta)
    if kind!='commercial':err('Tipo inválido')
    query=public_query()
    term=request.args.get('q','').strip()[:120]
    if term:query=query.where(or_(Revision.name_es.icontains(term,autoescape=True),
                                  CommercialSolution.code.icontains(term,autoescape=True)))
    rows,meta=page_query(query.order_by(CommercialSolution.code))
    return data([dict(id=str(p.id),code=p.code,**{
        'name_es':rev.name_es,'assets':serialize_revision(rev,True,include_extraction=False)['assets']
    }) for p in rows if (rev:=g.db.get(Revision,p.published_revision_id))],meta)



@api.patch('/admin/products/<id>/assets/<asset_id>')
@role('ADMIN')
def published_permissions(id,asset_id):
    product=obj(CommercialSolution,id,True)
    if not product.published_revision_id:err('Producto sin revisión publicada','NOT_FOUND',404)
    revision=obj(Revision,product.published_revision_id)
    revision_policies(revision,{asset_id:request.get_json(silent=True)})
    return data({'updated':True})



@api.patch('/admin/generic-solutions/<id>/assets/<asset_id>')
@role('ADMIN')
def generic_permissions(id,asset_id):
    x=obj(GenericSolution,id,True)
    if x.status not in ('DRAFT','PUBLISHED'):err('Genérica archivada','IMMUTABLE',409)
    link=g.db.get(GenericAsset,{'generic_id':x.id,'asset_id':pk(asset_id)})
    if not link:err('No encontrado','NOT_FOUND',404)
    document_policy(link,obj(Asset,asset_id),'generic',x.id,request.get_json(silent=True))
    return data({'updated':True})



@api.get('/admin/ifc/inventory')
@role('ADMIN')
def admin_ifc_inventory():
    kind=request.args.get('kind','commercial')
    q=request.args.get('q','').strip()
    if kind not in ('generic','commercial') or len(q)>120:err('Filtro IFC inválido','VALIDATION',422)
    page,size=ifc_page()
    if kind=='generic':
        query=(select(GenericSolution,Asset,GenericAsset)
          .join(GenericAsset,GenericAsset.generic_id==GenericSolution.id)
          .join(Asset,Asset.id==GenericAsset.asset_id)
          .where(Asset.file_type=='IFC'))
        if q:query=query.where(or_(GenericSolution.code.icontains(q,autoescape=True),GenericSolution.name_es.icontains(q,autoescape=True)))
        total=g.db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
        found=g.db.execute(query.order_by(GenericSolution.code,Asset.id).limit(size).offset((page-1)*size)).all()
        rows=[{'kind':kind,'target_id':str(x.id),'code':x.code,'name':x.name_es,'solution_status':x.status,
               **ifc_row(a,link)} for x,a,link in found]
    else:
        latest=(select(Revision.id).where(Revision.product_id==CommercialSolution.id)
            .order_by(Revision.number.desc()).limit(1).correlate(CommercialSolution).scalar_subquery())
        selected_revision=func.coalesce(CommercialSolution.published_revision_id,latest)
        query=(select(CommercialSolution,Revision,Manufacturer,Asset,RevisionAsset)
            .join(Revision,Revision.id==selected_revision)
            .join(Manufacturer,Manufacturer.id==CommercialSolution.manufacturer_id)
            .join(RevisionAsset,RevisionAsset.revision_id==Revision.id)
            .join(Asset,Asset.id==RevisionAsset.asset_id)
            .where(Asset.file_type=='IFC'))
        if q:query=query.where(or_(CommercialSolution.code.icontains(q,autoescape=True),Revision.name_es.icontains(q,autoescape=True),Manufacturer.name.icontains(q,autoescape=True)))
        total=g.db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
        found=g.db.execute(query.order_by(CommercialSolution.code,Asset.id).limit(size).offset((page-1)*size)).all()
        rows=[{'kind':kind,'target_id':str(p.id),'code':p.code,'name':r.name_es,'manufacturer':m.name,
               'solution_status':p.availability,'revision':r.number,**ifc_row(a,link)} for p,r,m,a,link in found]
    if rows:
        changed=g.db.execute(select(AuditLog.detail['asset_id'].astext,AuditLog.at)
            .where(AuditLog.action=='DOCUMENT_POLICY',
                   AuditLog.detail['asset_id'].astext.in_([row['asset_id'] for row in rows]))
            .order_by(AuditLog.at.desc())).all()
        latest={}
        for asset_id,at in changed:latest.setdefault(asset_id,at.isoformat())
        for row in rows:row['last_permission_change_at']=latest.get(row['asset_id'])
    return data(rows,{'page':page,'page_size':size,'total':total})



@api.get('/admin/ifc/<id>/integrity')
@role('ADMIN')
def admin_ifc_integrity(id):
    asset=obj(Asset,id)
    if asset.file_type!='IFC':err('Solo IFC','VALIDATION',422)
    root=Path(current_app.config['ASSET_DIR']).resolve();path=(root/asset.storage_key).resolve()
    if path.parent!=root:err('Ruta de archivo inválida','VALIDATION',422)
    if not path.is_file():status='MISSING';actual=None
    else:
        digest=hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
        actual=digest.hexdigest();status='MATCH' if actual==asset.sha256 else 'MISMATCH'
    extraction=g.db.scalar(select(Extraction).where(Extraction.asset_id==asset.id).order_by(Extraction.created_at.desc(),Extraction.id.desc()))
    return data({'asset_id':str(asset.id),'status':status,'expected_sha256':asset.sha256,
                 'actual_sha256':actual,'extraction_valid':extraction.is_valid if extraction else None,
                 'representable_elements':sum(bool(x.get('has_representation')) for x in (extraction.normalized.get('elements') or [])) if extraction else 0})



@api.get('/admin/ifc/<id>/history')
@role('ADMIN')
def admin_ifc_history(id):
    asset=obj(Asset,id)
    if asset.file_type!='IFC':err('Solo IFC','VALIDATION',422)
    entries,meta=page_query(select(AuditLog).where(AuditLog.action=='DOCUMENT_POLICY',
        AuditLog.detail['asset_id'].astext==str(asset.id)).order_by(AuditLog.at.desc(),AuditLog.id.desc()))
    return data([{'id':str(x.id),'at':x.at.isoformat(),'actor_id':str(x.actor_id) if x.actor_id else None,
                  'detail':x.detail} for x in entries],meta)



@api.post('/admin/ifc/permissions/bulk')
@role('ADMIN')
def admin_ifc_bulk_permissions():
    body=request.get_json(silent=True)
    if not isinstance(body,dict) or body.get('confirmed') is not True:err('Confirma el cambio de permisos','VALIDATION',422)
    targets=body.get('targets')
    if not isinstance(targets,list) or not 1<=len(targets)<=100:err('Selecciona entre 1 y 100 IFC','VALIDATION',422)
    results=[];seen=set()
    for target in targets:
        key=str(target.get('asset_id')) if isinstance(target,dict) else ''
        if key in seen:
            results.append({'asset_id':key,'updated':False,'code':'DUPLICATE','message':'IFC duplicado en el lote'});continue
        seen.add(key)
        try:
            with g.db.begin_nested():
                if not isinstance(target,dict) or target.get('kind') not in ('generic','commercial'):
                    err('Destino IFC inválido','VALIDATION',422)
                kind=target['kind'];target_id=pk(target.get('target_id'));asset_id=pk(target.get('asset_id'))
                asset=obj(Asset,asset_id)
                if asset.file_type!='IFC':err('Solo IFC','VALIDATION',422)
                if kind=='generic':
                    solution=obj(GenericSolution,target_id,True)
                    if solution.status not in ('DRAFT','PUBLISHED'):err('Solución archivada','IMMUTABLE',409)
                    link=g.db.scalar(select(GenericAsset).where(GenericAsset.generic_id==solution.id,
                        GenericAsset.asset_id==asset.id).with_for_update())
                    scope='generic';entity=solution.id
                else:
                    product=obj(CommercialSolution,target_id,True)
                    revision_id=product.published_revision_id or g.db.scalar(select(Revision.id).where(Revision.product_id==product.id).order_by(Revision.number.desc()).limit(1))
                    link=g.db.scalar(select(RevisionAsset).where(RevisionAsset.revision_id==revision_id,
                        RevisionAsset.asset_id==asset.id).with_for_update()) if revision_id else None
                    scope='revision';entity=revision_id
                if link is None:err('El IFC no pertenece a la solución','NOT_FOUND',404)
                expected=target.get('expected')
                if expected is not None:
                    if not isinstance(expected,dict) or type(expected.get('public_view_allowed')) is not bool or type(expected.get('public_download_allowed')) is not bool:
                        err('Permisos originales inválidos','VALIDATION',422)
                    if (link.public_view_allowed!=expected['public_view_allowed'] or
                            link.public_download_allowed!=expected['public_download_allowed']):
                        err('Los permisos cambiaron durante la revisión; actualiza el inventario','CONFLICT',409)
                document_policy(link,asset,scope,entity,target.get('policy'))
            results.append({'asset_id':key,'updated':True,
                'public_view_allowed':link.public_view_allowed,
                'public_download_allowed':link.public_download_allowed})
        except ApiError as exc:
            results.append({'asset_id':key,'updated':False,'code':exc.code,'message':exc.message})
        except IntegrityError:
            results.append({'asset_id':key,'updated':False,'code':'CONFLICT','message':'Conflicto de integridad'})
    return data(results)

