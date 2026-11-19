"""Live PostgreSQL integration: export TEST_DATABASE_URL to enable. Not SQLite substitutes."""
import os
import pytest
pytestmark=pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'),reason='Requires disposable test PostgreSQL')

@pytest.fixture
def ctx():
    from app import create_app
    from app.models import Base,User,now
    from app.security import ph
    from sqlalchemy.orm import Session
    app=create_app({'DATABASE_URL':os.getenv('TEST_DATABASE_URL','postgresql+psycopg://invalid'),
                    'JWT_SECRET':'a'*48,'COOKIE_SECURE':False,'TESTING':True})
    with app.app_context():
        Base.metadata.drop_all(app.extensions['engine']);Base.metadata.create_all(app.extensions['engine'])
        with Session(app.extensions['engine']) as s:
            s.add(User(email='admin@example.com',password_hash=ph.hash('AdminPassword_1234'),role='ADMIN'));s.commit()
    yield app
    with app.app_context():Base.metadata.drop_all(app.extensions['engine'])
    app.extensions['engine'].dispose()

def login(client,email,password):
    r=client.post('/api/v1/auth/login',json={'email':email,'password':password})
    assert r.status_code==200,r.json
    return {'Authorization':'Bearer '+r.json['data']['access_token']}

def register(client,email,company):
    r=client.post('/api/v1/auth/register',json={'email':email,'password':'GoodPassword_1234','manufacturer_name':company})
    assert r.status_code==201,r.json
    return {'Authorization':'Bearer '+r.json['data']['access_token']}

def test_register_and_cross_organization_idor(ctx):
    a=ctx.test_client();b=ctx.test_client()
    auth_a=register(a,'a@example.com','Company A');auth_b=register(b,'b@example.com','Company B')
    # Seed a known taxonomy directly, but use HTTP for authorisation behaviour.
    from app.models import System,Subsystem
    from sqlalchemy.orm import Session
    with Session(ctx.extensions['engine']) as s:
        sys=System(code='SYS',name_es='System');s.add(sys);s.flush()
        sub=Subsystem(code='SYS.WAL',name_es='Walls',system_id=sys.id);s.add(sub);s.commit();sid=str(sub.id)
    create=a.post('/api/v1/manufacturer/products',headers=auth_a,json={'code':'PROD1','subsystem_id':sid,'name_es':'Demo','technical_data':{},'generic_solution_ids':[]})
    assert create.status_code==201,create.json
    pid=create.json['data']['id'];rid=create.json['data']['revisions'][0]['id']
    assert b.get('/api/v1/manufacturer/products/'+pid,headers=auth_b).status_code==404
    assert b.get('/api/v1/manufacturer/revisions/'+rid,headers=auth_b).status_code==404
    assert b.patch('/api/v1/manufacturer/revisions/'+rid,headers=auth_b,json={}).status_code==404
    assert a.get('/api/v1/products/'+pid).status_code==404
    invalid=a.post('/api/v1/manufacturer/revisions/'+rid+'/submit',headers=auth_a,json={})
    assert invalid.status_code==422 and 'IFC' in str(invalid.json)

def test_login_refresh_csrf_and_rotation(ctx):
    c=ctx.test_client();register(c,'test@example.com','Org')
    assert c.post('/api/v1/auth/refresh',json={}).status_code==403
    csrf=c.get_cookie('csrf').value
    assert c.post('/api/v1/auth/refresh',json={},headers={'X-CSRF-Token':csrf}).status_code==200
    csrf=c.get_cookie('csrf').value
    assert c.post('/api/v1/auth/logout',json={},headers={'X-CSRF-Token':csrf}).status_code==200
    assert c.get('/api/v1/auth/me').status_code==401

def test_only_admin_can_review(ctx):
    a=ctx.test_client();b=ctx.test_client()
    auth_a=register(a,'a@example.com','Company A');login(b,'admin@example.com','AdminPassword_1234')
    assert a.get('/api/v1/admin/reviews',headers=auth_a).status_code==403
    assert a.get('/api/v1/admin/audit-logs',headers=auth_a).status_code==403


