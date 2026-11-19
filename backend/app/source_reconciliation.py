"""Conservative METRA-DEMO source-to-PostgreSQL three-way reconciliation.

Only source-only changes to unpublished generics are automatically applied. All
changes to published snapshots and commercial revisions become persisted,
auditable proposals. No current revision or approved publication is overwritten.
"""
from __future__ import annotations
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from sqlalchemy import select

from .consolidated_data import imported_payload, prior_storage_uris
from .asset_identity import storage_key as stable_asset_key
from .models import (Asset, CatalogueSourceState, CommercialSolution, GenericSolution,
                     Revision, User, Subsystem, System, Archetype, Manufacturer)

DATASET = 'metra-demo'
SOURCE_FIELDS_G = ('name_es','technical_data','composition','economic_data','environmental_data')
SOURCE_FIELDS_P = ('name_es','description','commercial_reference','functional_unit',
                   'technical_data','economic_data','environmental_data')


def clean(value):
    """The source file location is not a business property; ignore its renaming."""
    if isinstance(value, dict):
        return {key:clean(item) for key,item in value.items() if key!='legacy_source'}
    if isinstance(value, list):
        return [clean(item) for item in value]
    return value


def fingerprint(value):
    return hashlib.sha256(json.dumps(clean(value),ensure_ascii=False,sort_keys=True,
        separators=(',',':')).encode('utf-8')).hexdigest()


def source_values(kind, item, path, root, doc=None):
    relative=path.relative_to(root).as_posix()
    technical=clean(imported_payload(item,relative))
    if kind=='g':
        classification=(doc or {}).get('catalogue',{})
        group={name:classification.get(name,{}).get('code') for name in ('system','subsystem','archetype')}
        return {**({'classification': group} if doc is not None else {}),'name_es':item.get('name_es') or item['code'], 'technical_data':technical,
                'composition':item.get('composition') or [],
                'economic_data':item.get('economic_data') or {},
                'environmental_data':item.get('environmental_data') or {}}
    return {**({'classification':{'subsystem':item.get('subsystem_code'),
                         'manufacturer':(doc or {}).get('manufacturer',{}).get('code')}} if doc is not None else {}),
            'name_es':item.get('name_es') or item['code'],
            'description':item.get('description') or '',
            'commercial_reference':item.get('commercial_reference') or '',
            'functional_unit':item.get('functional_unit') or 'unit',
            'technical_data':{**technical,'composition':item.get('composition') or []},
            'economic_data':item.get('economic_data') or {},
            'environmental_data':item.get('environmental_data') or {}}


def source_entries(root):
    """Return one entity per code; no document-level snapshot hash collisions."""
    from scripts.import_metra_demo import source_documents
    seen=set()
    for kind,collection in (('g','generic_solutions'),('p','manufacturer_solutions')):
        for path,doc in source_documents(root,collection):
            for item in doc[collection]:
                key=f'{kind}:{item["code"]}'
                if key in seen:raise ValueError('Duplicated source entity: '+key)
                seen.add(key)
                yield kind,key,path,doc,item,source_values(kind,item,path,root,doc)


_MISSING=object()


def _report_value(value):
    return {'$missing':True} if value is _MISSING else deepcopy(value)


def three_way(baseline, origin, persisted):
    """Compare dictionary property paths; arrays remain indivisible values."""
    decisions={}
    def visit(path,old,source,target):
        if all(isinstance(value,dict) for value in (old,source,target)):
            for key in sorted(old.keys() | source.keys() | target.keys()):
                child=f'{path}/{str(key).replace("~","~0").replace("/","~1")}' if path else str(key)
                visit(child,old.get(key,_MISSING),source.get(key,_MISSING),target.get(key,_MISSING))
            return
        if source==old and target==old: outcome='UNCHANGED'
        elif source==old: outcome='DESTINATION_ONLY'
        elif target==source: outcome='CONVERGED'
        elif target==old: outcome='SOURCE_ONLY'
        else: outcome='CONFLICT'
        decisions[path]={'operation':outcome,'previous':_report_value(old),
                         'source':_report_value(source),'destination':_report_value(target)}
    for field in sorted(baseline.keys() | origin.keys() | persisted.keys()):
        visit(field,baseline.get(field,_MISSING),origin.get(field,_MISSING),persisted.get(field,_MISSING))
    return decisions


