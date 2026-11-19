"""Versioned HTTP endpoints for admin."""
from ..api_support import (
    ApiError,
    Archetype,
    Asset,
    AuditLog,
    CatalogueDTO,
    CommercialSolution,
    GenericAsset,
    GenericSlot,
    GenericSolution,
    IntegrityError,
    MODELS,
    Manufacturer,
    Notification,
    Revision,
    RevisionAsset,
    Subsystem,
    System,
    api,
    audit,
    data,
    decision,
    decision_reason,
    dto,
    err,
    fields,
    func,
    g,
    get_user,
    ifc_counts,
    issue_invitation,
    obj,
    or_,
    page_query,
    pk,
    publish_legacy_generic,
    publish_legacy_product,
    request,
    role,
    select,
    serialize_generic,
    serialize_product,
    serialize_revision,
)


@api.get('/admin/manufacturers')
@role('ADMIN')
def admin_manufacturers():
    rows,meta=page_query(select(Manufacturer).order_by(Manufacturer.name,Manufacturer.code))
    return data([fields(row,['id','code','name','status','contact_public']) for row in rows],meta)



@api.post('/admin/manufacturers/<id>/invitations')
@role('ADMIN')
def invite_manufacturer(id):
    manufacturer=obj(Manufacturer,id)
    if manufacturer.status!='ACTIVE':err('Fabricante inactivo','CONFLICT',409)
    body=request.get_json(silent=True)
    if not isinstance(body,dict):err('Se requiere un objeto JSON')
    evidence=body.get('evidence')
    if not isinstance(evidence,str) or not 10<=len(evidence.strip())<=2000:
        err('Registra la evidencia de representación','VALIDATION',422)
    response=issue_invitation(manufacturer.id,get_user())
    audit('VERIFY_ORGANIZATION','manufacturer',manufacturer.id,{'evidence':evidence})
    return response



@api.get('/admin/reviews')
@role('ADMIN')
def reviews_queue():
    q=select(Revision).where(Revision.status=='SUBMITTED').order_by(Revision.submitted_at)
    xs,meta=page_query(q);return data([serialize_revision(r,True,include_extraction=False) for r in xs],meta)



@api.get('/admin/reviews/<id>')
@role('ADMIN')
def review_detail(id):
    r=obj(Revision,id);return data(serialize_revision(r,True))



@api.post('/admin/reviews/bulk-approve')
@role('ADMIN')
def bulk_approve():
    body=request.get_json(silent=True) or {}
    if not isinstance(body,dict):err('Se requiere un objeto JSON')
    ids=body.get('ids')
    if not isinstance(ids,list) or not 1<=len(ids)<=100 or body.get('confirmed') is not True:
        err('Selecciona 1–100 revisiones y confirma')
    reason=decision_reason()
    policies=body.get('document_permissions',{})
    if not isinstance(policies,dict):err('Políticas documentales inválidas')
    outcome=[]
    for id in sorted({pk(item) for item in ids}):
        try:
            with g.db.begin_nested():
                decision(id,True,reason,policies=policies.get(str(id)))
            outcome.append({'id':str(id),'published':True})
        except ApiError as exc:
            outcome.append({'id':str(id),'published':False,'message':exc.message,'details':exc.details})
    return data(outcome)



@api.post('/admin/reviews/<id>/corrections')
@role('ADMIN')
def request_corrections(id):
    return data(serialize_product(decision(id,False,decision_reason(),corrections=True),True))



@api.post('/admin/reviews/<id>/approve')
@role('ADMIN')
def approve(id):return data(serialize_product(decision(id,True,decision_reason(),policies=(request.get_json(silent=True) or {}).get('document_permissions')),True))



@api.post('/admin/reviews/<id>/reject')
@role('ADMIN')
def reject(id):return data(serialize_product(decision(id,False,decision_reason()),True))