def test_admin_legacy_batch_keeps_history_and_requires_ifc_permission(ctx,tmp_path):
    from uuid import uuid4
    from pathlib import Path
    from hashlib import sha256
    from sqlalchemy.orm import Session
    from app.models import Asset,RevisionAsset,System,Subsystem,DataTemplate,Manufacturer,CommercialSolution,Revision,User,ReviewDecision
    from sqlalchemy import select
    admin=ctx.test_client()
    auth=login(admin,'admin@example.com','AdminPassword_1234')
    with Session(ctx.extensions['engine']) as db:
        u=db.scalar(select(User).where(User.role=='ADMIN'))
        system=System(code='LEG',name_es='Sistema');db.add(system);db.flush()
        sub=Subsystem(code='LEG.FAC',name_es='Fachadas',system_id=system.id)
        manufacturer=Manufacturer(code='ORG-V3',name='Organización de prueba')
        db.add_all([sub,manufacturer]);db.flush()
        db.add(DataTemplate(subsystem_id=sub.id,version=1,fields=[]))
        p=CommercialSolution(code='TEST-V3',manufacturer_id=manufacturer.id,subsystem_id=sub.id,
                             availability='SUSPENDED')
        db.add(p);db.flush()
        ctx.config['ASSET_DIR']=str(tmp_path)
        blob=(Path(__file__).resolve().parents[1]/'tests/fixtures/panel_demo.ifc').read_bytes()
        (tmp_path/'panel.ifc').write_bytes(blob)
        source=Revision(product_id=p.id,number=1,status='REJECTED',created_by=u.id,name_es='Panel',
                        technical_data={'legacy_source':'origin.json','legacy_payload':{'private':True},
                                        'composition':[{'name':'Cara exterior'}]},
                        economic_data={'unit_price':12},environmental_data={'declared_unit':'m2'})
        asset=Asset(file_type='IFC',original_name='panel.ifc',storage_key='panel.ifc',size=len(blob),
                    sha256=sha256(blob).hexdigest(),processing_status='VALID')
        db.add_all([source,asset]);db.flush()
        db.add(RevisionAsset(revision_id=source.id,asset_id=asset.id))
        db.commit()
        pid=str(p.id)
        aid=str(asset.id)
    route='/api/v1/admin/legacy/publications'
    public=ctx.test_client()
    wrong_method=public.get(route)
    assert wrong_method.status_code==405 and wrong_method.json['error']['code']=='METHOD_NOT_ALLOWED'
    assert public.get('/api/v1/products/'+pid).status_code==404
    payload={'ids':[pid,str(uuid4())],'kind':'commercial','evidence':'Registro de pruebas de publicación','confirmed':True}
    assert public.post(route,json=payload).status_code==401
    assert admin.post(route,json={'ids':[]},headers=auth).status_code==400
    manufacturer_client=ctx.test_client()
    manufacturer_auth=register(manufacturer_client,'publisher@example.com','Otra organización')
    assert manufacturer_client.post(route,json=payload,headers=manufacturer_auth).status_code==403
    inventory=admin.get('/api/v1/admin/legacy/inventory?kind=commercial',headers=auth)
    assert inventory.status_code==200,inventory.json
    assert inventory.json['meta']['total']==1
    assert 'technical_data' not in inventory.json['data'][0]
    policy={'public_view_allowed':True,'public_download_allowed':False}
    payload['document_permissions']={pid:{aid:policy}}
    rejected=admin.post(route,json=payload,headers=auth)
    assert rejected.status_code==200,rejected.json
    assert not any(row['published'] for row in rejected.json['data'])
    assert public.get('/api/v1/assets/'+aid+'/view').status_code==404
    policy['rights_evidence']='Cesión de visualización para ensayo'
    result=admin.post(route,json=payload,headers=auth)
    assert result.status_code==200,result.json
    assert sorted(row['published'] for row in result.json['data'])==[False,True]
    repeat=admin.post(route,json=payload,headers=auth)
    assert repeat.status_code==200
    assert next(row for row in repeat.json['data'] if row['id']==pid)['published'] is True
    detail=public.get('/api/v1/products/'+pid).json['data']
    published_inventory=admin.get('/api/v1/admin/legacy/inventory?kind=commercial&status=published',headers=auth)
    assert published_inventory.status_code==200,published_inventory.json
    assert published_inventory.json['meta']['total']==1
    assert detail['published']['number']==2
    assert public.get('/api/v1/assets/'+aid+'/view').data==blob
    assert public.get('/api/v1/assets/'+aid+'/download').status_code==404
    assert detail['published']['bim_status']=='VIEWABLE'
    ifc_inventory=admin.get('/api/v1/admin/ifc/inventory?kind=commercial',headers=auth)
    assert ifc_inventory.status_code==200,ifc_inventory.json
    assert ifc_inventory.json['meta']['total']==1
    assert ifc_inventory.json['data'][0]['asset_id']==aid
    assert ifc_inventory.json['data'][0]['integrity_status']=='MATCH'
    assert ifc_inventory.json['data'][0]['public_view_allowed'] is True
    integrity=admin.get('/api/v1/admin/ifc/'+aid+'/integrity',headers=auth)
    assert integrity.status_code==200 and integrity.json['data']['status']=='MATCH'
    assert admin.get('/api/v1/admin/ifc/'+aid+'/history',headers=auth).json['meta']['total']==1
    bulk='/api/v1/admin/ifc/permissions/bulk'
    policy_target={'kind':'commercial','target_id':pid,'asset_id':aid,
                   'policy':{'public_view_allowed':False,'public_download_allowed':False}}
    assert public.post(bulk,json={'confirmed':True,'targets':[policy_target]}).status_code==401
    assert manufacturer_client.post(bulk,json={'confirmed':True,'targets':[policy_target]},headers=manufacturer_auth).status_code==403
    revoked=admin.post(bulk,json={'confirmed':True,'targets':[policy_target]},headers=auth)
    assert revoked.status_code==200 and revoked.json['data'][0]['updated'] is True
    assert public.get('/api/v1/assets/'+aid+'/view').status_code==404
    policy_target['policy']={'public_view_allowed':True,'public_download_allowed':False,
                             'rights_evidence':'Autorización de prueba para visualización'}
    granted=admin.post(bulk,json={'confirmed':True,'targets':[policy_target]},headers=auth)
    assert granted.status_code==200 and granted.json['data'][0]['updated'] is True
    assert public.get('/api/v1/assets/'+aid+'/view').status_code==200
    assert public.get('/api/v1/assets/'+aid+'/download').status_code==404
    policy_target['expected']={'public_view_allowed':False,'public_download_allowed':False}
    stale=admin.post(bulk,json={'confirmed':True,'targets':[policy_target]},headers=auth)
    assert stale.json['data'][0]['code']=='CONFLICT'
    del policy_target['expected']
    policy_target['policy']={'public_view_allowed':True,'public_download_allowed':True,
                             'rights_evidence':'Autorización de descarga en ensayo'}
    assert admin.post(bulk,json={'confirmed':True,'targets':[policy_target]},headers=auth).json['data'][0]['updated']
    assert public.get('/api/v1/assets/'+aid+'/download').data==blob
    policy_target['policy']={'public_view_allowed':True,'public_download_allowed':False}
    assert admin.post(bulk,json={'confirmed':True,'targets':[policy_target]},headers=auth).json['data'][0]['updated']
    assert public.get('/api/v1/assets/'+aid+'/download').status_code==404
    assert admin.post(bulk,json={'confirmed':True,'targets':[policy_target]},headers=auth).status_code==200
    assert admin.get('/api/v1/admin/ifc/'+aid+'/history',headers=auth).json['meta']['total']==5
    (tmp_path/'panel.ifc').write_bytes(b'altered')
    assert admin.get('/api/v1/admin/ifc/'+aid+'/integrity',headers=auth).json['data']['status']=='MISMATCH'
    assert public.get('/api/v1/assets/'+aid+'/view').status_code==422
    assert public.get('/api/v1/products/'+pid).json['data']['published']['bim_status']=='CORRUPT'
    policy_target['policy']={'public_view_allowed':False,'public_download_allowed':False}
    assert admin.post(bulk,json={'confirmed':True,'targets':[policy_target]},headers=auth).json['data'][0]['updated'] is True
    policy_target['policy']={'public_view_allowed':True,'public_download_allowed':False,
                             'rights_evidence':'Autorización de prueba para visualización'}
    denied=admin.post(bulk,json={'confirmed':True,'targets':[policy_target]},headers=auth)
    assert denied.json['data'][0]['code']=='INTEGRITY'
    (tmp_path/'panel.ifc').write_bytes(blob)
    assert admin.post(bulk,json={'confirmed':True,'targets':[policy_target]},headers=auth).json['data'][0]['updated'] is True
    assert public.get('/api/v1/assets/'+aid+'/view').status_code==200
    assert 'legacy_payload' not in detail['published']['technical_data']
    assert 'legacy_source' not in detail['published']['technical_data']
    assert detail['published']['technical_data']['composition']==[{'name':'Cara exterior'}]
    assert detail['published']['economic_data']=={'unit_price':12}
    assert detail['published']['environmental_data']=={'declared_unit':'m2'}
    assert public.get('/api/v1/catalogue/counts').json['data']['products']=={detail['subsystem_id']:1}
    manufacturers=public.get('/api/v1/manufacturers?scope=catalogue').json['data']
    assert manufacturers==[{'id':detail['manufacturer_id'],'name':'Organización de prueba'}]
    page=public.get('/api/v1/products?sort=name&page_size=1')
    assert page.json['meta']['total']==1
    assert page.json['data'][0]['id']==pid
    with Session(ctx.extensions['engine']) as db:
        assert sorted(db.scalars(select(Revision.status)))==['APPROVED','REJECTED']
        assert db.scalar(select(ReviewDecision.reason))==payload['evidence']
        assert db.scalar(select(CommercialSolution).where(CommercialSolution.id==p.id)).availability=='ACTIVE'


