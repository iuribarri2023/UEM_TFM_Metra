"""Asset service for the versioned Flask API."""
from .asset_staging import promote_if_absent

from .http_core import (
    Asset,
    CommercialSolution,
    DocumentJob,
    Extraction,
    GenericAsset,
    GenericSolution,
    ParseFailure,
    Path,
    Response,
    Revision,
    RevisionAsset,
    api,
    audit,
    current_app,
    data,
    err,
    export_bc3,
    fields,
    g,
    get_user,
    hashlib,
    obj,
    pk,
    request,
    secure_filename,
    select,
    send_file,
    thumbnail_path,
    uuid4,
)

def serialize_asset(asset,link=None,include_extraction=True,*,catalogue=False,product_id=None):
    x=fields(asset,['id','file_type','original_name','sha256','size','processing_status'])
    x.update(format=asset.file_type, version=None, integrity_status='NOT_CHECKED',
             extraction_status=asset.processing_status, provenance='UNSPECIFIED', derivatives=[])
    if link:
        x.update(public_download_allowed=link.public_download_allowed,public_view_allowed=link.public_view_allowed,
                 association={'generic_id': str(link.generic_id) if isinstance(link,GenericAsset) else None,
                              'revision_id': str(link.revision_id) if isinstance(link,RevisionAsset) else None,
                              'product_id': str(product_id) if product_id else None})
    if include_extraction and link and (link.public_view_allowed or link.public_download_allowed):
        x['extraction_summary_href'] = f'/api/v1/documents/{asset.id}/summary'
    if link and link.public_view_allowed and asset.file_type=='IFC' and asset.processing_status=='VALID':
        root=Path(current_app.config['ASSET_DIR']).resolve()
        try:
            path=thumbnail_path(root,asset.sha256).resolve()
            x['thumbnail_available']=path.parent==root/'.ifc-thumbnails' and path.is_file()
            if x['thumbnail_available']:
                x['derivatives'].append({'type':'IFC_THUMBNAIL','href':f'/api/v1/documents/{asset.id}/thumbnail'})
        except (ValueError,OSError):
            x['thumbnail_available']=False
    return x

def bim_status(linked,verify=True):
    ifcs=[(a,link) for a,link in linked if a.file_type=='IFC']
    if not ifcs:return 'NO_IFC'
    authorized=[a for a,link in ifcs if a.processing_status=='VALID' and link.public_view_allowed]
    states = [ifc_file_state(a, verify=verify) for a in authorized]
    if 'MATCH' in states or 'PRESENT' in states:return 'VIEWABLE'
    if 'CORRUPT' in states:return 'CORRUPT'
    if authorized:return 'MISSING'
    if any(a.processing_status=='INVALID' for a,_ in ifcs):return 'INVALID'
    if any(a.processing_status in ('PENDING','PROCESSING') for a,_ in ifcs):return 'PROCESSING'
    return 'PRIVATE'

def ifc_file_state(asset,verify=True):
    root=Path(current_app.config['ASSET_DIR']).resolve();path=(root/asset.storage_key).resolve()
    if path.parent!=root or not path.is_file():return 'MISSING'
    if not verify:return 'PRESENT'
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return 'MATCH' if digest.hexdigest()==asset.sha256 else 'CORRUPT'

def ifc_counts(linked):
    ifcs=[(a,link) for a,link in linked if a.file_type=='IFC']
    root=Path(current_app.config['ASSET_DIR']).resolve()
    return {'ifc_count':len(ifcs),'ifc_valid':sum(a.processing_status=='VALID' for a,_ in ifcs),
            'ifc_invalid':sum(a.processing_status=='INVALID' for a,_ in ifcs),
            'ifc_missing_file':sum((root/a.storage_key).resolve().parent!=root or not (root/a.storage_key).is_file() for a,_ in ifcs),
            'ifc_private':sum(not link.public_view_allowed for _,link in ifcs),
            'ifc_view_allowed':sum(link.public_view_allowed for _,link in ifcs),
            'ifc_download_allowed':sum(link.public_download_allowed for _,link in ifcs)}

def create_asset(revision_id=None,generic_id=None,manufacturer_id=None,expected_type=None,return_asset=False):
    f=request.files.get('file')
    if not f or not f.filename:err('Archivo requerido')
    extension=Path(f.filename).suffix.lower()
    type_map={'.ifc':'IFC','.bc3':'BC3','.zip':'BC3','.xml':'EPD'}
    typ=type_map.get(extension)
    if not typ or (expected_type and typ!=expected_type):err('Tipo de archivo no admitido','UNSUPPORTED_MEDIA',415)
    content=f.read(current_app.config['MAX_CONTENT_LENGTH']+1)
    if len(content)>current_app.config['MAX_CONTENT_LENGTH']:err('Archivo demasiado grande','TOO_LARGE',413)
    if not content:err('Archivo vacío')
    status='PENDING'
    key=uuid4().hex+extension
    root=Path(current_app.config['ASSET_DIR']).resolve()
    path=root/key
    # Stage, fsync, verify and atomically promote before publishing the DB row.
    # The request transaction compensates a later DB failure via g.created_files.
    content_sha=hashlib.sha256(content).hexdigest()
    if not promote_if_absent(root,key,content,sha256=content_sha):
        err('Identificador de activo ya existente','CONFLICT',409)
    g.created_files.append(path)
    a=Asset(manufacturer_id=manufacturer_id,original_name=secure_filename(f.filename)[:255],storage_key=key,file_type=typ,
      sha256=content_sha,size=len(content),processing_status=status)
    g.db.add(a);g.db.flush()
    g.db.add(DocumentJob(asset_id=a.id,state='PENDING'))
    if revision_id:g.db.add(RevisionAsset(revision_id=revision_id,asset_id=a.id))
    if generic_id:g.db.add(GenericAsset(generic_id=generic_id,asset_id=a.id))
    audit('UPLOAD','asset',a.id,{'type':typ,'status':status})
    if return_asset:return a
    return data(serialize_asset(a),status=202)

