"""Versioned HTTP endpoints for manufacturer."""
from ..api_support import (
    ApiError,
    CommercialSolution,
    ComponentDocumentLink,
    DataTemplate,
    Manufacturer,
    Notification,
    ProductDTO,
    Revision,
    RevisionAsset,
    RevisionDTO,
    RevisionGeneric,
    RevisionOrigin,
    Subsystem,
    User,
    api,
    audit,
    data,
    dto,
    err,
    fields,
    g,
    get_user,
    issue_invitation,
    notify,
    now,
    obj,
    owner,
    page_query,
    pk,
    request,
    revision_owned,
    role,
    select,
    serialize_product,
    serialize_revision,
    set_generics,
    validate_submission,
)


@api.get('/manufacturer/profile')
@role('MANUFACTURER')
def profile():
    m=obj(Manufacturer,get_user().manufacturer_id)
    return data(fields(m,['id','code','name','description','website','public_email','contact_public','status']))



@api.patch('/manufacturer/profile')
@role('MANUFACTURER')
def profile_update():
    m=obj(Manufacturer,get_user().manufacturer_id)
    body=request.get_json(silent=True) or {}
    for k in ('name','description','website','public_email','contact_public'):
        if k in body:
            if k=='contact_public' and not isinstance(body[k],bool):err('contact_public debe ser booleano')
            if k in ('website','public_email') and body[k] and (len(str(body[k]))>512 or (k=='website' and not str(body[k]).startswith('https://'))):err('Contacto inválido')
            setattr(m,k,body[k])
    audit('UPDATE_PROFILE','manufacturer',m.id)
    return data(fields(m,['id','name','description','website','public_email','contact_public']))



@api.post('/manufacturer/invitations')
@role('MANUFACTURER')
def invitation_create():
    user=get_user()
    return issue_invitation(user.manufacturer_id,user)



@api.get('/manufacturer/products')
@role('MANUFACTURER')
def own_products():
    q=select(CommercialSolution).where(CommercialSolution.manufacturer_id==get_user().manufacturer_id).order_by(CommercialSolution.created_at.desc())
    xs,meta=page_query(q);return data([serialize_product(x,True) for x in xs],meta)



@api.post('/manufacturer/products')
@role('MANUFACTURER')
def own_create():
    b=dto(ProductDTO);s=obj(Subsystem,b.subsystem_id)
    if s.archived:err('Subsistema archivado','VALIDATION',422)
    if g.db.scalar(select(CommercialSolution.id).where(CommercialSolution.code==b.code)):err('Código duplicado','CONFLICT',409)
    u=get_user();p=CommercialSolution(manufacturer_id=u.manufacturer_id,subsystem_id=s.id,code=b.code)
    g.db.add(p);g.db.flush()
    t=g.db.scalar(select(DataTemplate).where(DataTemplate.subsystem_id==s.id).order_by(DataTemplate.version.desc()))
    r=Revision(product_id=p.id,number=1,created_by=u.id,name_es=b.name_es,commercial_reference=b.commercial_reference,
     description=b.description,functional_unit=b.functional_unit,template_version=t.version if t else 1,
     technical_data={'schema_version':'1.0','properties':b.technical_data.get('properties',{})})
    g.db.add(r);g.db.flush();set_generics(r,b.generic_solution_ids,p.subsystem_id)
    audit('CREATE','product',p.id)
    return data(serialize_product(p,True),status=201)



@api.get('/manufacturer/products/<id>')
@role('MANUFACTURER')
def own_detail(id):
    p=obj(CommercialSolution,id);owner(p);return data(serialize_product(p,True))



@api.patch('/manufacturer/products/<id>')
@role('MANUFACTURER')
def own_availability(id):
    p=obj(CommercialSolution,id,True);owner(p)
    state=(request.get_json(silent=True) or {}).get('availability')
    if state not in ('ACTIVE','SUSPENDED','ARCHIVED'):err('Estado inválido','VALIDATION',422)
    p.availability=state;audit('AVAILABILITY','product',p.id,{'state':state})
    return data(serialize_product(p,True))