def test_legacy_generic_publication_and_inventory(ctx):
    from sqlalchemy.orm import Session
    from sqlalchemy import select
    from app.models import System,Subsystem,Archetype,GenericSolution,Asset,GenericAsset
    admin=ctx.test_client();auth=login(admin,'admin@example.com','AdminPassword_1234')
    with Session(ctx.extensions['engine']) as db:
        system=System(code='GLEG',name_es='Sistema');db.add(system);db.flush()
        sub=Subsystem(code='GLEG.WAL',name_es='Muro',system_id=system.id);db.add(sub);db.flush()
        archetype=Archetype(code='GLEG.WAL.A',name_es='Arquetipo',subsystem_id=sub.id);db.add(archetype);db.flush()
        rec=GenericSolution(code='GLEG.WAL.A.GS001',name_es='Ficha histórica',subsystem_id=sub.id,
            archetype_id=archetype.id,status='DRAFT',technical_data={'legacy_source':'test.json','properties':{'test':1}},
            economic_data={'price':12},environmental_data={'epd':'private'},composition=[{'layer':'a'}])
        db.add(rec);db.flush()
        asset=Asset(file_type='IFC',original_name='test.ifc',storage_key='test.ifc',size=1,sha256='0'*64,processing_status='VALID')
        db.add(asset);db.flush();db.add(GenericAsset(generic_id=rec.id,asset_id=asset.id))
        db.commit();id=str(rec.id)
    inventory=admin.get('/api/v1/admin/legacy/inventory?kind=generic&page_size=20',headers=auth)
    assert inventory.status_code==200,inventory.json
    assert inventory.json['meta']['total']==1
    assert 'technical_data' not in inventory.json['data'][0]
    payload={'kind':'generic','ids':[id],'evidence':'Registro editorial de prueba','confirmed':True}
    for _ in range(2):
        result=admin.post('/api/v1/admin/legacy/publications',json=payload,headers=auth)
        assert result.status_code==200 and result.json['data'][0]['published'] is True
    assert admin.get('/api/v1/admin/legacy/inventory?kind=generic&status=published',headers=auth).json['meta']['total']==1
    assert ctx.test_client().get('/api/v1/generic-solutions/'+id).status_code==200
    with Session(ctx.extensions['engine']) as db:
        current=db.get(GenericSolution,rec.id)
        assert current.status=='PUBLISHED'
        assert current.economic_data=={'price':12}
        assert current.environmental_data=={'epd':'private'}
        assert current.composition==[{'layer':'a'}]