@api.get('/admin/catalogue/<kind>')
@role('ADMIN')
def admin_catalogue_list(kind):
    model=MODELS.get(kind)
    if not model:err('Entidad desconocida','NOT_FOUND',404)
    query=select(model).order_by(model.created_at.desc())
    if model is GenericSolution and request.args.get('status'):
        query=query.where(GenericSolution.status==request.args['status'])
    xs,meta=page_query(query)
    return data([serialize_generic(x,True,include_extraction=False) if isinstance(x,GenericSolution) else fields(x,[c.key for c in model.__table__.columns if c.key not in ('created_at','updated_at')]) for x in xs],meta)



@api.get('/admin/catalogue/<kind>/<id>')
@role('ADMIN')
def admin_catalogue_detail(kind,id):
    model=MODELS.get(kind)
    if not model:err('Entidad desconocida','NOT_FOUND',404)
    rec=obj(model,id)
    if isinstance(rec,GenericSolution):return data(serialize_generic(rec,True))
    return data(fields(rec,[c.key for c in model.__table__.columns if c.key not in ('created_at','updated_at')]))



@api.post('/admin/legacy/publications')
@role('ADMIN')
def publish_legacy():
    """Publish reviewed metadata while keeping the original revision private."""
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        err('Se requiere un objeto JSON')
    selection = body.get('ids')
    evidence = body.get('evidence')
    kind = body.get('kind')
    if (not isinstance(selection, list) or not 1 <= len(selection) <= 100
            or not isinstance(evidence, str) or not 10 <= len(evidence.strip()) <= 2000
            or kind not in ('commercial', 'generic') or body.get('confirmed') is not True):
        err('Selecciona 1–100 fichas, registra evidencia y confirma')
    policies=body.get('document_permissions',{})
    if not isinstance(policies,dict):err('Políticas documentales inválidas')
    ids = sorted({pk(value) for value in selection})
    results = []
    for item in ids:
        try:
            with g.db.begin_nested():
                if kind == 'generic':
                    publish_legacy_generic(item, evidence, policies.get(str(item)))
                else:
                    publish_legacy_product(item, evidence, policies.get(str(item)))
            results.append({'id':str(item), 'published':True})
        except ApiError as exc:
            results.append({'id':str(item), 'published':False, 'message':exc.message,
                            'code':exc.code,'details':exc.details})
        except IntegrityError:
            results.append({'id':str(item),'published':False,'message':'Conflicto de integridad al publicar',
                            'code':'CONFLICT','details':[]})
    return data(results)



@api.get('/admin/overview')
@role('ADMIN')
def admin_overview():
    counts={
        'systems':g.db.scalar(select(func.count()).select_from(System)),
        'subsystems':g.db.scalar(select(func.count()).select_from(Subsystem)),
        'archetypes':g.db.scalar(select(func.count()).select_from(Archetype)),
        'generic_total':g.db.scalar(select(func.count()).select_from(GenericSolution)),
        'generic_published':g.db.scalar(select(func.count()).select_from(GenericSolution).where(GenericSolution.status=='PUBLISHED')),
        'generic_draft':g.db.scalar(select(func.count()).select_from(GenericSolution).where(GenericSolution.status=='DRAFT')),
        'commercial_total':g.db.scalar(select(func.count()).select_from(CommercialSolution)),
        'commercial_public':g.db.scalar(select(func.count()).select_from(CommercialSolution).where(CommercialSolution.availability=='ACTIVE',CommercialSolution.published_revision_id.is_not(None))),
        'legacy_quarantined':g.db.scalar(select(func.count()).select_from(CommercialSolution).where(CommercialSolution.availability=='SUSPENDED')),
        'manufacturers':g.db.scalar(select(func.count()).select_from(Manufacturer)),
        'ifc_assets':g.db.scalar(select(func.count()).select_from(Asset).where(Asset.file_type=='IFC')),
        'pending_reviews':g.db.scalar(select(func.count()).select_from(Revision).where(Revision.status=='SUBMITTED')),
    }
    return data(counts)



