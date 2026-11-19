"""Manufacturer service for the versioned Flask API."""

from .http_core import (
    Asset,
    DataTemplate,
    Extraction,
    GenericSolution,
    Invitation,
    RevisionAsset,
    RevisionGeneric,
    User,
    audit,
    check_template,
    data,
    discrepancies,
    err,
    g,
    hash_token,
    now,
    obj,
    request,
    secrets,
    select,
    timedelta,
)

def issue_invitation(manufacturer_id,user):
    from email_validator import validate_email, EmailNotValidError
    body=request.get_json(silent=True)
    if not isinstance(body,dict):err('Se requiere un objeto JSON')
    try:email=validate_email(body.get('email',''),check_deliverability=False).normalized.lower()
    except (EmailNotValidError,TypeError):err('Correo inválido','VALIDATION',422)
    if g.db.scalar(select(User.id).where(User.email==email)):err('Usuario existente','CONFLICT',409)
    token=secrets.token_urlsafe(42)
    inv=Invitation(email=email,manufacturer_id=manufacturer_id,token_hash=hash_token(token),
                   expires_at=now()+timedelta(hours=48),created_by=user.id)
    g.db.add(inv)
    g.db.flush()
    audit('INVITE','manufacturer',manufacturer_id,{'email':email})
    return data({'invitation_token':token,'expires_at':inv.expires_at.isoformat()},status=201)

def set_generics(rev,ids,subsystem_id):
    if len(set(ids))!=len(ids):err('Referencias duplicadas','VALIDATION',422)
    inherited=set(g.db.scalars(select(RevisionGeneric.generic_id).where(RevisionGeneric.revision_id==rev.id)))
    generics=[obj(GenericSolution,i) for i in ids]
    if any(x.subsystem_id!=subsystem_id or (x.status!='PUBLISHED' and x.id not in inherited) for x in generics):
        err('Genérica incompatible o no publicada','INCOMPATIBLE',422)
    g.db.query(RevisionGeneric).filter(RevisionGeneric.revision_id==rev.id).delete(synchronize_session=False)
    for x in generics:g.db.add(RevisionGeneric(revision_id=rev.id,generic_id=x.id))

def validate_submission(r,p):
    errs=[]
    t=g.db.scalar(select(DataTemplate).where(DataTemplate.subsystem_id==p.subsystem_id,DataTemplate.version==r.template_version))
    if not t:errs.append('El subsistema requiere una plantilla técnica versionada')
    else:errs+=check_template(t,r.technical_data.get('properties',{}))
    assets=list(g.db.execute(select(Asset,RevisionAsset).join(RevisionAsset,Asset.id==RevisionAsset.asset_id).where(RevisionAsset.revision_id==r.id)))
    if not any(a.file_type=='IFC' and a.processing_status=='VALID' for a,_ in assets):errs.append('Se requiere un IFC válido')
    for a,_ in assets:
        if a.processing_status!='VALID':errs.append(f'Archivo inválido: {a.original_name}')
    if t:
        ifc_data={}
        for a,_ in assets:
            if a.file_type=='IFC':
                ex=g.db.scalar(select(Extraction).where(Extraction.asset_id==a.id).order_by(Extraction.created_at.desc()))
                if ex:ifc_data=ex.normalized;break
        r.discrepancies=discrepancies(t,r.technical_data.get('properties',{}),ifc_data)
        if r.discrepancies:errs.append('Existen discrepancias IFC pendientes')
    return errs