def test_admin_ifc_generic_permission_persists_without_republication(ctx,tmp_path,monkeypatch):
    from hashlib import sha256
    from pathlib import Path
    from sqlalchemy.orm import Session
    from sqlalchemy import select
    from app.models import System,Subsystem,Archetype,GenericSolution,Asset,GenericAsset,AuditLog,Extraction
    from app.parsers import parse_ifc
    from app.ifc_thumbnails import cache_thumbnail
    from app import asset_service as api_module
    ctx.config['ASSET_DIR']=str(tmp_path)
    blob=(Path(__file__).resolve().parents[1]/'tests/fixtures/panel_demo.ifc').read_bytes()
    (tmp_path/'generic.ifc').write_bytes(blob)
    with Session(ctx.extensions['engine']) as db:
        system=System(code='G-PERM',name_es='Sistema');db.add(system);db.flush()
        sub=Subsystem(code='G-PERM.SUB',name_es='Subsistema',system_id=system.id);db.add(sub);db.flush()
        archetype=Archetype(code='G-PERM.ARC',name_es='Arquetipo',subsystem_id=sub.id);db.add(archetype);db.flush()
        item=GenericSolution(code='G-PERM.GS1',name_es='Genérica ensayo',subsystem_id=sub.id,
            archetype_id=archetype.id,status='PUBLISHED',technical_data={'property':'preserved'},
            economic_data={'price':7},environmental_data={'epd':'original'},composition=[{'layer':'a'}])
        asset=Asset(file_type='IFC',original_name='generic.ifc',storage_key='generic.ifc',
            size=len(blob),sha256=sha256(blob).hexdigest(),processing_status='VALID')
        db.add_all([item,asset]);db.flush();db.add(GenericAsset(generic_id=item.id,asset_id=asset.id))
        parsed=parse_ifc(blob)
        db.add(Extraction(asset_id=asset.id,source_format='IFC',schema_version=parsed['schema_version'],
                          normalized=parsed,warnings=parsed['warnings'],is_valid=True))
        db.commit();item_id=str(item.id);asset_id=str(asset.id)
    client=ctx.test_client();auth=login(client,'admin@example.com','AdminPassword_1234')
    public=ctx.test_client();route='/api/v1/admin/ifc/permissions/bulk'
    tree='/api/v1/documents/'+asset_id+'/ifc-tree'
    preview='/api/v1/documents/'+asset_id+'/thumbnail'
    assert cache_thumbnail(tmp_path.resolve(),tmp_path/'generic.ifc',sha256(blob).hexdigest())
    assert public.get(tree).status_code==404
    assert public.get(preview).status_code==404
    target={'kind':'generic','target_id':item_id,'asset_id':asset_id,
        'expected':{'public_view_allowed':False,'public_download_allowed':False},
        'policy':{'public_view_allowed':True,'public_download_allowed':False,
                  'rights_evidence':'Autorización de ensayo para visualización'}}
    assert public.get('/api/v1/generic-solutions/'+item_id).json['data']['bim_status']=='PRIVATE'
    invalid=client.post(route,json={'confirmed':True,'targets':[dict(target,policy={
        'public_view_allowed':True,'public_download_allowed':False,'rights_evidence':'corto'})]},headers=auth)
    assert invalid.json['data'][0]['code']=='VALIDATION'
    granted=client.post(route,json={'confirmed':True,'targets':[target]},headers=auth)
    assert granted.status_code==200 and granted.json['data'][0]['updated']
    assert public.get('/api/v1/generic-solutions/'+item_id).json['data']['bim_status']=='VIEWABLE'
    view=public.get('/api/v1/assets/'+asset_id+'/view')
    assert view.data==blob
    assert view.headers['X-METRA-View-Format']=='IFC_ORIGINAL'
    thumbnail=public.get(preview)
    assert thumbnail.status_code==200 and b'<polygon' in thumbnail.data
    assert 'no-store' in thumbnail.headers['Cache-Control']
    actual=api_module.ifc_file_state
    calls=[]
    def file_state(asset,verify=True):
        calls.append(verify)
        return actual(asset,verify)
    monkeypatch.setattr(api_module,'ifc_file_state',file_state)
    catalog=public.get('/api/v1/generic-solutions?q=G-PERM.GS1').json['data'][0]
    assert catalog['assets'][0]['thumbnail_available'] is True
    assert calls==[False]
    result=public.get(tree)
    assert result.status_code==200,result.json
    assert result.json['data'][0]['global_id']==parsed['elements'][0]['global_id']
    assert 'psets' not in result.json['data'][0]
    assert result.json['meta']['truncated'] is False
    assert public.get('/api/v1/assets/'+asset_id+'/download').status_code==404
    with Session(ctx.extensions['engine']) as db:
        link=db.get(GenericAsset,{'generic_id':item.id,'asset_id':asset.id})
        assert link.public_view_allowed and not link.public_download_allowed
        assert db.scalar(select(GenericSolution).where(GenericSolution.id==item.id)).status=='PUBLISHED'
        assert db.scalar(select(AuditLog).where(AuditLog.action=='DOCUMENT_POLICY')) is not None
    target['expected']={'public_view_allowed':True,'public_download_allowed':False}
    target['policy']={'public_view_allowed':False,'public_download_allowed':False}
    revoked=client.post(route,json={'confirmed':True,'targets':[target]},headers=auth)
    assert revoked.json['data'][0]['updated']
    assert public.get('/api/v1/generic-solutions/'+item_id).json['data']['bim_status']=='PRIVATE'
    assert public.get('/api/v1/assets/'+asset_id+'/view').status_code==404
    assert public.get(tree).status_code==404
    assert public.get(preview).status_code==404
    assert client.get('/api/v1/admin/ifc/inventory?kind=generic',headers=auth).json['data'][0]['public_view_allowed'] is False
    (tmp_path/'second.ifc').write_bytes(blob)
    with Session(ctx.extensions['engine']) as db:
        second=Asset(file_type='IFC',original_name='second.ifc',storage_key='second.ifc',
            size=len(blob),sha256=sha256(blob).hexdigest(),processing_status='VALID')
        db.add(second);db.flush();db.add(GenericAsset(generic_id=item.id,asset_id=second.id))
        db.commit();second_id=str(second.id)
    first={'kind':'generic','target_id':item_id,'asset_id':asset_id,
        'expected':{'public_view_allowed':False,'public_download_allowed':False},
        'policy':{'public_view_allowed':True,'public_download_allowed':False,
                  'rights_evidence':'Visualización concedida en lote de ensayo'}}
    second_target={'kind':'generic','target_id':item_id,'asset_id':second_id,
        'expected':{'public_view_allowed':False,'public_download_allowed':False},
        'policy':{'public_view_allowed':False,'public_download_allowed':True,
                  'rights_evidence':'Descarga concedida en lote de ensayo'}}
    batch=client.post(route,json={'confirmed':True,'targets':[first,second_target]},headers=auth)
    assert batch.status_code==200 and all(x['updated'] for x in batch.json['data'])
    assert public.get('/api/v1/assets/'+asset_id+'/view').status_code==200
    assert public.get('/api/v1/assets/'+asset_id+'/download').status_code==404
    assert public.get('/api/v1/assets/'+second_id+'/view').status_code==404
    assert public.get('/api/v1/documents/'+second_id+'/ifc-tree').status_code==404
    assert public.get('/api/v1/assets/'+second_id+'/download').data==blob


