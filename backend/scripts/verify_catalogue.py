"""Verify a fresh installation using the active inventory and its rights manifest."""
import os
from pathlib import Path
import sys
from urllib.request import urlopen

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine,select
from sqlalchemy.orm import Session
from app.inventory import inventory
from app.models import CatalogueInitialization,CommercialSolution,GenericSolution,GenericAsset,RevisionAsset,Asset,DataTemplate,Subsystem,User
from app.data_templates import FAMILIES
from bootstrap_catalogue_demo import KEY
from boot_credentials import read_rights
from ifc_inventory import audit


def main():
    manifest=inventory()
    rights=read_rights(manifest)
    engine=create_engine(os.environ['DATABASE_URL'],hide_parameters=True)
    with Session(engine) as db:
        assert db.get(CatalogueInitialization,KEY)
        expected_admin=os.getenv('METRA_ADMIN_EMAIL','').lower()
        assert db.scalar(select(User.id).where(User.role=='ADMIN',User.active.is_(True),
                                              *([User.email==expected_admin] if expected_admin else [])))
        generics=list(db.scalars(select(GenericSolution).where(GenericSolution.status=='PUBLISHED')))
        products=list(db.scalars(select(CommercialSolution).where(CommercialSolution.availability=='ACTIVE',
                                                                  CommercialSolution.published_revision_id.is_not(None))))
        assert (len(generics),len(products))==(manifest['counts']['generic'],manifest['counts']['commercial'])
        active_templates=set(db.scalars(select(Subsystem.code).join(DataTemplate,DataTemplate.subsystem_id==Subsystem.id)
                                       .where(Subsystem.archived.is_(False))))
        assert set(FAMILIES)<=active_templates
        counts,warnings,_=audit(db,Path(os.getenv('ASSET_DIR','/data/assets')).resolve())
        assert counts['integrity_ok']==len(manifest['references']) and not warnings
        for item in [*generics,*products]:
            kind='g' if isinstance(item,GenericSolution) else 'p'
            model=GenericAsset if kind=='g' else RevisionAsset
            owner=model.generic_id if kind=='g' else model.revision_id
            owner_id=item.id if kind=='g' else item.published_revision_id
            rule=rights.get(f'{kind}:{item.code}')
            for link,asset in db.execute(select(model,Asset).join(Asset,Asset.id==model.asset_id).where(owner==owner_id)):
                assert link.public_view_allowed==bool(rule and rule['sha256']==asset.sha256 and rule['view'])
                assert link.public_download_allowed==bool(rule and rule['sha256']==asset.sha256 and rule['download'])
    for url in (os.getenv('METRA_HEALTH_URL','http://backend:8000/health'),
                os.getenv('METRA_FRONTEND_URL','http://frontend/')):
        with urlopen(url,timeout=10) as response:
            assert response.status==200 and response.read(200)
    print('Administrador, catálogo, plantillas, originales, permisos y HTTP correctos.')


if __name__=='__main__':
    main()