@api.get('/admin/legacy/products')
@role('ADMIN')
def admin_legacy_products():
    # Retained for existing clients; use the compact inventory for the publication screen.
    query=select(CommercialSolution).where(CommercialSolution.availability=='SUSPENDED').order_by(CommercialSolution.code)
    items,meta=page_query(query)
    return data([serialize_product(p,True,include_extraction=False) for p in items],meta)



@api.get('/admin/legacy/inventory')
@role('ADMIN')
def legacy_inventory():
    """Small, server-paged publication rows; full records stay on detail endpoints."""
    kind=request.args.get('kind','commercial')
    state=request.args.get('status','pending')
    search=request.args.get('q','').strip()
    sort=request.args.get('sort','code')
    if kind not in ('commercial','generic') or state not in ('pending','published','all'):
        err('Filtro de inventario inválido','VALIDATION',422)
    if sort not in ('code','name','updated') or len(search)>120:
        err('Búsqueda u ordenación inválida','VALIDATION',422)
    if kind=='generic':
        query=select(GenericSolution).where(GenericSolution.technical_data.has_key('legacy_source'))
        if state=='pending':query=query.where(GenericSolution.status=='DRAFT')
        elif state=='published':query=query.where(GenericSolution.status=='PUBLISHED')
        if search:query=query.where(or_(GenericSolution.code.ilike('%'+search+'%'),GenericSolution.name_es.ilike('%'+search+'%')))
        order={'code':GenericSolution.code,'name':GenericSolution.name_es,'updated':GenericSolution.updated_at.desc()}[sort]
        items,meta=page_query(query.order_by(order,GenericSolution.id))
        ids=[x.id for x in items]
        classifications=dict(g.db.execute(select(Subsystem.id,Subsystem.code).where(Subsystem.id.in_([x.subsystem_id for x in items]))).all()) if items else {}
        assets={id:[] for id in ids}
        if ids:
            for generic_id,asset,link in g.db.execute(select(GenericAsset.generic_id,Asset,GenericAsset).join(Asset,Asset.id==GenericAsset.asset_id).where(GenericAsset.generic_id.in_(ids))):
                assets[generic_id].append((asset,link))
        rows=[{'id':str(x.id),'code':x.code,'name':x.name_es,'kind':kind,'manufacturer':None,
               'classification':classifications.get(x.subsystem_id,''),'status':x.status,'revision':None,
               'updated_at':x.updated_at.isoformat(),'ifc_status':next((a.processing_status for a,_ in assets[x.id] if a.file_type=='IFC'),'MISSING'),
               'has_bc3':any(a.file_type=='BC3' for a,_ in assets[x.id]),'has_epd':any(a.file_type=='EPD' for a,_ in assets[x.id]),
               'warnings':(['IFC válido requerido'] if not any(a.file_type=='IFC' and a.processing_status=='VALID' for a,_ in assets[x.id]) else [])+
                          (['Prestaciones técnicas requeridas'] if not (x.technical_data.get('properties') or x.technical_data.get('technical_performance')) else []),
               **ifc_counts(assets[x.id])} for x in items]
        return data(rows,meta)
    latest=(select(Revision.id).where(Revision.product_id==CommercialSolution.id)
            .order_by(Revision.number.desc()).limit(1).correlate(CommercialSolution).scalar_subquery())
    query=(select(CommercialSolution,Manufacturer,Revision)
           .join(Manufacturer,Manufacturer.id==CommercialSolution.manufacturer_id)
           .join(Revision,Revision.id==latest)
           .where(Revision.technical_data.has_key('legacy_source')))
    if state=='pending':query=query.where(CommercialSolution.availability=='SUSPENDED')
    elif state=='published':query=query.where(CommercialSolution.availability=='ACTIVE',CommercialSolution.published_revision_id.is_not(None))
    if search:query=query.where(or_(CommercialSolution.code.ilike('%'+search+'%'),Revision.name_es.ilike('%'+search+'%'),Manufacturer.name.ilike('%'+search+'%')))
    order={'code':CommercialSolution.code,'name':Revision.name_es,'updated':CommercialSolution.updated_at.desc()}[sort]
    # page_query selects ORM scalars only; page the joined rows explicitly.
    try:page=int(request.args.get('page',1));size=int(request.args.get('page_size',20))
    except ValueError:err('Paginación inválida','VALIDATION',422)
    if not 1<=page<=10000 or not 1<=size<=100:err('Paginación fuera de límites','VALIDATION',422)
    total=g.db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    items=list(g.db.execute(query.order_by(order,CommercialSolution.id).limit(size).offset((page-1)*size)))
    classifications=dict(g.db.execute(select(Subsystem.id,Subsystem.code).where(Subsystem.id.in_([p.subsystem_id for p,_,_ in items]))).all()) if items else {}
    revisions=[r.id for _,_,r in items]
    assets={id:[] for id in revisions}
    if revisions:
        for revision_id,asset,link in g.db.execute(select(RevisionAsset.revision_id,Asset,RevisionAsset).join(Asset,Asset.id==RevisionAsset.asset_id).where(RevisionAsset.revision_id.in_(revisions))):
            assets[revision_id].append((asset,link))
    rows=[{'id':str(p.id),'code':p.code,'name':r.name_es,'kind':kind,'manufacturer':m.name,
           'classification':classifications.get(p.subsystem_id,''),'status':p.availability,'revision':r.number,
           'updated_at':p.updated_at.isoformat(),'ifc_status':next((a.processing_status for a,_ in assets[r.id] if a.file_type=='IFC'),'MISSING'),
           'has_bc3':any(a.file_type=='BC3' for a,_ in assets[r.id]),'has_epd':any(a.file_type=='EPD' for a,_ in assets[r.id]),
           'warnings':['IFC válido requerido'] if not any(a.file_type=='IFC' and a.processing_status=='VALID' for a,_ in assets[r.id]) else [],
           **ifc_counts(assets[r.id])} for p,m,r in items]
    return data(rows,{'page':page,'page_size':size,'total':total})