def test_v3_ifc_import_reimport_preserves_assets_and_links(ctx,tmp_path):
    from scripts.import_metra_demo import ROOT,source_documents,import_generic,import_commercial
    from app.models import Asset,GenericAsset,RevisionAsset,GenericSolution,CommercialSolution,Revision,User
    from sqlalchemy.orm import Session
    from sqlalchemy import select,func
    from hashlib import sha256
    root=ROOT/'data/metra-demo'
    commercial_path,commercial_doc=next(source_documents(root,'manufacturer_solutions'))
    subsystem_code=commercial_doc['manufacturer_solutions'][0]['subsystem_code']
    generic_path,generic_doc=next((path,doc) for path,doc in source_documents(root,'generic_solutions')
        if (doc.get('catalogue') or {}).get('subsystem',{}).get('code')==subsystem_code)
    with Session(ctx.extensions['engine']) as db:
        author=db.scalar(select(User).where(User.role=='ADMIN'))
        first_generic=import_generic(db,root,generic_path,generic_doc,tmp_path,True)
        first_commercial=import_commercial(db,root,commercial_path,commercial_doc,tmp_path,author,True)
        before=(db.scalar(select(func.count()).select_from(Asset)),
                db.scalar(select(func.count()).select_from(GenericAsset)),
                db.scalar(select(func.count()).select_from(RevisionAsset)),
                db.scalar(select(func.count()).select_from(Revision)))
        second_generic=import_generic(db,root,generic_path,generic_doc,tmp_path,True)
        second_commercial=import_commercial(db,root,commercial_path,commercial_doc,tmp_path,author,True)
        after=(db.scalar(select(func.count()).select_from(Asset)),
               db.scalar(select(func.count()).select_from(GenericAsset)),
               db.scalar(select(func.count()).select_from(RevisionAsset)),
               db.scalar(select(func.count()).select_from(Revision)))
        assert first_generic[0]>0 and first_commercial[0]>0
        assert second_generic[0]==0 and second_commercial[0]==0
        assert before==after
        assert after[0]==after[1]+after[2]
        for asset in db.scalars(select(Asset)):
            assert sha256((tmp_path/asset.storage_key).read_bytes()).hexdigest()==asset.sha256
        db.commit()


def test_v3_ifc_restore_rejects_changed_source(ctx,tmp_path,monkeypatch):
    from hashlib import sha256
    from sqlalchemy.orm import Session
    from scripts import import_metra_demo as import_metra_demo
    from app.models import Asset

    source=tmp_path/'changed.ifc'
    source.write_bytes(b'changed source')
    monkeypatch.setattr(import_metra_demo,'get_asset_path',lambda *_:source)
    key=sha256(b'v3:generic_solutions:TEST:source.ifc').hexdigest()+'.ifc'
    with Session(ctx.extensions['engine']) as db:
        db.add(Asset(original_name='source.ifc',storage_key=key,file_type='IFC',
                     sha256=sha256(b'original source').hexdigest(),size=15,
                     processing_status='VALID'))
        db.flush()
        with pytest.raises(RuntimeError,match='ha cambiado'):
            import_metra_demo.ingest_ifc(db,tmp_path/'store',tmp_path,source,
                                 'generic_solutions','TEST','source.ifc')
        assert not (tmp_path/'store'/key).exists()


def test_cost_database_persists_independently_and_regenerates(ctx,tmp_path):
    from io import BytesIO
    from app.worker import process_next
    ctx.config['ASSET_DIR']=str(tmp_path)
    c=ctx.test_client()
    auth=login(c,'admin@example.com','AdminPassword_1234')
    route='/api/v1/cost-databases'
    assert c.get('/api/v1/admin/price-books',headers=auth).status_code==404
    raw=b'~V|test|FIEBDC-3/2020|\r\n~C|ONE|m|Elemento|15|\r\n'
    def upload():
        return c.post(route+'/imports',headers=auth,data={'name':'Referencia de ensayo','file':(BytesIO(raw),'test.bc3')})
    result=upload()
    assert result.status_code==202,result.json
    assert c.get(route+'/imports',headers=auth).json['data'][0]['state']=='PENDING'
    assert upload().status_code==409
    assert process_next(ctx.extensions['engine'],tmp_path)
    job=c.get(route+'/imports',headers=auth).json['data'][0]
    assert job['state']=='VALID' and job['concept_count']==1
    version=c.get(route,headers=auth).json['data'][0]
    concepts=c.get(route+'/'+version['id']+'/concepts',headers=auth).json['data']
    assert [(x['code'],x['unit_price']) for x in concepts]==[('ONE',15)]
    url=route+'/'+version['id']+'/export/bc3'
    assert c.get(url).status_code==401
    assert c.get(url,headers=auth).data==raw
    assert len(list(tmp_path.iterdir()))==1

    invalid=c.post(route+'/imports',headers=auth,
                   data={'name':'Ensayo inválido','file':(BytesIO(b'contenido sin registros'),'invalid.bc3')})
    assert invalid.status_code==202,invalid.json
    assert process_next(ctx.extensions['engine'],tmp_path)
    jobs=c.get(route+'/imports',headers=auth).json['data']
    failed=next(job for job in jobs if job['asset_id']==invalid.json['data']['asset_id'])
    assert failed['state']=='INVALID' and failed['version_id'] is None


