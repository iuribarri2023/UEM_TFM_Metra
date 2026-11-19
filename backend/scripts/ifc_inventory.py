"""Read-only METRA-DEMO IFC integrity and geometry audit; --repair is explicit and idempotent."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from sqlalchemy import create_engine,select
from sqlalchemy.orm import Session

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.models import Asset,CommercialSolution,Extraction,GenericAsset,GenericSolution,Revision,RevisionAsset,User
from app.consolidated_data import prior_storage_uris
from import_metra_demo import ROOT,source_documents,ifc_uris,get_asset_path
from app.asset_identity import storage_key


def expected_sources():
    root=ROOT/'data/metra-demo'
    for kind,collection in [('generic','generic_solutions'),('commercial','manufacturer_solutions')]:
        for manifest,doc in source_documents(root,collection):
            for item in doc[collection]:
                for uri in ifc_uris(item):
                    path=get_asset_path(manifest,root,collection,uri)
                    old_uri=prior_storage_uris().get(('g' if kind=='generic' else 'p')+':'+item['code'],{}).get(uri,uri)
                    # Historical storage identity is immutable across the METRA-DEMO rename.
                    key=storage_key(collection,item['code'],old_uri)
                    yield kind,item['code'],key,path


def geometry_probe(path):
    import ifcopenshell
    import ifcopenshell.geom
    model=ifcopenshell.open(str(path))
    if not model:return False
    settings=ifcopenshell.geom.settings()
    for product in model.by_type('IfcProduct'):
        if not getattr(product,'Representation',None):continue
        try:
            shape=ifcopenshell.geom.create_shape(settings,product)
            if shape and len(shape.geometry.verts)>0:return True
        except Exception:
            continue
    return False


def audit(db,store,geometry=False):
    counts=Counter();warnings=[];repairable=[]
    expected=list(expected_sources())
    counts['metra_demo_references']=len(expected)
    known={a.storage_key:a for a in db.scalars(select(Asset).where(Asset.file_type=='IFC'))}
    for kind,code,key,source in expected:
        asset=known.get(key)
        if not asset:
            counts['missing_asset_record']+=1;warnings.append(f'{kind}:{code}: recurso no registrado');continue
        counts['registered']+=1
        path=(store/key).resolve()
        if path.parent!=store or not path.is_file():
            counts['missing_file']+=1;warnings.append(f'{kind}:{code}: original ausente')
            if source and source.is_file() and hashlib.sha256(source.read_bytes()).hexdigest()==asset.sha256:
                repairable.append(key);counts['restorable_from_source']+=1
            continue
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest!=asset.sha256:
            counts['hash_mismatch']+=1;warnings.append(f'{kind}:{code}: SHA-256 no coincide');continue
        counts['integrity_ok']+=1
        if asset.processing_status=='VALID':counts['valid']+=1
        else:counts['invalid_or_pending']+=1
        extraction=db.scalar(select(Extraction).where(Extraction.asset_id==asset.id).order_by(Extraction.created_at.desc(),Extraction.id.desc()))
        if extraction and extraction.is_valid:counts['extraction_valid']+=1
        else:counts['extraction_missing_or_invalid']+=1
        if geometry:
            try:
                if geometry_probe(path):counts['geometry_probe_ok']+=1
                else:counts['geometry_probe_failed']+=1;warnings.append(f'{kind}:{code}: sin geometría triangulable')
            except Exception:
                counts['geometry_probe_failed']+=1;warnings.append(f'{kind}:{code}: error de geometría')
        if kind=='generic':
            target=db.scalar(select(GenericSolution.id).where(GenericSolution.code==code))
            link=db.get(GenericAsset,(target,asset.id)) if target else None
            if link:counts['linked_generic']+=1
        else:
            target=db.scalar(select(CommercialSolution.id).where(CommercialSolution.code==code))
            revision=db.scalar(select(Revision.id).where(Revision.product_id==target,Revision.number==1)) if target else None
            link=db.get(RevisionAsset,(revision,asset.id)) if revision else None
            if link:counts['linked_commercial_source']+=1
            product=db.get(CommercialSolution,target) if target else None
            if product and product.published_revision_id and db.get(RevisionAsset,(product.published_revision_id,asset.id)):
                counts['linked_commercial_published']+=1
        if not link:counts['missing_link']+=1;warnings.append(f'{kind}:{code}: vínculo ausente')
        else:
            if link.public_view_allowed:counts['view_allowed']+=1
            if link.public_download_allowed:counts['download_allowed']+=1
    counts['all_ifc_assets']=len(known)
    expected_map={key:(kind,code) for kind,code,key,_ in expected}
    associated=set()
    for asset_id,code,key in db.execute(select(GenericAsset.asset_id,GenericSolution.code,Asset.storage_key)
            .join(GenericSolution,GenericSolution.id==GenericAsset.generic_id)
            .join(Asset,Asset.id==GenericAsset.asset_id).where(Asset.file_type=='IFC')):
        associated.add(asset_id)
        if key in expected_map and expected_map[key]!=('generic',code):
            counts['incorrect_association']+=1;warnings.append(f'{code}: vínculo genérico ajeno a su fuente')
    for asset_id,code,key in db.execute(select(RevisionAsset.asset_id,CommercialSolution.code,Asset.storage_key)
            .join(Revision,Revision.id==RevisionAsset.revision_id)
            .join(CommercialSolution,CommercialSolution.id==Revision.product_id)
            .join(Asset,Asset.id==RevisionAsset.asset_id).where(Asset.file_type=='IFC')):
        associated.add(asset_id)
        if key in expected_map and expected_map[key]!=('commercial',code):
            counts['incorrect_association']+=1;warnings.append(f'{code}: vínculo comercial ajeno a su fuente')
    counts['unassociated']=sum(asset.id not in associated for asset in known.values())
    return dict(counts),warnings,repairable


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--geometry',action='store_true',help='Probar triangulación con IfcOpenShell; puede tardar')
    parser.add_argument('--repair',action='store_true',help='Reimportar idempotentemente desde las fuentes METRA-DEMO y encolar IFC inválidos')
    args=parser.parse_args()
    engine=create_engine(os.environ['DATABASE_URL'],pool_pre_ping=True,hide_parameters=True)
    if args.repair:
        if os.getenv('METRA_IFC_REPAIR')!='1' or not os.getenv('METRA_IFC_ADMIN_EMAIL'):
            raise SystemExit('METRA_IFC_REPAIR=1 y METRA_IFC_ADMIN_EMAIL obligatorios')
        with Session(engine) as db:
            actor=db.scalar(select(User).where(User.email==os.environ['METRA_IFC_ADMIN_EMAIL'].strip().lower(),User.role=='ADMIN',User.active==True))
            if not actor:raise SystemExit('Administrador activo requerido')
        subprocess.run([sys.executable,str(Path(__file__).with_name('import_metra_demo.py')),'--apply'],check=True)
    store=Path(os.getenv('ASSET_DIR','/data/assets')).resolve()
    with Session(engine) as db:
        counts,warnings,_=audit(db,store,args.geometry)
        if args.repair:
            actor=db.scalar(select(User).where(User.email==os.environ['METRA_IFC_ADMIN_EMAIL'].strip().lower(),User.role=='ADMIN',User.active==True))
            if not actor:raise SystemExit('Administrador activo requerido')
            from app import create_app
            from app.documents import queue_document
            from flask import g
            with create_app().app_context():
                g.db=db;g._user=actor
                for asset in db.scalars(select(Asset).where(Asset.file_type=='IFC',Asset.processing_status=='INVALID')):
                    queue_document(asset,force=True)
            db.commit()
    print(json.dumps(counts,ensure_ascii=False,sort_keys=True))
    for warning in warnings[:100]:print('WARNING:',warning,file=sys.stderr)
    if len(warnings)>100:print(f'WARNING: {len(warnings)-100} advertencias adicionales',file=sys.stderr)


if __name__=='__main__':main()
