"""Seed only metra_publication_test for the real browser IFC test."""
import hashlib
import os
import sys
from pathlib import Path
from sqlalchemy import create_engine,select
from sqlalchemy.orm import Session

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.models import Base,System,Subsystem,Archetype,GenericSolution,GenericAsset,Asset,Extraction,Manufacturer,CommercialSolution,Revision,RevisionAsset,User,DataTemplate
from app.data_templates import fields_for
from app.parsers import parse_ifc
from app.security import ph

def main():
    url=os.environ['DATABASE_URL']
    if os.getenv('METRA_TEST_DB')!='1' or not url.rsplit('/',1)[-1]=='metra_publication_test':
        raise SystemExit('Solo se permite metra_publication_test con METRA_TEST_DB=1')
    engine=create_engine(url,hide_parameters=True)
    Base.metadata.create_all(engine)
    source=Path(__file__).resolve().parents[1]/'tests/fixtures/panel_demo.ifc'
    content=source.read_bytes();normalized=parse_ifc(content)
    store=Path(os.environ['ASSET_DIR']);store.mkdir(parents=True,exist_ok=True)
    with Session(engine) as db:
        if db.scalar(select(GenericSolution.id).where(GenericSolution.code=='E2E.IFC.GS001')):
            sub=db.scalar(select(Subsystem).where(Subsystem.code=='E2E.PAN'))
            if sub and not db.scalar(select(DataTemplate.id).where(DataTemplate.subsystem_id==sub.id)):
                db.add(DataTemplate(subsystem_id=sub.id,version=1,fields=fields_for(sub.code)))
                db.commit()
            if not db.scalar(select(User.id).where(User.email=='ifc-e2e@example.com')):
                db.add(User(email='ifc-e2e@example.com',password_hash=ph.hash('IfcE2ePassword_1234'),role='ADMIN'))
                db.commit()
            print('IFC E2E fixtures already present');return
        user=User(email='ifc-e2e@example.com',password_hash=ph.hash('IfcE2ePassword_1234'),role='ADMIN')
        system=System(code='E2E',name_es='Ensayo IFC');db.add_all([user,system]);db.flush()
        sub=Subsystem(code='E2E.PAN',name_es='Panel de ensayo',system_id=system.id);db.add(sub);db.flush()
        db.add(DataTemplate(subsystem_id=sub.id,version=1,fields=fields_for(sub.code)))
        arch=Archetype(code='E2E.PAN.IFC',name_es='Panel IFC',subsystem_id=sub.id);db.add(arch);db.flush()
        generic=GenericSolution(code='E2E.IFC.GS001',name_es='Panel IFC público de ensayo',subsystem_id=sub.id,
            archetype_id=arch.id,status='PUBLISHED',technical_data={'properties':{'sample':True}})
        maker=Manufacturer(code='E2E-ORG',name='Fabricante de ensayo')
        db.add_all([generic,maker]);db.flush()
        product=CommercialSolution(code='E2E.IFC.P001',manufacturer_id=maker.id,subsystem_id=sub.id,availability='ACTIVE')
        db.add(product);db.flush()
        revision=Revision(product_id=product.id,number=1,status='APPROVED',name_es='Producto IFC de ensayo',created_by=user.id,
            technical_data={'properties':{'sample':True}},economic_data={'test':1},environmental_data={'test':2})
        db.add(revision);db.flush();product.published_revision_id=revision.id
        pending=Revision(product_id=product.id,number=2,status='SUBMITTED',name_es='Revisión IFC de ensayo',
            created_by=user.id,technical_data={'properties':{'sample':True}})
        db.add(pending);db.flush()
        for key,view in [('e2e-generic.ifc',True),('e2e-generic-second.ifc',True),('e2e-commercial.ifc',False)]:
            (store/key).write_bytes(content)
            asset=Asset(storage_key=key,original_name=key,file_type='IFC',size=len(content),sha256=hashlib.sha256(content).hexdigest(),processing_status='VALID')
            db.add(asset);db.flush()
            db.add(Extraction(asset_id=asset.id,schema_version=normalized['schema_version'],source_format='IFC',normalized=normalized,warnings=normalized['warnings'],is_valid=True))
            if view:db.add(GenericAsset(generic_id=generic.id,asset_id=asset.id,public_view_allowed=True,public_download_allowed=False))
            else:
                db.add(RevisionAsset(revision_id=revision.id,asset_id=asset.id))
                db.add(RevisionAsset(revision_id=pending.id,asset_id=asset.id))
        db.commit()
    print('IFC E2E fixtures ready')

if __name__=='__main__':main()