def test_manufacturer_documents_publication_and_new_revision(ctx,tmp_path):
    from pathlib import Path
    from sqlalchemy.orm import Session
    from app.models import System,Subsystem,DataTemplate
    from app.worker import process_next
    ctx.config['ASSET_DIR']=str(tmp_path)
    admin=ctx.test_client()
    admin_auth=login(admin,'admin@example.com','AdminPassword_1234')
    maker=ctx.test_client()
    maker_auth=register(maker,'maker@example.com','Product test organization')
    with Session(ctx.extensions['engine']) as db:
        system=System(code='BIM',name_es='BIM');db.add(system);db.flush()
        sub=Subsystem(code='BIM.PAN',name_es='Paneles',system_id=system.id);db.add(sub);db.flush()
        db.add(DataTemplate(subsystem_id=sub.id,version=1,fields=[]))
        db.commit()
        sub_id=str(sub.id)
    created=maker.post('/api/v1/manufacturer/products',headers=maker_auth,json={
        'subsystem_id':sub_id,'code':'PANEL-TEST','name_es':'Panel de prueba','functional_unit':'m2'
    })
    assert created.status_code==201,created.json
    item=created.json['data']
    pid=item['id'];rid=item['revisions'][0]['id']
    revision='/api/v1/manufacturer/revisions/'+rid
    update={'name_es':'Panel de prueba','functional_unit':'m2','composition':[{'name':'Aislante','material':'Fibra','thickness_mm':100}]}
    invalid=maker.patch(revision,headers=maker_auth,json={**update,'composition':[{'name':'Capa','thickness_mm':0}]})
    assert invalid.status_code==422,invalid.json
    changed=maker.patch(revision,headers=maker_auth,json=update)
    assert changed.status_code==200,changed.json
    assert changed.json['data']['technical_data']['composition']==update['composition']
    eco={'label':'Coste declarado','value':12.5,'unit':'EUR/m2','source':'Fabricante'}
    env={'label':'GWP declarado','value':-2,'unit':'kg CO2e','source':'Ficha técnica'}
    changed=maker.patch(revision,headers=maker_auth,json={**update,'economic_values':[eco],'environmental_values':[env]})
    assert changed.status_code==200,changed.json
    assert changed.json['data']['economic_data']['declared']==[eco]
    assert changed.json['data']['environmental_data']['declared']==[env]
    unchanged=maker.patch(revision,headers=maker_auth,json=update)
    assert unchanged.json['data']['economic_data']['declared']==[eco]
    fixture=Path(__file__).resolve().parent/'fixtures'
    models=[]
    for name in ('panel_demo.ifc','lignum.xml'):
        with (fixture/name).open('rb') as file:
            upload=maker.post(revision+'/assets',headers=maker_auth,data={'file':(file,name)})
        assert upload.status_code==202,upload.json
        asset=upload.json['data']
        assert asset['processing_status']=='PENDING'
        processing='/api/v1/documents/'+asset['id']+'/processing'
        assert maker.get(processing,headers=maker_auth).json['data']['state']=='PENDING'
        assert process_next(ctx.extensions['engine'],tmp_path)
        assert maker.get(processing,headers=maker_auth).json['data']['state']=='VALID'
        models.append(asset)
    from io import BytesIO
    upload=maker.post(revision+'/assets',headers=maker_auth,
        data={'file':(BytesIO(b'~V|test|FIEBDC-3/2020|\n~C|PANEL|m2|Panel|35|'), 'panel.bc3')})
    assert upload.status_code==202,upload.json
    models.append(upload.json['data'])
    assert process_next(ctx.extensions['engine'],tmp_path)
    for asset in models:
        perm=maker.patch(revision+'/assets/'+asset['id'],headers=maker_auth,json={
            'public_download_allowed':True,'public_view_allowed':asset['file_type']=='IFC',
            'rights_evidence':'Autorización de ensayo'
        })
        assert perm.status_code==200,perm.json
    source='/api/v1/documents/'+models[0]['id']+'/data'
    guid=next(row['global_id'] for row in maker.get(source,headers=maker_auth).json['data'] if row['global_id'])
    link_url=revision+'/component-links'
    link_read='/api/v1/revisions/'+rid+'/component-links'
    link_params={'ifc_asset_id':models[0]['id'],'global_id':guid}
    body={'ifc_asset_id':models[0]['id'],'ifc_global_id':guid,
          'target_asset_id':models[2]['id'],'concept_code':'PANEL','evidence':'Correspondencia comprobada en el ensayo'}
    invalid=maker.post(link_url,headers=maker_auth,json={**body,'concept_code':'INEXISTENTE'})
    assert invalid.status_code==422,invalid.json
    linked=maker.post(link_url,headers=maker_auth,json=body)
    assert linked.status_code==201,linked.json
    assert maker.get(link_read,headers=maker_auth,query_string=link_params).json['data'][0]['evidence']==body['evidence']
    public=ctx.test_client()
    assert public.get(link_read,query_string=link_params).status_code==404
    assert public.get('/api/v1/products?ifc=1').json['data']==[]
    submitted=maker.post(revision+'/submit',headers=maker_auth,json={})
    assert submitted.status_code==200,submitted.json
    approved=admin.post('/api/v1/admin/reviews/bulk-approve',headers=admin_auth,
                        json={'ids':[rid],'confirmed':True})
    assert approved.json['data'][0]['published'],approved.json
    catalogue=public.get('/api/v1/products?q=PANEL-TEST&ifc=1&bc3=1&epd=1')
    assert [p['id'] for p in catalogue.json['data']]==[pid]
    detail=public.get('/api/v1/products/'+pid).json['data']['published']
    assert {asset['file_type'] for asset in detail['assets']}=={'IFC','EPD','BC3'}
    public_links=public.get(link_read,query_string=link_params).json['data']
    assert [link['concept_code'] for link in public_links]==['PANEL']
    assert 'evidence' not in public_links[0]
    assert maker.delete(link_url+'/'+linked.json['data']['id'],headers=maker_auth).status_code==409
    assert public.get('/api/v1/assets/'+models[0]['id']+'/view').data.startswith(b'ISO-10303-21')
    ifc='/api/v1/assets/'+models[0]['id']
    policy='/api/v1/admin/products/'+pid+'/assets/'+models[0]['id']
    assert admin.patch(policy,headers=admin_auth,json={
        'public_view_allowed':True,'public_download_allowed':False
    }).status_code==200
    assert public.get(ifc+'/view').status_code==200
    assert public.get(ifc+'/download').status_code==404
    document='/api/v1/documents/'+models[0]['id']
    assert public.get(document+'/data?page_size=1').json['meta']['page_size']==1
    assert 'elements' not in public.get(document+'/summary').json['data']
    assert admin.patch(policy,headers=admin_auth,json={
        'public_view_allowed':True,'public_download_allowed':True
    }).status_code==422
    assert maker.patch(revision,headers=maker_auth,json={}).status_code==409
    route='/api/v1/manufacturer/products/'+pid+'/revisions'
    next_revision=maker.post(route,headers=maker_auth,json={'source_revision_id':rid})
    assert next_revision.status_code==201,next_revision.json
    draft=next_revision.json['data']
    assert draft['parent_id']==rid
    assert draft['technical_data']['composition']==update['composition']
    assert not any(asset['public_view_allowed'] or asset['public_download_allowed'] for asset in draft['assets'])
    cloned=maker.get('/api/v1/revisions/'+draft['id']+'/component-links',headers=maker_auth,query_string=link_params)
    assert [link['concept_code'] for link in cloned.json['data']]==['PANEL']
    assert maker.post(route,headers=maker_auth,json={'source_revision_id':rid}).status_code==409
    assert public.get('/api/v1/products/'+pid).json['data']['published']['id']==rid



