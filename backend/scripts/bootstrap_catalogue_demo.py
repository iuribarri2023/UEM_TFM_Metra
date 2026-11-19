"""One-time academic publication on a dedicated database and asset volume."""
import json
import hashlib
import os
import sys
from pathlib import Path
from secrets import token_urlsafe

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app.inventory import inventory
from boot_credentials import credentials, read_rights
from catalogue_data import validate
from app.catalogue import install_templates
from app.data_quality import quality_report
from app.models import (Asset, AuditLog, CatalogueInitialization, CommercialSolution,
                        GenericAsset, GenericSolution, Revision,
                        RevisionAsset, RevisionGeneric, RevisionOrigin, User,
                        System, Subsystem, Archetype, now)
from app.security import ph
from import_metra_demo import IMPORT_AUTHOR, get_or_add, import_commercial, import_generic, source_documents
from app.source_reconciliation import reconcile, initialize_baselines

KEY = 'catalogue-first-publication'
ORIGIN = 'Publicación inicial del catálogo'


def complete_source_taxonomy(db,root):
    """Include valid empty source families before installing their templates."""
    for _path,doc in source_documents(root,'generic_solutions'):
        catalogue=doc.get('catalogue') or {}
        if not all((catalogue.get(key) or {}).get('code') for key in ('system','subsystem','archetype')):
            raise RuntimeError('Taxonomía canónica incompleta')
        system,subsystem,archetype=(catalogue[key] for key in ('system','subsystem','archetype'))
        parent=get_or_add(db,System,system['code'],name_es=system.get('name_es') or system['code'])
        branch=get_or_add(db,Subsystem,subsystem['code'],name_es=subsystem.get('name_es') or subsystem['code'],
                          system_id=parent.id)
        get_or_add(db,Archetype,archetype['code'],name_es=archetype.get('name_es') or archetype['code'],
                   subsystem_id=branch.id)


def publish_commercial(db, product, author):
    source = db.scalar(select(Revision).where(Revision.product_id == product.id, Revision.number == 1))
    published = Revision(product_id=product.id, number=2, status='APPROVED', created_by=author.id,
                         decided_at=now(), name_es=source.name_es, description=source.description,
                         commercial_reference=source.commercial_reference, functional_unit=source.functional_unit,
                         template_version=source.template_version, technical_data=source.technical_data,
                         economic_data=source.economic_data, environmental_data=source.environmental_data)
    db.add(published)
    db.flush()
    for link in db.scalars(select(RevisionAsset).where(RevisionAsset.revision_id == source.id)):
        db.add(RevisionAsset(revision_id=published.id, asset_id=link.asset_id,
                             public_view_allowed=False, public_download_allowed=False))
    for link in db.scalars(select(RevisionGeneric).where(RevisionGeneric.revision_id == source.id)):
        db.add(RevisionGeneric(revision_id=published.id, generic_id=link.generic_id))
    db.add(RevisionOrigin(revision_id=published.id, parent_id=source.id, message=ORIGIN))
    product.published_revision_id = published.id
    product.availability = 'ACTIVE'
    db.add(AuditLog(action='INITIAL_CATALOGUE_PUBLICATION', entity='revision',
                    entity_id=str(published.id), detail={'origin': ORIGIN}))


