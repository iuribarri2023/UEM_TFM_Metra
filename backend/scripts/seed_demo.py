# CLI imports the backend package independently of the invocation CWD.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0,str(_Path(__file__).resolve().parents[1]))
"""Synthetic demonstration: taxonomy and editable data templates only.

Optional synthetic public IFC. No external manufacturer credentials or EPDs.
"""
import os
import argparse
import hashlib
from pathlib import Path
from uuid import uuid4
from sqlalchemy import create_engine,select
from sqlalchemy.orm import Session
from app.models import System,Subsystem,Archetype,GenericSolution,DataTemplate,Asset,GenericAsset,Extraction

def get(s,cls,code,**kwargs):
    x=s.scalar(select(cls).where(cls.code==code))
    if x:return x
    x=cls(code=code,**kwargs);s.add(x);s.flush();return x

def publish_demo(s):
    from app.parsers import parse_ifc
    system=get(s,System,'DEMO',name_es='Ejemplos de ensayo')
    subsystem=get(s,Subsystem,'DEMO.PAN',name_es='Paneles de ensayo',system_id=system.id)
    archetype=get(s,Archetype,'DEMO.PAN.SIN',name_es='Panel sintético',subsystem_id=subsystem.id)
    item=get(s,GenericSolution,'DEMO.PAN.SIN.GS001',name_es='Panel BIM de ensayo',
             archetype_id=archetype.id,subsystem_id=subsystem.id,status='DRAFT',
             technical_data={'properties':{'Espesor':{'value':200,'unit':'mm'}},
                             'functional_unit':'m2','demo':True})
    if item.status!='DRAFT' or s.scalar(select(GenericAsset).where(GenericAsset.generic_id==item.id)):
        return
    source=Path(__file__).resolve().parents[1]/'tests/fixtures/panel_demo.ifc'
    raw=source.read_bytes()
    result=parse_ifc(raw)
    store=Path(os.environ.get('ASSET_DIR','/data/assets'))
    store.mkdir(parents=True,exist_ok=True)
    key=uuid4().hex+'.ifc'
    path=store/key
    with path.open('xb') as stream:
        stream.write(raw)
    try:
        asset=Asset(original_name=source.name,storage_key=key,file_type='IFC',
                    sha256=hashlib.sha256(raw).hexdigest(),size=len(raw),processing_status='VALID')
        s.add(asset)
        s.flush()
        s.add(Extraction(asset_id=asset.id,schema_version=result['schema_version'],source_format='IFC',
                         normalized=result,warnings=result['warnings'],is_valid=True))
        s.add(GenericAsset(generic_id=item.id,asset_id=asset.id,public_view_allowed=True,public_download_allowed=True))
        item.status='PUBLISHED'
        s.commit()
    except Exception:
        path.unlink(missing_ok=True)
        raise


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--public-demo',action='store_true',help='Publica un IFC sintético generado para el proyecto')
    options=parser.parse_args()
    with Session(create_engine(os.environ['DATABASE_URL'])) as s:
        definitions=[('STR','Estructuras','STR.WAL','Muros estructurales','STR.WAL.CON','Muros de hormigón'),
          ('ENV','Envolventes','ENV.FAC','Fachadas','ENV.FAC.PANEL','Paneles industrializados'),
          ('INT','Interiores','INT.PAR','Particiones','INT.PAR.MOD','Paneles interiores')]
        for code,name,sc,sname,ac,aname in definitions:
            system=get(s,System,code,name_es=name)
            subsystem=get(s,Subsystem,sc,name_es=sname,system_id=system.id)
            archetype=get(s,Archetype,ac,name_es=aname,subsystem_id=subsystem.id)
            get(s,GenericSolution,ac+'.GS001',name_es='Referencia sintética · '+aname,archetype_id=archetype.id,subsystem_id=subsystem.id,status='DRAFT',
              technical_data={'schema_version':'1.0','demo':True,'note':'Sin IFC publicado; cargar IFC válido y publicar como admin'})
            if not s.scalar(select(DataTemplate).where(DataTemplate.subsystem_id==subsystem.id)):
                s.add(DataTemplate(subsystem_id=subsystem.id,version=1,fields=[
                  {'code':'espesor','label':'Espesor','required':True,'type':'number','unit':'mm','min':1,'max':3000},
                  {'code':'peso','label':'Peso superficial','required':True,'type':'number','unit':'kg','min':0}]))
        s.commit()
        if options.public_demo:
            publish_demo(s)
    print('Seed sintético idempotente creado; referencias genéricas DRAFT hasta validación IFC')
if __name__=='__main__':main()
