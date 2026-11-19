"""Read-only operational readiness, separate from process and database liveness."""
import hashlib
from pathlib import Path
from sqlalchemy import func, select

from .inventory import inventory
from .data_templates import FAMILIES
from .models import Asset, CatalogueSourceState, CommercialSolution, DataTemplate, GenericSolution, Revision, Subsystem


def report(db, store):
    manifest=inventory()
    expected=manifest['counts']
    generic=db.scalar(select(func.count()).select_from(GenericSolution))
    commercial=db.scalar(select(func.count()).select_from(CommercialSolution))
    public_generic=db.scalar(select(func.count()).select_from(GenericSolution).where(GenericSolution.status=='PUBLISHED'))
    public_commercial=db.scalar(select(func.count()).select_from(CommercialSolution).where(
        CommercialSolution.availability=='ACTIVE',CommercialSolution.published_revision_id.is_not(None)))
    templates=db.scalar(select(func.count(func.distinct(Subsystem.id))).select_from(Subsystem)
        .join(DataTemplate,DataTemplate.subsystem_id==Subsystem.id).where(Subsystem.archived.is_(False)))
    states={key:db.scalar(select(func.count()).select_from(CatalogueSourceState).where(
        CatalogueSourceState.status==key)) for key in ('CONFLICT','PENDING','UNBASELINED')}
    pending_reviews=db.scalar(select(func.count()).select_from(Revision).where(Revision.status=='SUBMITTED'))
    root=Path(store).resolve()
    missing=invalid=0
    for asset in db.scalars(select(Asset).where(Asset.file_type=='IFC')):
        path=root/asset.storage_key
        if path.is_symlink() or path.resolve().parent!=root:
            invalid+=1
        elif not path.is_file():
            missing+=1
        else:
            digest=hashlib.sha256()
            with path.open('rb') as source:
                for block in iter(lambda:source.read(1024*1024),b''):digest.update(block)
            if digest.hexdigest()!=asset.sha256:invalid+=1
    blocked=bool(missing or invalid or templates<len(FAMILIES))
    degraded=bool(sum(states.values()) or pending_reviews or generic!=expected['generic'] or commercial!=expected['commercial']
                  or public_generic<expected['generic'] or public_commercial<expected['commercial']
                  or generic+commercial>db.scalar(select(func.count()).select_from(CatalogueSourceState)))
    return {
        'state':'BLOCKED' if blocked else 'DEGRADED' if degraded else 'HEALTHY',
        'schema_ready':True,
        'catalogue':{'expected':expected,'imported':{'generic':generic,'commercial':commercial},
                     'public':{'generic':public_generic,'commercial':public_commercial}},
        'data_templates':{'expected':len(FAMILIES),'installed_subsystems':templates},
        'ifc':{'missing':missing,'invalid_hash_or_path':invalid},
        'reconciliation':{'conflicts':states['CONFLICT'],'pending_proposals':states['PENDING'],
                          'missing_baselines':states['UNBASELINED'],'pending_reviews':pending_reviews},
    }
