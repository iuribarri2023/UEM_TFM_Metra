"""Import native METRA-DEMO JSON + IFC into the standalone Marketplace safely.

Run in the *new* backend, after Alembic migrations:
  python scripts/import_metra_demo.py                 # inventory (read-only)
  python scripts/import_metra_demo.py --apply         # idempotent import into PostgreSQL + ASSET_DIR
  python scripts/import_metra_demo.py /mnt/external --apply

The original source snapshots are preserved in data/metra-demo. No manufacturer or IFC
asset is granted public access automatically. Original "APPROVED" does not
constitute authorization to publish a third-party brand/model today.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from secrets import token_urlsafe
from sqlalchemy import create_engine,select,text
from sqlalchemy.orm import Session

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.models import (System,Subsystem,Archetype,GenericSolution,GenericSlot,
    Manufacturer,CommercialSolution,Revision,RevisionGeneric,User,
    Asset,GenericAsset,RevisionAsset,Extraction,DataTemplate)
from app.consolidated_data import imported_payload, prior_storage_uris
from app.asset_identity import storage_key
from app.parsers import parse_ifc,ParseFailure
from app.asset_staging import promote_if_absent

ROOT=Path(__file__).resolve().parents[1]
IMPORT_AUTHOR='legacy-import@invalid.local'


def source_documents(root:Path,collection:str):
    home=root/collection/'metra-demo'
    for path in sorted(home.rglob('*.json')):
        if path.name in ('taxonomy.json','validation-report.json'):
            continue
        try:
            content=json.loads(path.read_text(encoding='utf-8'))
            if isinstance(content,dict) and isinstance(content.get(collection),list):
                yield path,content
        except (ValueError,UnicodeError) as exc:
            print(f'WARNING: invalid JSON {path}: {exc}',file=sys.stderr)


def get_or_add(db,model,code,**kwargs):
    existing=db.scalar(select(model).where(model.code==code))
    if existing:return existing
    rec=model(code=code,**kwargs)
    db.add(rec);db.flush();return rec


def legacy_source(path:Path,root:Path):
    return str(path.relative_to(root)).replace('\\','/')


def safe_source(candidate:Path,root:Path):
    home=root.resolve()
    result=candidate.resolve()
    if not result.is_relative_to(home):
        raise ValueError('Ruta de activo fuera del dataset metra-demo')
    return result


def get_asset_path(json_path:Path,root:Path,collection:str,uri:str):
    if not isinstance(uri,str) or not uri.lower().endswith('.ifc'):
        return None
    # The generic manifests are rooted at generic_solutions/metra-demo.
    # Commercial manifests are relative to their individual JSON directory (ENV/FAC etc).
    base=root/collection/'metra-demo'
    options=[json_path.parent/uri,base/uri]
    for candidate in options:
        p=safe_source(candidate,base)
        if p.is_file():return p
    return None


def ifc_uris(doc:dict):
    files=doc.get('assets')
    if isinstance(files,dict):
        return [v for k,v in files.items() if k.lower()=='ifc' and isinstance(v,str)]
    if isinstance(files,list):
        return [f.get('uri') for f in files if isinstance(f,dict) and
                (str(f.get('format','')).upper()=='IFC' or str(f.get('role','')).upper()=='PRIMARY_IFC')
                and isinstance(f.get('uri'),str)]
    return []


def ingest_ifc(db,store:Path,root:Path,json_path:Path,collection:str,
               entity_code:str,uri:str,manufacturer_id=None,generic_id=None,revision_id=None):
    src=get_asset_path(json_path,root,collection,uri)
    if not src:
        return False,'IFC mencionado en JSON pero no encontrado: '+uri
    content=src.read_bytes()
    digest=hashlib.sha256(content).hexdigest()
    kind = 'g' if collection == 'generic_solutions' else 'p'
    old_uri = prior_storage_uris().get(f'{kind}:{entity_code}', {}).get(uri, uri)
    # Identity must remain stable in PostgreSQL and existing asset volumes.
    # 'v3:' is an immutable historical storage namespace, not the active dataset name.
    key=storage_key(collection,entity_code,old_uri)
    target=safe_source(store/key,store)
    # After metadata normalization a previous installation may retain the original
    # IFC under the same stable storage key. Preserve it and its DB SHA until a
    # deliberate reconciliation is performed; never silently rewrite asset bytes.
    old_digest=None
    if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest()!=digest:
        compatibility_file=ROOT/'data/integrity/ifc-metadata-compatibility.json'
        compatibility=json.loads(compatibility_file.read_text(encoding='utf-8'))
        source_rel=src.relative_to(root).as_posix()
        pair=compatibility.get(source_rel)
        previous=hashlib.sha256(target.read_bytes()).hexdigest()
        if not pair or pair!=[previous,digest]:
            raise RuntimeError(f'El archivo persistente no coincide con su huella: {entity_code}')
        old_digest=previous
    asset=db.scalar(select(Asset).where(Asset.storage_key==key))
    if not asset:
        if old_digest:
            raise RuntimeError('Activo histórico sin registro; requiere reconciliación documental.')
        try:
            normalized=parse_ifc(content)
            normalized.update(source_path=legacy_source(src,root),sha256=digest,
                              source_dataset='metra-demo',validation_level='basic_open_and_guid_uniqueness')
            valid=True
            warnings=normalized.get('warnings',[])
        except ParseFailure as exc:
            normalized={'schema_version':'1.0','source_format':'IFC','source_dataset':'metra-demo',
                        'source_path':legacy_source(src,root),'sha256':digest,'parse_error':str(exc)}
            valid=False;warnings=[str(exc)]
        # Promotion is atomic at filesystem level; a post-rollback orphan is
        # detected by the storage audit (no unsafe automatic deletion).
        promote_if_absent(store,key,content,sha256=digest)
        asset=Asset(manufacturer_id=manufacturer_id,original_name=src.name[:255],storage_key=key,
                    file_type='IFC',sha256=digest,size=len(content),
                    processing_status='VALID' if valid else 'INVALID')
        db.add(asset);db.flush()
        db.add(Extraction(asset_id=asset.id,schema_version='1.0',source_format='IFC',
                          normalized=normalized,warnings=warnings,is_valid=valid))
    else:
        if asset.sha256!=digest and asset.sha256!=old_digest:
            raise RuntimeError(f'El archivo de origen ha cambiado para el código {entity_code}. Revisión manual requerida.')
        target=store/key
        if not target.is_file():
            if asset.sha256 != digest:
                raise RuntimeError('Original IFC missing: reconciliation with backup required')
            promote_if_absent(store,key,content,sha256=digest)
    if generic_id and not db.get(GenericAsset,{'generic_id':generic_id,'asset_id':asset.id}):
        db.add(GenericAsset(generic_id=generic_id,asset_id=asset.id,
                            public_download_allowed=False,public_view_allowed=False))
    if revision_id and not db.get(RevisionAsset,{'revision_id':revision_id,'asset_id':asset.id}):
        db.add(RevisionAsset(revision_id=revision_id,asset_id=asset.id,
                             public_download_allowed=False,public_view_allowed=False))
    return True,None


def import_generic(db,root:Path,json_path:Path,doc:dict,store:Path,with_assets:bool):
    cat=doc.get('catalogue') or {}
    if not all(cat.get(k,{}).get('code') for k in ('system','subsystem','archetype')):
        return 0,0,['Taxonomía incompleta: '+str(json_path)]
    s,ss,a=(cat['system'],cat['subsystem'],cat['archetype'])
    sys=get_or_add(db,System,s['code'],name_es=s.get('name_es') or s['code'])
    subsystem=get_or_add(db,Subsystem,ss['code'],name_es=ss.get('name_es') or ss['code'],system_id=sys.id)
    archetype=get_or_add(db,Archetype,a['code'],name_es=a.get('name_es') or a['code'],subsystem_id=subsystem.id)
    created=assets=0;warnings=[]
    for item in doc['generic_solutions']:
        code=item['code']
        entry=db.scalar(select(GenericSolution).where(GenericSolution.code==code))
        if not entry:
            technical=imported_payload(item,legacy_source(json_path,root))
            entry=GenericSolution(code=code,name_es=item.get('name_es') or code,
                archetype_id=archetype.id,subsystem_id=subsystem.id,status='DRAFT',
                technical_data=technical,composition=item.get('composition') or [],
                economic_data=item.get('economic_data') or {},
                environmental_data=item.get('environmental_data') or {})
            db.add(entry);db.flush();created+=1
            used=set()
            for pos,slot in enumerate(item.get('composition') or []):
                if not isinstance(slot,dict):continue
                base=str(slot.get('code') or slot.get('slot_code') or f'SLOT-{pos+1:03d}')[:85]
                scode=base;counter=1
                while scode in used:
                    counter+=1;scode=f'{base[:85]}-{counter}'
                used.add(scode)
                db.add(GenericSlot(generic_solution_id=entry.id,code=scode,
                    name_es=str(slot.get('name_es') or slot.get('name') or scode)[:255],
                    slot_order=pos,required=bool(slot.get('required',False)),properties=slot))
        if with_assets:
            for uri in ifc_uris(item):
                ok,warning=ingest_ifc(db,store,root,json_path,'generic_solutions',code,uri,generic_id=entry.id)
                if ok:assets+=1
                if warning:warnings.append(warning)
    return created,assets,warnings


def import_commercial(db,root:Path,json_path:Path,doc:dict,store:Path,author,with_assets:bool):
    m=doc.get('manufacturer') or {}
    if not m.get('code'):return 0,0,['Fabricante sin código: '+str(json_path)]
    manufacturer=get_or_add(db,Manufacturer,m['code'],name=m.get('name') or m['code'],
           description=m.get('description') or '',website=m.get('website') if str(m.get('website') or '').startswith('https://') else None,
           status='ACTIVE',contact_public=False)
    created=assets=0;warnings=[]
    for item in doc['manufacturer_solutions']:
        code=item['code']
        subsystem=db.scalar(select(Subsystem).where(Subsystem.code==item.get('subsystem_code')))
        if not subsystem:
            warnings.append('Subsistema no encontrado '+str(item.get('subsystem_code'))+' para '+code)
            continue
        product=db.scalar(select(CommercialSolution).where(CommercialSolution.code==code))
        if not product:
            product=CommercialSolution(code=code,manufacturer_id=manufacturer.id,
                                       subsystem_id=subsystem.id,availability='SUSPENDED')
            db.add(product);db.flush()
            rev=Revision(product_id=product.id,number=1,status='REJECTED',
                name_es=item.get('name_es') or code,commercial_reference=item.get('commercial_reference') or '',
                description=item.get('description') or '',functional_unit=item.get('functional_unit') or 'unit',
                created_by=author.id,template_version=(db.scalar(select(DataTemplate.version).where(
                    DataTemplate.subsystem_id==subsystem.id).order_by(DataTemplate.version.desc()).limit(1)) or 1),rejection_reason='Importación histórica pendiente de validación de derechos y fuentes',
                technical_data={**imported_payload(item,legacy_source(json_path,root)), 'composition':item.get('composition') or []},
                economic_data=item.get('economic_data') or {},
                environmental_data=item.get('environmental_data') or {})
            db.add(rev);db.flush()
            codes=list(dict.fromkeys(([item['generic_solution_code']] if item.get('generic_solution_code') else [])+
                (item.get('generic_solution_codes') or [])))
            for generic_code in codes:
                generic=db.scalar(select(GenericSolution).where(GenericSolution.code==generic_code))
                if generic and generic.subsystem_id==subsystem.id:
                    db.add(RevisionGeneric(revision_id=rev.id,generic_id=generic.id))
                else:warnings.append('Referencia genérica incompatible/ausente: '+code+' -> '+str(generic_code))
            created+=1
        else:
            rev=db.scalar(select(Revision).where(Revision.product_id==product.id,Revision.number==1))
            if not rev:
                warnings.append('Producto preexistente sin revisión histórica 1: '+code)
                continue
        if with_assets:
            for uri in ifc_uris(item):
                ok,warning=ingest_ifc(db,store,root,json_path,'manufacturer_solutions',code,uri,
                    manufacturer_id=manufacturer.id,revision_id=rev.id)
                if ok:assets+=1
                if warning:warnings.append(warning)
    return created,assets,warnings


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path,nargs='?',default=ROOT/'data/metra-demo')
    parser.add_argument('--apply',action='store_true',help='Persistir entidades e IFC bajo ASSET_DIR')
    parser.add_argument('--skip-assets',action='store_true',help='Solo JSON; no recomendado para el catálogo')
    args=parser.parse_args()
    root=args.source.resolve()
    gfiles=list(source_documents(root,'generic_solutions'))
    cfiles=list(source_documents(root,'manufacturer_solutions'))
    generic_count=sum(len(d['generic_solutions']) for _,d in gfiles)
    commercial_count=sum(len(d['manufacturer_solutions']) for _,d in cfiles)
    all_assets=sum(len(ifc_uris(item)) for _,d in gfiles for item in d['generic_solutions'])+sum(
        len(ifc_uris(item)) for _,d in cfiles for item in d['manufacturer_solutions'])
    print(f'Fuentes metra-demo: {len(gfiles)} JSON genéricos ({generic_count} registros), '
          f'{len(cfiles)} JSON comerciales ({commercial_count} registros), {all_assets} referencias IFC')
    if not gfiles or not cfiles:raise SystemExit('No se ha encontrado el dataset metra-demo completo')
    if not args.apply:
        print('Modo lectura: base de datos intacta. Para importar ejecuta --apply.');return
    if not os.environ.get('DATABASE_URL'):raise SystemExit('DATABASE_URL obligatorio')
    from argon2 import PasswordHasher
    ph=PasswordHasher()
    store=Path(os.getenv('ASSET_DIR','/data/assets')).resolve()
    engine=create_engine(os.environ['DATABASE_URL'],pool_pre_ping=True)
    created_g=created_c=linked=0;warnings=[]
    with Session(engine) as db:
        db.execute(text('SELECT pg_advisory_xact_lock(287197612)'))
        user=db.scalar(select(User).where(User.email==IMPORT_AUTHOR))
        if not user:
            user=User(email=IMPORT_AUTHOR,password_hash=ph.hash(token_urlsafe(42)),role='ADMIN',active=False)
            db.add(user);db.flush()
        for path,doc in gfiles:
            new,count,issues=import_generic(db,root,path,doc,store,not args.skip_assets)
            created_g+=new;linked+=count;warnings+=issues
        from app.catalogue import install_templates
        install_templates(db)
        for path,doc in cfiles:
            new,count,issues=import_commercial(db,root,path,doc,store,user,not args.skip_assets)
            created_c+=new;linked+=count;warnings+=issues
        if warnings:
            raise RuntimeError('Importación con incidencias, transacción revertida: ' + '; '.join(warnings[:10]))
        from app.catalogue import install_templates
        install_templates(db)
        db.commit()
    print(f'Nuevos registros: genéricas={created_g}, comerciales={created_c}; '
          f'IFC vinculados/verificados en esta ejecución={linked}. Advertencias={len(warnings)}')
    for warning in warnings[:30]:print('WARNING:',warning,file=sys.stderr)
    if warnings:print(f'Consulta las {len(warnings)} advertencias; se han mostrado como máximo 30.')
    print('Publicación: NO. Genéricas DRAFT; comerciales SUSPENDED con revisión REJECTED; permisos privados.')

if __name__=='__main__':main()