def test_budget_edit_access_totals_and_export(ctx):
    from decimal import Decimal
    from app.parsers import parse_bc3

    owner=ctx.test_client()
    headers=register(owner,'owner@example.com','Presupuestos')
    other=ctx.test_client()
    other_headers=register(other,'other@example.com','Otra organización')
    response=owner.post('/api/v1/budgets',headers=headers,json={'name':'Presupuesto de ensayo'})
    assert response.status_code==201,response.json
    route='/api/v1/budgets/'+response.json['data']['id']
    assert other.get(route,headers=other_headers).status_code==404
    assert ctx.test_client().get(route).status_code==404

    item={'code':'MAT-01','description':'Panel','unit':'m2','quantity':'2.5','unit_price':'4.25'}
    response=owner.post(route+'/items',headers=headers,json=item)
    assert response.status_code==201,response.json
    item_route=route+'/items/'+response.json['data']['id']
    assert owner.patch(item_route,headers=headers,json={**item,'quantity':'3.5'}).status_code==200
    totals=owner.get(route+'/totals',headers=headers).json['data']
    assert totals['items']==1
    assert Decimal(totals['total'])==Decimal('14.875')
    export=owner.get(route+'/export/bc3',headers=headers)
    assert export.status_code==200
    assert any(concept['code']=='MAT-01' for concept in parse_bc3(export.data)['concepts'])
    assert owner.delete(item_route,headers=headers).status_code==200
    assert owner.get(route+'/totals',headers=headers).json['data']['items']==0


def test_generic_ifc_permissions_can_change_while_published(ctx,tmp_path):
    from pathlib import Path
    from app.worker import process_next

    ctx.config['ASSET_DIR']=str(tmp_path)
    admin=ctx.test_client()
    headers=login(admin,'admin@example.com','AdminPassword_1234')
    base='/api/v1/admin/catalogue'

    def create(kind,code,**body):
        result=admin.post(base+'/'+kind,headers=headers,json={'code':code,'name_es':code,**body})
        assert result.status_code==201,result.json
        return result.json['data']['id']

    system=create('systems','SYS')
    subsystem=create('subsystems','SYS.SUB',system_id=system)
    archetype=create('archetypes','SYS.SUB.ARC',subsystem_id=subsystem)
    generic=create('generic-solutions','GEN-001',archetype_id=archetype,technical_data={'properties':{'test':True}})
    path=Path(__file__).resolve().parents[1]/'tests/fixtures/panel_demo.ifc'
    with path.open('rb') as file:
        response=admin.post('/api/v1/admin/generic-solutions/'+generic+'/assets',headers=headers,
                            data={'file':(file,path.name)})
    assert response.status_code==202,response.json
    asset=response.json['data']['id']
    assert process_next(ctx.extensions['engine'],tmp_path)
    assert admin.post(base+'/generic-solutions/'+generic+'/publish',headers=headers).status_code==200

    public=ctx.test_client()
    detail='/api/v1/generic-solutions/'+generic
    original='/api/v1/assets/'+asset
    assert public.get(detail).json['data']['assets']==[]
    policy='/api/v1/admin/generic-solutions/'+generic+'/assets/'+asset
    response=admin.patch(policy,headers=headers,json={
        'public_view_allowed':True,'public_download_allowed':False,'rights_evidence':'Cesión de visualización de ensayo'
    })
    assert response.status_code==200,response.json
    assert public.get(detail).json['data']['assets'][0]['id']==asset
    assert public.get(original+'/view').data.startswith(b'ISO-10303-21')
    assert public.get(original+'/download').status_code==404
    assert admin.patch(policy,headers=headers,json={
        'public_view_allowed':False,'public_download_allowed':False
    }).status_code==200
    assert public.get(detail).json['data']['status']=='PUBLISHED'
    assert public.get(original+'/view').status_code==404
    assert admin.post('/api/v1/admin/assets/'+asset+'/reprocess',headers=headers).status_code==202
    assert process_next(ctx.extensions['engine'],tmp_path)
    from app.models import Extraction
    from sqlalchemy import func,select
    from sqlalchemy.orm import Session
    from uuid import UUID
    with Session(ctx.extensions['engine']) as db:
        count=db.scalar(select(func.count()).select_from(Extraction).where(Extraction.asset_id==UUID(asset)))
        assert count==1


def test_public_catalogue_queries_do_not_grow_per_card(ctx):
    from sqlalchemy import event
    from sqlalchemy.orm import Session
    from app.models import Archetype,CommercialSolution,GenericSolution,Manufacturer,Revision,Subsystem,System,User
    from sqlalchemy import select

    engine=ctx.extensions['engine']
    with Session(engine) as db:
        author=db.scalar(select(User).where(User.role=='ADMIN'))
        system=System(code='PERF',name_es='Sistema')
        db.add(system);db.flush()
        subsystem=Subsystem(code='PERF.SUB',name_es='Subsistema',system_id=system.id)
        maker=Manufacturer(code='PERF.M',name='Fabricante')
        db.add_all([subsystem,maker]);db.flush()
        archetype=Archetype(code='PERF.A',name_es='Arquetipo',subsystem_id=subsystem.id)
        db.add(archetype);db.flush()
        for number in range(12):
            db.add(GenericSolution(code=f'PERF.G{number}',name_es=f'Genérica {number}',status='PUBLISHED',
                   archetype_id=archetype.id,subsystem_id=subsystem.id))
            product=CommercialSolution(code=f'PERF.P{number}',manufacturer_id=maker.id,subsystem_id=subsystem.id)
            db.add(product);db.flush()
            revision=Revision(product_id=product.id,number=1,name_es=f'Producto {number}',status='APPROVED',created_by=author.id)
            db.add(revision);db.flush()
            product.published_revision_id=revision.id
        db.commit()

    statements=[]
    def collect(_conn,_cursor,statement,*_):
        if statement.lstrip().upper().startswith('SELECT'):
            statements.append(statement)

    event.listen(engine,'before_cursor_execute',collect)
    try:
        client=ctx.test_client()
        for resource,expected in [('generic-solutions',4),('products',6)]:
            amounts=[]
            for size in (1,12):
                statements.clear()
                response=client.get(f'/api/v1/{resource}?page_size={size}')
                assert response.status_code==200,response.json
                assert len(response.json['data'])==size
                amounts.append(len(statements))
            assert amounts==[expected,expected]
    finally:
        event.remove(engine,'before_cursor_execute',collect)