@api.post('/manufacturer/products/<id>/revisions')
@role('MANUFACTURER')
def new_revision(id):
    p=obj(CommercialSolution,id,True);owner(p)
    rr=list(g.db.scalars(select(Revision).where(Revision.product_id==p.id).order_by(Revision.number.desc())))
    if not rr or rr[0].status not in ('APPROVED','REJECTED'):err('Existe una revisión activa','CONFLICT',409)
    payload=request.get_json(silent=True)
    if payload is None:payload={}
    if not isinstance(payload,dict):err('Se requiere un objeto JSON')
    source_id=payload.get('source_revision_id')
    if source_id:
        requested=pk(source_id)
        source=next((row for row in rr if row.id==requested and row.status in ('APPROVED','REJECTED')),None)
        if not source:err('Revisión de origen no disponible','NOT_FOUND',404)
    else:
        source=rr[0] if rr[0].status=='REJECTED' else g.db.get(Revision,p.published_revision_id)
        if not source:err('No existe versión de origen','CONFLICT',409)
    r=Revision(product_id=p.id,number=rr[0].number+1,created_by=get_user().id,
      name_es=source.name_es,description=source.description,commercial_reference=source.commercial_reference,
      functional_unit=source.functional_unit,template_version=source.template_version,
      technical_data=dict(source.technical_data),economic_data=dict(source.economic_data),
      environmental_data=dict(source.environmental_data))
    g.db.add(r);g.db.flush()
    g.db.add(RevisionOrigin(revision_id=r.id,parent_id=source.id,
                            message='Restauración como borrador' if source_id else 'Nueva revisión'))
    # Frozen historic references are preserved even when their generic was archived.
    for generic_id in g.db.scalars(select(RevisionGeneric.generic_id).where(RevisionGeneric.revision_id==source.id)):
        g.db.add(RevisionGeneric(revision_id=r.id,generic_id=generic_id))
    for link in g.db.scalars(select(RevisionAsset).where(RevisionAsset.revision_id==source.id)):
        g.db.add(RevisionAsset(revision_id=r.id,asset_id=link.asset_id,
                              public_view_allowed=link.public_view_allowed and not source_id,
                              public_download_allowed=link.public_download_allowed and not source_id))
    g.db.flush()
    for link in g.db.scalars(select(ComponentDocumentLink).where(ComponentDocumentLink.revision_id==source.id)):
        g.db.add(ComponentDocumentLink(revision_id=r.id,ifc_asset_id=link.ifc_asset_id,
            ifc_global_id=link.ifc_global_id,target_asset_id=link.target_asset_id,
            concept_code=link.concept_code,material=link.material,unit=link.unit,
            evidence=link.evidence,author_id=link.author_id,created_at=link.created_at))
    audit('RESTORE_REVISION' if source_id else 'NEW_REVISION','revision',r.id,{'source_revision_id':str(source.id)})
    return data(serialize_revision(r,True),status=201)



@api.get('/manufacturer/revisions/<id>')
@role('MANUFACTURER')
def own_revision(id):
    r,p=revision_owned(id);return data(serialize_revision(r,True))



@api.patch('/manufacturer/revisions/<id>')
@role('MANUFACTURER')
def update_revision(id):
    r,p=revision_owned(id,True)
    if r.status!='DRAFT':err('La revisión no se puede editar','IMMUTABLE',409)
    b=dto(RevisionDTO)
    for name in ('name_es','description','commercial_reference','functional_unit'):setattr(r,name,getattr(b,name))
    r.technical_data={**r.technical_data,'properties':b.technical_data.get('properties',{})}
    if b.composition is not None:
        r.technical_data={**r.technical_data,'composition':[layer.model_dump() for layer in b.composition]}
    if b.economic_values is not None:
        r.economic_data={**r.economic_data,'declared':[value.model_dump() for value in b.economic_values]}
    if b.environmental_values is not None:
        r.environmental_data={**r.environmental_data,'declared':[value.model_dump() for value in b.environmental_values]}
    set_generics(r,b.generic_solution_ids,p.subsystem_id)
    audit('UPDATE_DRAFT','revision',r.id)
    return data(serialize_revision(r,True))



@api.post('/manufacturer/revisions/<id>/submit')
@role('MANUFACTURER')
def submit_revision(id):
    r,p=revision_owned(id,True)
    if r.status!='DRAFT':err('Solo borradores pueden enviarse','IMMUTABLE',409)
    failures=validate_submission(r,p)
    if failures:raise ApiError('SUBMISSION_INVALID','No se puede enviar la revisión',422,failures)
    r.status='SUBMITTED';r.submitted_at=now();audit('SUBMIT','revision',r.id)
    notify(g.db.scalars(select(User).where(User.role=='ADMIN',User.active==True)),'SUBMITTED',f'Revisión enviada: {r.name_es}')
    return data(serialize_revision(r,True))



@api.get('/manufacturer/notifications')
@role('MANUFACTURER')
def notifications():
    q=select(Notification).where(Notification.user_id==get_user().id).order_by(Notification.created_at.desc())
    xs,meta=page_query(q)
    return data([fields(n,['id','event','message','read_at']) for n in xs],meta)



@api.patch('/notifications/<id>/read')
def mark_read(id):
    n=obj(Notification,id)
    if n.user_id!=get_user().id:err('No encontrado','NOT_FOUND',404)
    n.read_at=now();return data({'read':True})

