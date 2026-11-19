"""Single command surface for the consolidated catalogue."""
import argparse
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.consolidate_data import BACKEND, GROUPS, digest, documents, pointer
from app.consolidated_data import academic_value
from app.data_templates import FAMILIES, fields_for

ROOT = BACKEND / 'data/metra-demo'
EVIDENCE = BACKEND / 'data/integrity'


def unescape(path):
    return [p.replace('~1','/').replace('~0','~') for p in path.lstrip('/').split('/')]


def read_pointer(value, path):
    for part in unescape(path):
        value = value[int(part)] if isinstance(value,list) else value[part]
    return value


def validate(root=ROOT, evidence=EVIDENCE):
    from app.canonical import property_value
    from app.inventory import inventory
    manifest = inventory()
    actual = {p.relative_to(root).as_posix(): sha256(p.read_bytes()).hexdigest()
              for p in root.rglob('*.ifc')}
    if actual != manifest['active_sha256']:
        raise ValueError('Diferencias en el inventario IFC activo')
    counts=Counter()
    seen={}
    references={}
    coverage={}
    pending=[]
    quantities={}
    for group,path,doc in documents(root):
        prefix='g' if group==GROUPS[0] else 'p'
        for row in doc[group]:
            code=row['code']
            key=f'{prefix}:{code}'
            subsystem=row.get('subsystem_code') or doc['catalogue']['subsystem']['code']
            if key in seen or subsystem not in FAMILIES:
                raise ValueError('Código duplicado o subsistema fuera del alcance: '+key)
            seen[key]=subsystem
            counts['generic' if prefix=='g' else 'commercial']+=1
            pending.extend((ref,subsystem) for ref in row.get('generic_solution_codes',[]))
            if not row.get('name_es') or not row.get('description') or not row.get('composition'):
                raise ValueError('Falta descripción o composición: '+key)
            for asset in row['assets']:
                if asset['format']=='IFC':
                    physical=(path.parent/asset['uri']).resolve()
                    if key in references or not physical.is_file():
                        raise ValueError('Referencia IFC inválida: '+key)
                    references[key]=physical.relative_to(root.resolve()).as_posix()
            stats=coverage.setdefault(subsystem,Counter())
            stats['solutions']+=1
            missing=[]
            for field in fields_for(subsystem):
                name=field['code']
                cell=row['technical_performance'][name]
                if cell['unit']!=field['unit']:
                    raise ValueError('Unidad de plantilla inválida: '+key+'/'+name)
                if cell['value'] is not None and property_value(field,cell)[1]!='PRESENT':
                    raise ValueError('Valor inválido: '+key+'/'+name)
                category=('missing' if cell['value'] is None else 'calculated' if cell.get('source_type')=='CALCULATED'
                          else 'estimated' if academic_value(prefix,code,pointer(('technical_performance',name,'value')),cell['value']) else 'declared')
                stats[category]+=1
                if category=='missing': missing.append(name)
            quantities[key]={'subsystem':subsystem,'missing':missing}
            cost=row['economic_data']['reference']
            env=row['environmental_data']['reference']
            assert cost['functional_unit']==env['functional_unit']==row['functional_unit']
            assert cost['subsystem']==env['subsystem']==subsystem
            assert cost['method']==env['method']=='METRA-REF-2026-01'
            assert all(line['quantity']>=0 and line['subtotal']>=0 for line in cost['items'])
            assert abs(sum(line['subtotal'] for line in cost['items'])-cost['total'])<.005
            assert [module['module'] for module in env['modules']]==['A1–A3','A4']
            assert abs(sum(module['value'] for module in env['modules'])-env['total'])<.0005
    if counts!=manifest['counts'] or references!=manifest['references']:
        raise ValueError('El inventario no coincide con el manifiesto activo')
    if any(seen.get('g:'+code)!=sub for code,sub in pending):
        raise ValueError('Relación genérica-comercial incompatible')
    return {'counts':dict(counts),'references':len(references),'archived_ifcs':0,
            'templates':len(FAMILIES),'coverage':coverage,'solutions':quantities}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['audit','dry-run','apply','validate','verify-assets'])
    args = parser.parse_args()
    report = validate()
    print(json.dumps(report,indent=2,ensure_ascii=False),flush=True)
    if args.action=='verify-assets' and os.getenv('DATABASE_URL'):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from ifc_inventory import audit
        engine = create_engine(os.environ['DATABASE_URL'],hide_parameters=True)
        with Session(engine) as db:
            counts, warnings, _ = audit(db,Path(os.getenv('ASSET_DIR','/data/assets')).resolve())
        print(json.dumps({'database_assets':counts,'issues':warnings},ensure_ascii=False,indent=2))
        if counts.get('integrity_ok')!=report['references'] or any(counts.get(key) for key in ('missing_link','incorrect_association','hash_mismatch')):
            raise SystemExit(1)
    if args.action=='apply':
        subprocess.run([sys.executable,str(BACKEND/'scripts/import_metra_demo.py'),'--apply'],check=True)


if __name__=='__main__':
    main()