def test_public_two_solution_comparator_mixed_visibility_and_legacy_rejection(ctx):
    """Executed only against an explicitly disposable TEST_DATABASE_URL."""
    from sqlalchemy.orm import Session
    from sqlalchemy import select
    from app.models import (System, Subsystem, Archetype, GenericSolution, Manufacturer, DataTemplate,
                            CommercialSolution, Revision, User)
    with Session(ctx.extensions['engine']) as db:
        actor=db.scalar(select(User).where(User.role=='ADMIN'))
        system=System(code='CMP',name_es='Comparación');db.add(system);db.flush()
        sub=Subsystem(code='CMP.FAC',name_es='Fachadas',system_id=system.id)
        db.add(sub);db.flush()
        db.add(DataTemplate(subsystem_id=sub.id,version=1,fields=[]))
        arch=Archetype(code='CMP.FAC.A',name_es='Arquetipo',subsystem_id=sub.id)
        db.add(arch);db.flush()
        generic=GenericSolution(code='CMP.GS001',name_es='Genérica publicada',archetype_id=arch.id,
                                subsystem_id=sub.id,status='PUBLISHED',technical_data={'functional_unit':'m2'},
                                composition=[],environmental_data={},economic_data={})
        hidden=GenericSolution(code='CMP.GS002',name_es='Genérica privada',archetype_id=arch.id,
                               subsystem_id=sub.id,status='DRAFT',technical_data={},composition=[],
                               environmental_data={},economic_data={})
        maker=Manufacturer(code='CMP-ORG',name='Fabricante ensayo')
        db.add_all([generic,hidden,maker]);db.flush()
        product=CommercialSolution(code='CMP.P001',manufacturer_id=maker.id,subsystem_id=sub.id,
                                   availability='ACTIVE')
        db.add(product);db.flush()
        revision=Revision(product_id=product.id,number=1,status='APPROVED',name_es='Producto publicado',
                          functional_unit='m2',technical_data={'properties':{}},economic_data={},
                          environmental_data={},created_by=actor.id)
        db.add(revision);db.flush();product.published_revision_id=revision.id
        db.commit();gid=str(generic.id);hidden_id=str(hidden.id);pid=str(product.id)
    client=ctx.test_client()
    result=client.get('/api/v1/solutions/compare',query_string={'ids':f'g:{gid},p:{pid}'})
    assert result.status_code==200,result.json
    assert [item['kind'] for item in result.json['data']['solutions']]==['generic','commercial']
    assert len(result.json['data']['solutions'])==2
    assert result.json['data']['same_functional_unit'] is True
    assert client.get('/api/v1/solutions/compare',query_string={
        'ids':f'g:{gid},g:{hidden_id}'}).status_code==404
    assert client.get('/api/v1/solutions/compare',query_string={
        'ids':f'g:{gid},p:{pid},g:{hidden_id}'}).status_code==422
    assert client.get('/api/v1/products/compare',query_string={
        'ids':f'{pid},{pid},{pid}'}).status_code==422


def test_v4_comparison_scope_and_property_filter(ctx):
    from sqlalchemy.orm import Session
    from app.catalogue import install_templates
    from app.models import System, Subsystem, Archetype, GenericSolution
    with Session(ctx.extensions['engine']) as db:
        system = System(code='ENV', name_es='Envolvente')
        db.add(system); db.flush()
        facade = Subsystem(code='ENV.FAC', name_es='Fachada', system_id=system.id)
        roof = Subsystem(code='ENV.CUB', name_es='Cubierta', system_id=system.id)
        db.add_all([facade, roof]); db.flush()
        facade_arch = Archetype(code='ENV.FAC.A', name_es='Fachada A', subsystem_id=facade.id)
        roof_arch = Archetype(code='ENV.CUB.A', name_es='Cubierta A', subsystem_id=roof.id)
        db.add_all([facade_arch, roof_arch]); db.flush()
        items = []
        for code, sub, arch, thickness in [('G1',facade,facade_arch,100),('G2',facade,facade_arch,200),('G3',roof,roof_arch,150)]:
            item = GenericSolution(code=code,name_es=code,subsystem_id=sub.id,archetype_id=arch.id,status='PUBLISHED',
                                   technical_data={'functional_unit':'m2','properties':{'total_thickness_mm':thickness}})
            db.add(item); items.append(item)
        assert install_templates(db) == 2
        db.flush()
        assert install_templates(db) == 0
        ids = [str(item.id) for item in items]; fid = str(facade.id); rid = str(roof.id); sid = str(system.id)
        db.commit()
    client = ctx.test_client()
    same = f'g:{ids[0]},g:{ids[1]}'
    diff = f'g:{ids[0]},g:{ids[2]}'
    assert client.get('/api/v1/solutions/compare', query_string={'ids':same,'system_id':sid,'subsystem_id':fid}).status_code == 200
    for query in ({'ids':diff}, {'ids':same,'subsystem_id':rid}):
        response = client.get('/api/v1/solutions/compare', query_string=query)
        assert response.status_code == 422 and response.json['error']['code'] == 'INCOMPATIBLE_SUBSYSTEM'
    filtered = client.get('/api/v1/generic-solutions', query_string={'subsystem_id':fid,'property':'total_thickness_mm','minimum':150,'template_summary':1})
    assert filtered.status_code == 200, filtered.json
    assert [row['id'] for row in filtered.json['data']] == [ids[1]]
    assert filtered.json['data'][0]['template_highlights']
    assert filtered.json['meta']['total'] == 1
    assert client.get('/api/v1/admin/data-quality').status_code in (401,403)
