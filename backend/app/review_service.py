"""Review service for the versioned Flask API."""

from .asset_service import (
    document_policy,
    revision_policies,
)

from .http_core import (
    ApiError,
    Asset,
    CommercialSolution,
    GenericAsset,
    GenericSolution,
    ReviewDecision,
    Revision,
    RevisionAsset,
    RevisionGeneric,
    RevisionOrigin,
    User,
    audit,
    err,
    g,
    get_user,
    notify,
    now,
    obj,
    pk,
    request,
    select,
)

from .manufacturer_service import (
    validate_submission,
)

def decision(id,approved,reason,corrections=False,policies=None):
    r=obj(Revision,id,True);p=obj(CommercialSolution,r.product_id,True)
    if r.status!='SUBMITTED':err('Revisión ya decidida','CONFLICT',409)
    if not approved and len(reason)<5:err('Motivo obligatorio (mínimo 5 caracteres)','VALIDATION',422)
    if approved:
        problems=validate_submission(r,p)
        if problems:raise ApiError('SUBMISSION_INVALID','Validación fallida',422,problems)
        if policies is not None:revision_policies(r,policies)
        r.status='APPROVED';p.published_revision_id=r.id
    else:r.status='REJECTED';r.rejection_reason=reason
    r.decided_at=now()
    state='CORRECTIONS_REQUESTED' if corrections else r.status
    u=get_user();g.db.add(ReviewDecision(revision_id=r.id,admin_id=u.id,decision=state,reason=reason or None))
    audit('APPROVE' if approved else state,'revision',r.id,{'reason':reason})
    notify(g.db.scalars(select(User).where(User.manufacturer_id==p.manufacturer_id,User.active==True)),
      r.status,('Revisión aprobada: ' if approved else 'Revisión rechazada: ')+r.name_es+(' — '+reason if reason else ''))
    return p

def decision_reason():
    body=request.get_json(silent=True) or {}
    if not isinstance(body,dict):err('Se requiere un objeto JSON')
    reason=body.get('reason','')
    if not isinstance(reason,str) or len(reason)>2000:err('Motivo inválido')
    return reason.strip()

def publish_legacy_generic(item, evidence, policies=None):
    record = obj(GenericSolution, item, True)
    if record.status == 'PUBLISHED' and record.technical_data.get('legacy_source'):
        return
    if record.status != 'DRAFT' or not record.technical_data.get('legacy_source'):
        err('Se requiere una referencia histórica en borrador','CONFLICT',409)
    valid_ifc=g.db.scalar(select(Asset.id).join(GenericAsset,GenericAsset.asset_id==Asset.id).where(
        GenericAsset.generic_id==record.id,Asset.file_type=='IFC',Asset.processing_status=='VALID').limit(1))
    if not valid_ifc:err('Se requiere IFC válido','SUBMISSION_INVALID',422)
    if not record.technical_data.get('properties') and not record.technical_data.get('technical_performance'):
        err('Prestaciones técnicas requeridas','SUBMISSION_INVALID',422)
    if policies is not None:
        if not isinstance(policies,dict) or len(policies)>100:err('Políticas documentales inválidas')
        for id,policy in policies.items():
            asset_id=pk(id)
            link=g.db.get(GenericAsset,{'generic_id':record.id,'asset_id':asset_id})
            if link is None:err('El archivo no pertenece a la solución genérica','NOT_FOUND',404)
            document_policy(link,obj(Asset,asset_id),'generic',record.id,policy)
    record.status = 'PUBLISHED'
    audit('PUBLISH_LEGACY_METADATA','generic',record.id,{'evidence':evidence})

def publish_legacy_product(item, evidence, policies=None):
    product = obj(CommercialSolution, item, True)
    if product.availability == 'ACTIVE' and product.published_revision_id:
        published = g.db.get(Revision, product.published_revision_id)
        if published and published.status == 'APPROVED' and published.technical_data.get('legacy_source'):
            return
    source = g.db.scalar(select(Revision).where(Revision.product_id==product.id)
                         .order_by(Revision.number.desc()).limit(1))
    if (product.availability != 'SUSPENDED' or product.published_revision_id or not source
            or source.status != 'REJECTED' or not source.technical_data.get('legacy_source')):
        err('Se requiere un producto histórico suspendido sin revisión pública','CONFLICT',409)
    valid_ifc=g.db.scalar(select(Asset.id).join(RevisionAsset,RevisionAsset.asset_id==Asset.id).where(
        RevisionAsset.revision_id==source.id,Asset.file_type=='IFC',Asset.processing_status=='VALID').limit(1))
    if not valid_ifc:err('Se requiere IFC válido','SUBMISSION_INVALID',422)
    author = get_user()
    revision = Revision(product_id=product.id, number=source.number+1, created_by=author.id,
                        status='APPROVED', decided_at=now(), name_es=source.name_es,
                        description=source.description, commercial_reference=source.commercial_reference,
                        functional_unit=source.functional_unit, template_version=source.template_version,
                        technical_data=dict(source.technical_data),
                        economic_data=dict(source.economic_data),
                        environmental_data=dict(source.environmental_data))
    g.db.add(revision)
    g.db.flush()
    for generic_id in g.db.scalars(select(RevisionGeneric.generic_id).where(RevisionGeneric.revision_id==source.id)):
        g.db.add(RevisionGeneric(revision_id=revision.id, generic_id=generic_id))
    for link in g.db.scalars(select(RevisionAsset).where(RevisionAsset.revision_id==source.id)):
        g.db.add(RevisionAsset(revision_id=revision.id, asset_id=link.asset_id,
                              public_view_allowed=link.public_view_allowed,
                              public_download_allowed=link.public_download_allowed))
    if policies is not None:
        g.db.flush()
        revision_policies(revision,policies)
    g.db.add(RevisionOrigin(revision_id=revision.id,parent_id=source.id,message='Publicación editorial METRA-DEMO'))
    product.published_revision_id = revision.id
    product.availability = 'ACTIVE'
    g.db.add(ReviewDecision(revision_id=revision.id, admin_id=author.id,
                            decision='APPROVED', reason=evidence))
    audit('PUBLISH_LEGACY_METADATA','revision',revision.id,
          {'evidence':evidence, 'source_revision_id':str(source.id)})