@api.get('/admin/legacy/products/<id>')
@role('ADMIN')
def admin_legacy_product_detail(id):
    product=obj(CommercialSolution,id)
    source=g.db.scalar(select(Revision).where(Revision.product_id==product.id,Revision.technical_data.has_key('legacy_source')).limit(1))
    if not source:err('No es un producto legacy','NOT_FOUND',404)
    return data(serialize_product(product,True))



@api.post('/admin/catalogue/<kind>')
@role('ADMIN')
def admin_catalogue_create(kind):
    model=MODELS.get(kind)
    if not model:err('Entidad desconocida','NOT_FOUND',404)
    b=request.get_json(silent=True) or {}
    if not isinstance(b,dict):err('Se requiere un objeto JSON')
    if model is not GenericSlot:
        dto(CatalogueDTO)
    allowed={c.key for c in model.__table__.columns}-{'id','created_at','updated_at','status','archived'}
    fields_to_set={k:v for k,v in b.items() if k in allowed}
    for rel in ('system_id','subsystem_id','archetype_id','generic_solution_id'):
        if rel in fields_to_set:fields_to_set[rel]=pk(fields_to_set[rel])
    if model is GenericSolution:
        if 'archetype_id' not in fields_to_set:err('Arquetipo obligatorio','VALIDATION',422)
        a=obj(Archetype,fields_to_set['archetype_id']);fields_to_set['subsystem_id']=a.subsystem_id
        fields_to_set.setdefault('technical_data',{'schema_version':'1.0'});
        # New generic remains DRAFT until valid IFC is attached.
    if model is System and str(fields_to_set.get('code','')).upper()=='INS':
        err('El sistema de instalaciones está fuera del catálogo activo','OUT_OF_SCOPE',422)
    subsystem = g.db.get(Subsystem,fields_to_set['subsystem_id']) if 'subsystem_id' in fields_to_set else None
    system_id = subsystem.system_id if subsystem else fields_to_set.get('system_id')
    system = g.db.get(System,system_id) if system_id else None
    if (subsystem and subsystem.archived) or (system and (system.archived or system.code=='INS')):
        err('Clasificación fuera del catálogo activo','OUT_OF_SCOPE',422)
    if model is GenericSlot and not fields_to_set.get('generic_solution_id'):err('Solución genérica obligatoria')
    try:x=model(**fields_to_set)
    except (TypeError,KeyError) as e:err('Campos insuficientes o inválidos','VALIDATION',422)
    g.db.add(x);g.db.flush();audit('CREATE','catalogue-'+kind,x.id)
    return data(fields(x,['id']+([ 'status'] if model is GenericSolution else [])),status=201)