def apply_source_paths(target,source,paths):
    """Build a fresh JSON value with only independently accepted source paths."""
    result=deepcopy(target)
    for path in paths:
        parts=[part.replace('~1','/').replace('~0','~') for part in path.split('/')]
        value=source
        for part in parts[:-1]:value=value[part]
        parent=result
        for part in parts[:-1]:parent=parent[part]
        if parts[-1] in value:parent[parts[-1]]=deepcopy(value[parts[-1]])
        else:parent.pop(parts[-1],None)
    return result


def persisted_values(db,kind,code):
    if kind=='g':
        entity=db.scalar(select(GenericSolution).where(GenericSolution.code==code))
        if entity is None:return None,None,None
        sub=db.get(Subsystem,entity.subsystem_id)
        arch=db.get(Archetype,entity.archetype_id)
        system=db.get(System,sub.system_id) if sub else None
        payload={key:clean(getattr(entity,key)) for key in SOURCE_FIELDS_G}
        payload['classification']={'system':system.code if system else None,
            'subsystem':sub.code if sub else None,'archetype':arch.code if arch else None}
        return entity,entity,payload
    entity=db.scalar(select(CommercialSolution).where(CommercialSolution.code==code))
    if entity is None:return None,None,None
    revision=(db.get(Revision,entity.published_revision_id) if entity.published_revision_id else None)
    if revision is None:
        revision=db.scalar(select(Revision).where(Revision.product_id==entity.id).order_by(Revision.number).limit(1))
    if revision is None:return entity,None,None
    sub=db.get(Subsystem,entity.subsystem_id)
    maker=db.get(Manufacturer,entity.manufacturer_id)
    payload={key:clean(getattr(revision,key)) for key in SOURCE_FIELDS_P}
    payload['classification']={'subsystem':sub.code if sub else None,
                               'manufacturer':maker.code if maker else None}
    return entity,revision,payload


def get_state(db,key):
    return db.get(CatalogueSourceState,key)


def store_baseline(db,key,origin):
    state=get_state(db,key)
    if state is None:
        state=CatalogueSourceState(key=key,dataset=DATASET,baseline=origin,
                                  source_hash=fingerprint(origin),pending={},status='SYNCED')
        db.add(state)
    else:
        state.dataset=DATASET
        state.baseline=origin
        state.source_hash=fingerprint(origin)
        state.pending={}
        state.status='SYNCED'
    return state


def initialize_baselines(db,root):
    """Used only after full initial import; every initial entity is known to match."""
    for _kind,key,_path,_doc,_item,source in source_entries(root):
        store_baseline(db,key,source)