def authorized_asset(id,mode):
    a=obj(Asset,id)
    user=get_user(False)
    allowed=bool(user and (user.role=='ADMIN' or a.manufacturer_id and a.manufacturer_id==user.manufacturer_id))
    if not allowed:
        attr=RevisionAsset.public_view_allowed if mode=='view' else RevisionAsset.public_download_allowed
        published=g.db.scalar(select(RevisionAsset.asset_id).join(Revision,Revision.id==RevisionAsset.revision_id)
          .join(CommercialSolution,CommercialSolution.published_revision_id==Revision.id)
          .where(RevisionAsset.asset_id==a.id,attr==True,Revision.status=='APPROVED',CommercialSolution.availability=='ACTIVE'))
        generic_attr=GenericAsset.public_view_allowed if mode=='view' else GenericAsset.public_download_allowed
        gen=g.db.scalar(select(GenericAsset.asset_id).join(GenericSolution,GenericSolution.id==GenericAsset.generic_id)
          .where(GenericAsset.asset_id==a.id,generic_attr==True,GenericSolution.status=='PUBLISHED'))
        allowed=bool(published or gen)
    if not allowed:err('Archivo no disponible','NOT_FOUND',404)
    return a

@api.get('/assets/<id>/<mode>')
def asset_access(id,mode):
    if mode not in ('view','download','regenerate'):err('No encontrado','NOT_FOUND',404)
    a=authorized_asset(id,mode)
    if mode=='view':
        if a.file_type!='IFC':err('Solo IFC se visualiza','UNSUPPORTED',422)
        if a.processing_status!='VALID':err('IFC pendiente o inválido','VALIDATION',422)
    if mode=='regenerate':
        if a.file_type!='BC3':err('Solo se regenera BC3','UNSUPPORTED',422)
        extraction=g.db.scalar(select(Extraction).where(Extraction.asset_id==a.id).order_by(Extraction.created_at.desc()))
        if not extraction or not extraction.is_valid:err('BC3 sin extracción válida','VALIDATION',422)
        try:content=export_bc3(extraction.normalized)
        except ParseFailure as exc:err(str(exc),'VALIDATION',422)
        return Response(content,mimetype='application/octet-stream',
                        headers={'Content-Disposition':f'attachment; filename="{Path(a.original_name).stem}.bc3"'})
    root=Path(current_app.config['ASSET_DIR']).resolve();path=(root/a.storage_key).resolve()
    if path.parent!=root or not path.is_file():err('Archivo no encontrado','NOT_FOUND',404)
    if a.file_type=='IFC':
        digest=hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
        if digest.hexdigest()!=a.sha256:err('El original no coincide con su SHA-256','INTEGRITY',422)
    response=send_file(path,mimetype={'IFC':'application/x-step','BC3':'application/octet-stream','EPD':'application/xml'}[a.file_type],
     as_attachment=(mode=='download'),download_name=a.original_name,conditional=True)
    if mode=='view':response.headers['X-METRA-View-Format']='IFC_ORIGINAL'
    return response

def document_policy(link, asset, scope, target, policy):
    if not isinstance(policy,dict):err('Política documental inválida')
    view=policy.get('public_view_allowed')
    download=policy.get('public_download_allowed')
    if type(view) is not bool or type(download) is not bool:
        err('Indica ambos permisos como valores booleanos')
    if view and not link.public_view_allowed and (asset.file_type!='IFC' or asset.processing_status!='VALID'):
        err('La visualización requiere un IFC válido','VALIDATION',422)
    if ((view and not link.public_view_allowed) or
            (download and not link.public_download_allowed)) and ifc_file_state(asset)!='MATCH':
        err('El IFC original debe estar presente y coincidir con su SHA-256','INTEGRITY',422)
    before=[link.public_view_allowed,link.public_download_allowed]
    after=[view,download]
    if before==after:return
    evidence=policy.get('rights_evidence','')
    if any(new and not old for old,new in zip(before,after)):
        if not isinstance(evidence,str) or not 10<=len(evidence.strip())<=2000:
            err('Registra la evidencia de autorización documental','VALIDATION',422)
    link.public_view_allowed,link.public_download_allowed=after
    audit('DOCUMENT_POLICY',scope,target,{'asset_id':str(asset.id),'before':before,
          'after':after,'evidence':evidence if isinstance(evidence,str) else ''})

def revision_policies(revision, policies):
    if not isinstance(policies,dict) or len(policies)>100:
        err('Políticas documentales inválidas')
    for id,policy in policies.items():
        asset_id=pk(id)
        link=g.db.get(RevisionAsset,{'revision_id':revision.id,'asset_id':asset_id})
        if link is None:err('El archivo no pertenece a la revisión','NOT_FOUND',404)
        document_policy(link,obj(Asset,asset_id),'revision',revision.id,policy)

def ifc_page():
    try:page=int(request.args.get('page',1));size=int(request.args.get('page_size',20))
    except ValueError:err('Paginación inválida','VALIDATION',422)
    if not 1<=page<=10000 or not 1<=size<=100:err('Paginación fuera de límites','VALIDATION',422)
    return page,size

def ifc_row(asset,link):
    return {'asset_id':str(asset.id),'original_name':asset.original_name,'processing_status':asset.processing_status,
            'sha256':asset.sha256,'integrity_status':ifc_file_state(asset),
            'updated_at':asset.updated_at.isoformat(),
            'public_view_allowed':link.public_view_allowed,
            'public_download_allowed':link.public_download_allowed}