@api.patch('/admin/catalogue/<kind>/<id>')
@role('ADMIN')
def admin_catalogue_update(kind,id):
    model=MODELS.get(kind)
    if not model:err('Entidad desconocida','NOT_FOUND',404)
    x=obj(model,id,True);body=request.get_json(silent=True) or {}
    if not isinstance(body,dict):err('Se requiere un objeto JSON')
    for field in ('technical_data','environmental_data','economic_data','properties'):
        if field in body and not isinstance(body[field],dict):err(f'{field} debe ser un objeto')
    if 'composition' in body and not isinstance(body['composition'],list):err('Composición debe ser una lista')
    if isinstance(x,GenericSolution) and x.status!='DRAFT':err('Edita una referencia en borrador','IMMUTABLE',409)
    for name in ('name_es','technical_data','environmental_data','economic_data','composition','properties','required','slot_order','description'):
        if name in body and hasattr(x,name):setattr(x,name,body[name])
    audit('UPDATE','catalogue-'+kind,x.id)
    return data({'updated':str(x.id)})



@api.post('/admin/catalogue/<kind>/<id>/<action>')
@role('ADMIN')
def admin_archive(kind,id,action):
    model=MODELS.get(kind)
    if not model or action not in ('archive','restore','publish'):err('Operación inválida','NOT_FOUND',404)
    x=obj(model,id,True)
    if action in ('restore','publish'):
        subsystem = x if isinstance(x,Subsystem) else g.db.get(Subsystem,x.subsystem_id) if hasattr(x,'subsystem_id') else None
        system = x if isinstance(x,System) else g.db.get(System,subsystem.system_id) if subsystem else None
        if system and system.code=='INS':
            err('El sistema de instalaciones está fuera del catálogo activo','OUT_OF_SCOPE',422)
    if action=='publish':
        if model is not GenericSolution:err('Solo soluciones genéricas se publican')
        links=list(g.db.execute(select(Asset,GenericAsset).join(GenericAsset,Asset.id==GenericAsset.asset_id).where(GenericAsset.generic_id==x.id)))
        if not any(a.file_type=='IFC' and a.processing_status=='VALID' for a,link in links):err('Se requiere IFC válido','SUBMISSION_INVALID',422)
        if not x.technical_data.get('properties') and not x.technical_data.get('technical_performance'):
            err('Prestaciones técnicas requeridas','SUBMISSION_INVALID',422)
        x.status='PUBLISHED'
    elif hasattr(x,'archived'):x.archived=action=='archive'
    elif model is GenericSolution:x.status='ARCHIVED' if action=='archive' else 'DRAFT'
    else:err('Operación no soportada')
    audit(action.upper(),'catalogue-'+kind,x.id)
    return data({'id':str(x.id),'action':action})



@api.get('/admin/audit-logs')
@role('ADMIN')
def audit_list():
    xs,meta=page_query(select(AuditLog).order_by(AuditLog.at.desc()))
    return data([fields(x,['id','at','actor_id','action','entity','entity_id','detail']) for x in xs],meta)



@api.get('/admin/notifications')
@role('ADMIN')
def admin_notifs():
    xs,meta=page_query(select(Notification).where(Notification.user_id==get_user().id).order_by(Notification.created_at.desc()))
    return data([fields(x,['id','event','message','read_at']) for x in xs],meta)