def bootstrap(db, store):
    db.execute(text('SELECT pg_advisory_xact_lock(287197612)'))
    previous = db.get(CatalogueInitialization, KEY)
    manifest = inventory()
    validate()
    existing = previous is not None or db.scalar(select(GenericSolution.id).limit(1)) is not None or db.scalar(select(CommercialSolution.id).limit(1)) is not None
    root = BACKEND / 'data/metra-demo'
    if existing:
        # A historic completion flag or any single row is never sufficient
        # evidence of complete import. Reconcile safely on every start.
        if not db.scalar(select(User.id).where(User.role=='ADMIN',User.active.is_(True)).limit(1)):
            email,password=credentials()
            if db.scalar(select(User.id).where(User.email==email)):
                raise RuntimeError('La cuenta administrativa existente requiere revisión; no se cambian credenciales.')
            db.add(User(email=email,password_hash=ph.hash(password),role='ADMIN',active=True))
            db.flush()
        author = db.scalar(select(User).where(User.email == IMPORT_AUTHOR))
        if author is None:
            author=User(email=IMPORT_AUTHOR,password_hash=ph.hash(token_urlsafe(42)),role='ADMIN',active=False)
            db.add(author)
            db.flush()
        if author.active:
            raise RuntimeError('La identidad técnica de importación debe estar deshabilitada.')
        # Repair a partial template installation before importing new revisions.
        complete_source_taxonomy(db,root)
        result_templates=install_templates(db)
        result=reconcile(db,root,store,apply=True)
        if result['documents']['missing_records']:
            from app.source_reconciliation import source_entries
            missing=set(result['documents']['missing_records'])
            visited=set()
            for kind,key,path,doc,_item,_source in source_entries(root):
                if key not in missing or (kind,path) in visited:continue
                visited.add((kind,path))
                imported=(import_generic(db,root,path,doc,store,True) if kind=='g' else
                          import_commercial(db,root,path,doc,store,author,True))
                if imported[2]:raise RuntimeError('Reparación de activos incompleta: '+'; '.join(imported[2][:5]))
            result['documents']['missing_records_before_repair']=result['documents']['missing_records']
            result['documents']['missing_records']=[]
        result_templates+=install_templates(db)
        from scripts.audit_asset_storage import audit as audit_storage
        storage=audit_storage(db,store,apply=True,restore=True)
        result['storage_recovery']={key:storage[key] for key in ('restored','recoverable','missing','wrong_hash')}
        result['new_templates']=result_templates
        if (result['documents']['missing_records'] or result['documents']['wrong_hash']
                or storage['wrong_hash'] or set(storage['missing'])-set(storage['restored'])):
            raise RuntimeError('La instalación contiene IFC ausentes o corruptos; consultar auditoría documental.')
        result['documents']['missing_files_before_recovery']=result['documents']['missing_files']
        result['documents']['missing_files']=[]
        result['existing_installation']=True
        result['initial_publication_preserved']=True
        from app.source_reconciliation import source_entries
        expected={key for _,key,*_ in source_entries(root)}
        actual={f'g:{code}' for code in db.scalars(select(GenericSolution.code))} | {
            f'p:{code}' for code in db.scalars(select(CommercialSolution.code))}
        result['complete_business_inventory']=expected.issubset(actual)
        result['publication']={
            'generic_published':db.scalar(select(func.count()).select_from(GenericSolution).where(GenericSolution.status=='PUBLISHED')),
            'commercial_published':db.scalar(select(func.count()).select_from(CommercialSolution).where(CommercialSolution.availability=='ACTIVE',CommercialSolution.published_revision_id.is_not(None))),
        }
        result['pending_approval']={
            'generic':db.scalar(select(func.count()).select_from(GenericSolution).where(GenericSolution.status=='DRAFT')),
            'commercial':db.scalar(select(func.count()).select_from(CommercialSolution).where(CommercialSolution.published_revision_id.is_(None))),
        }
        result['readiness']='DEGRADED' if (any(result['counts'][key] for key in
            ('conflicts','unbaselined','proposed')) or not result['complete_business_inventory']
            or result['publication']['generic_published']<manifest['counts']['generic']
            or result['publication']['commercial_published']<manifest['counts']['commercial']) else 'HEALTHY'
        return result
    email, password = credentials()
    rights = read_rights(manifest)
    admin = db.scalar(select(User).where(User.email==email))
    if admin is None:
        admin=User(email=email,password_hash=ph.hash(password),role='ADMIN',active=True)
        db.add(admin)
        db.flush()
    elif not admin.active or admin.role!='ADMIN' or not ph.verify(admin.password_hash,password):
        raise ValueError('La cuenta inicial ya existe con otras credenciales o permisos.')
    author = db.scalar(select(User).where(User.email == IMPORT_AUTHOR))
    if author is None:
        author = User(email=IMPORT_AUTHOR, password_hash=ph.hash(token_urlsafe(42)), role='ADMIN', active=False)
        db.add(author)
        db.flush()
    elif author.active:
        raise RuntimeError('La identidad técnica de importación debe estar deshabilitada.')
    for category in ('generic_solutions', 'manufacturer_solutions'):
        if category == 'manufacturer_solutions':
            # Capture the matching template contract when creating revision 1.
            templates = install_templates(db)
        for path, doc in source_documents(root, category):
            result = (import_generic(db, root, path, doc, store, True) if category == 'generic_solutions'
                      else import_commercial(db, root, path, doc, store, author, True))
            if result[2]:
                raise RuntimeError('Importación METRA-DEMO con conflictos: ' + '; '.join(result[2][:4]))
    db.flush()
    generics = list(db.scalars(select(GenericSolution)))
    products = list(db.scalars(select(CommercialSolution)))
    assets = db.scalar(select(func.count()).select_from(Asset).where(Asset.file_type == 'IFC', Asset.processing_status == 'VALID'))
    expected = {f'g:{item.code}' for item in generics} | {f'p:{item.code}' for item in products}
    if (len(generics), len(products), assets) != (manifest['counts']['generic'], manifest['counts']['commercial'], len(manifest['references'])):
        raise RuntimeError('El inventario activo no coincide con el manifiesto METRA-DEMO.')
    for asset in db.scalars(select(Asset).where(Asset.file_type == 'IFC')):
        path = (store / asset.storage_key).resolve()
        if path.parent != store or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != asset.sha256:
            raise RuntimeError('Un IFC no supera la comprobación de integridad de arranque.')
    templates += install_templates(db)
    for generic in generics:
        generic.status = 'PUBLISHED'
        db.add(AuditLog(action='INITIAL_CATALOGUE_PUBLICATION', entity='generic', entity_id=str(generic.id),
                        detail={'origin': ORIGIN}))
    for product in products:
        publish_commercial(db, product, author)
    db.flush()
    for item in [*generics,*products]:
        kind='g' if isinstance(item,GenericSolution) else 'p'
        rule=rights.get(f'{kind}:{item.code}')
        if rule is None:
            continue
        assoc=GenericAsset if kind=='g' else RevisionAsset
        owner=assoc.generic_id if kind=='g' else assoc.revision_id
        owner_id=item.id if kind=='g' else item.published_revision_id
        link=db.scalar(select(assoc).join(Asset,Asset.id==assoc.asset_id).where(
            owner==owner_id,Asset.sha256==rule['sha256'],Asset.processing_status=='VALID'))
        if link is None:
            raise ValueError(f'Derechos sin un activo válido asociado: {item.code}')
        link.public_view_allowed=rule['view']
        link.public_download_allowed=rule['download']
        db.add(AuditLog(actor_id=admin.id,action='INITIAL_DOCUMENT_RIGHTS',entity='asset',
                        entity_id=str(link.asset_id),detail=rule))
    report = {'generic_published': len(generics), 'commercial_published': len(products),
              'valid_ifcs': assets, 'new_templates': templates, 'consolidated_records': len(expected),
              'origin': ORIGIN, 'normalized_solutions': quality_report(db)['solutions']}
    initialize_baselines(db,root)
    db.add(CatalogueInitialization(key=KEY, report=report))
    return report


def main():
    engine = create_engine(os.environ['DATABASE_URL'], hide_parameters=True)
    with Session(engine) as db, db.begin():
        result = bootstrap(db, Path(os.environ['ASSET_DIR']).resolve())
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