def reconcile(db,root:Path,store:Path,*,apply=False,allow_import=True):
    """A dry run performs no writes, including no DB flush or file changes."""
    from scripts.import_metra_demo import import_commercial,import_generic,IMPORT_AUTHOR
    report={'dataset':DATASET,'mode':'apply' if apply else 'dry-run',
            'counts':{'new':0,'synced':0,'updated':0,'proposed':0,'conflicts':0,'unbaselined':0,'orphaned':0},
            'operations':[]}
    seen=set()
    initially_present={f'g:{code}' for code in db.scalars(select(GenericSolution.code))} | {
        f'p:{code}' for code in db.scalars(select(CommercialSolution.code))}
    for kind,key,path,doc,item,source in source_entries(root):
        seen.add(key)
        entity,record,target=persisted_values(db,kind,item['code'])
        state=get_state(db,key)
        if apply and state is not None and state.dataset != DATASET:
            state.dataset = DATASET
        operation={'code':item['code'],'kind':kind}
        if key not in initially_present:
            operation['status']='NEW'
            report['counts']['new']+=1
            if apply:
                author=db.scalar(select(User).where(User.email==IMPORT_AUTHOR))
                if kind=='p' and author is None:
                    raise RuntimeError('Identidad técnica importadora ausente; crear antes de reconciliar')
                if entity is None:
                    if kind=='g':
                        _,_,issues=import_generic(db,root,path,doc,store,True)
                    else:
                        _,_,issues=import_commercial(db,root,path,doc,store,author,True)
                else:
                    issues=[]
                if issues:raise RuntimeError('Importación incompleta: '+'; '.join(issues[:5]))
                # New commercial entities remain unapproved; never auto-publish.
                store_baseline(db,key,source)
        elif state is None:
            if target==source:
                operation['status']='BASELINE_RECONSTRUCTED'
                report['counts']['synced']+=1
                if apply:store_baseline(db,key,source)
            else:
                operation.update(status='UNBASELINED',reason='No existe snapshot fiable; se preservan los datos de PostgreSQL',
                                 source_hash=fingerprint(source), destination_hash=fingerprint(target))
                report['counts']['unbaselined']+=1
                if apply:
                    db.add(CatalogueSourceState(key=key,dataset=DATASET,baseline={},
                                               source_hash=fingerprint(source),status='UNBASELINED',
                                               pending={'reason':operation['reason']}))
        elif not state.baseline:
            operation.update(status='UNBASELINED',reason='Pendiente de verificación manual de la línea base')
            report['counts']['unbaselined']+=1
        else:
            differences=three_way(state.baseline,source,target)
            source_only=[f for f,d in differences.items() if d['operation']=='SOURCE_ONLY']
            conflicts=[f for f,d in differences.items() if d['operation']=='CONFLICT']
            protected=(kind=='p' or entity.status=='PUBLISHED' or
                       any(f.split('/')[0] in ('composition','classification') for f in source_only))
            proposal=bool(source_only and protected)
            operation['status']='CONFLICT' if conflicts else 'PROPOSAL' if proposal else 'UPDATE' if source_only else 'SYNCED'
            operation['changes']={f:d for f,d in differences.items() if d['operation']!='UNCHANGED'}
            if conflicts:report['counts']['conflicts']+=1
            elif proposal:report['counts']['proposed']+=1
            elif source_only:report['counts']['updated']+=1
            else:report['counts']['synced']+=1
            if apply:
                if source_only and not protected and not conflicts:
                    for f in sorted({path.split('/')[0] for path in source_only}):
                        merged=apply_source_paths(target,source,[path for path in source_only if path.split('/')[0]==f])
                        if f=='technical_data':
                            # Preserve the legacy source locator needed by the academic
                            # provenance adapter when a technical value changes.
                            original=getattr(record,'technical_data') or {}
                            locator=original.get('legacy_source')
                            value=merged[f]
                            if locator:value['legacy_source']=locator
                            setattr(record,f,value)
                        else:
                            setattr(record,f,merged[f])
                if conflicts or proposal:
                    state.pending={f:d for f,d in differences.items() if d['operation'] in ('SOURCE_ONLY','CONFLICT')}
                    state.status='CONFLICT' if conflicts else 'PENDING'
                else:
                    # Accept source changes only when they were actually applied or already converged.
                    state.baseline=source
                    state.source_hash=fingerprint(source)
                    state.pending={}
                    state.status='SYNCED'
        report['operations'].append(operation)
    # File and row consistency are reported separately from content reconciliation.
    # Old, valid IFC bytes remain in place until an explicit backed-up metadata migration.
    from scripts.import_metra_demo import ifc_uris, get_asset_path
    from .consolidated_data import prior_storage_uris
    asset_rows={a.storage_key:a for a in db.scalars(select(Asset).where(Asset.file_type=='IFC'))}
    document_status={'checked':0,'missing_records':[],'missing_files':[],
                     'wrong_hash':[],'source_changed':[]}
    for kind,key,path,doc,item,source in source_entries(root):
        collection='generic_solutions' if kind=='g' else 'manufacturer_solutions'
        for uri in ifc_uris(item):
            old_uri=prior_storage_uris().get(key,{}).get(uri,uri)
            storage_key=stable_asset_key(collection,item['code'],old_uri)
            asset=asset_rows.get(storage_key)
            document_status['checked']+=1
            if asset is None:
                document_status['missing_records'].append(key)
                continue
            target=(store/storage_key).resolve()
            if target.parent!=store.resolve() or not target.is_file():
                document_status['missing_files'].append(key)
                continue
            if hashlib.sha256(target.read_bytes()).hexdigest()!=asset.sha256:
                document_status['wrong_hash'].append(key)
                continue
            original=get_asset_path(path,root,collection,uri)
            if original and hashlib.sha256(original.read_bytes()).hexdigest()!=asset.sha256:
                document_status['source_changed'].append(key)
    report['documents']=document_status
    # Never delete missing source entities. They may have editorial revisions and assets.
    for state in db.scalars(select(CatalogueSourceState)):
        if state.key not in seen:
            report['counts']['orphaned']+=1
            report['operations'].append({'code':state.key,'status':'ORPHANED','reason':'Preserved in PostgreSQL'})
            if apply:state.status='ORPHANED'
    return report
