"""Solution serializers for the versioned Flask API."""

from .consolidated_data import historical_academic, runtime_domain, runtime_technical
from .asset_service import (
    bim_status,
    serialize_asset,
)

from .http_core import (
    Asset,
    GenericAsset,
    GenericSlot,
    Manufacturer,
    Revision,
    RevisionAsset,
    RevisionGeneric,
    RevisionOrigin,
    fields,
    g,
    select,
)

def serialize_tax(x):return fields(x,['id','code','name_es','archived']+[{'subsystems':'system_id','archetypes':'subsystem_id'}.get(x.__tablename__)] if x.__tablename__ in ('subsystems','archetypes') else ['id','code','name_es','archived'])

def serialize_generic(x,private=False,include_extraction=True,*,catalogue=None):
    v=fields(x,['id','code','name_es','archetype_id','subsystem_id','status','technical_data','environmental_data','economic_data','composition'])
    if catalogue is None:
        slots=g.db.scalars(select(GenericSlot).where(GenericSlot.generic_solution_id==x.id,GenericSlot.archived==False).order_by(GenericSlot.slot_order))
        linked=list(g.db.execute(select(Asset,GenericAsset).join(GenericAsset,GenericAsset.asset_id==Asset.id).where(GenericAsset.generic_id==x.id)))
    else:
        slots,linked=catalogue
    v['slots']=[fields(slot,['id','code','name_es','required','slot_order','properties']) for slot in slots]
    v['bim_status']=bim_status(linked,verify=catalogue is None)
    v['assets']=[serialize_asset(a,link,include_extraction,catalogue=catalogue is not None) for a,link in linked if private or (x.status=='PUBLISHED' and (link.public_view_allowed or link.public_download_allowed))]
    if not private:
        v['technical_data'] = public_technical(runtime_technical(v['technical_data'], 'g', x.code))
        archived = historical_academic(x.technical_data,'g',x.code)
        for domain in ('economic_data','environmental_data'):
            v[domain] = runtime_domain(v[domain],archived,domain,'g',x.code)
    return v

def public_technical(value):
    return {k: v for k, v in value.items()
            if k not in {'legacy_payload','legacy_source','publication_rights','viva_metrics','source_references'}}

def serialize_revision(rev,private=False,include_extraction=True,*,catalogue=None,code=''):
    x=fields(rev,['id','product_id','number','status','name_es','description','commercial_reference',
      'functional_unit','template_version','technical_data','economic_data','environmental_data','discrepancies','rejection_reason'])
    if private:
        x['created_at']=rev.created_at.isoformat()
        x['created_by']=str(rev.created_by) if rev.created_by else None
        origin=g.db.get(RevisionOrigin,rev.id)
        x['parent_id']=str(origin.parent_id) if origin else None
        x['message']=origin.message if origin else None
    if not private:
        x['technical_data']=public_technical(runtime_technical(x['technical_data'], 'p', code))
        archived = historical_academic(rev.technical_data,'p',code)
        for domain in ('economic_data','environmental_data'):
            x[domain] = runtime_domain(x[domain],archived,domain,'p',code)
    if catalogue is None:
        generics=g.db.scalars(select(RevisionGeneric.generic_id).where(RevisionGeneric.revision_id==rev.id))
        linked=list(g.db.execute(select(Asset,RevisionAsset).join(RevisionAsset,RevisionAsset.asset_id==Asset.id).where(RevisionAsset.revision_id==rev.id)))
    else:
        generics,linked=catalogue
    x['generic_solution_ids']=[str(item) for item in generics]
    x['bim_status']=bim_status(linked,verify=catalogue is None)
    x['assets']=[serialize_asset(a,link,include_extraction,catalogue=catalogue is not None,product_id=rev.product_id) for a,link in linked if private or (link.public_view_allowed or link.public_download_allowed)]
    return x

def serialize_product(product,private=False,include_extraction=True,*,catalogue=None):
    x=fields(product,['id','code','subsystem_id','manufacturer_id','availability','published_revision_id'])
    if catalogue is None:
        manufacturer=g.db.get(Manufacturer,product.manufacturer_id)
        r=g.db.get(Revision,product.published_revision_id) if product.published_revision_id else None
        related=None
    else:
        manufacturer,r,related=catalogue
    x['manufacturer']=fields(manufacturer,['id','name'])
    if manufacturer.contact_public:x['manufacturer'].update(website=manufacturer.website,public_email=manufacturer.public_email)
    x['published']=serialize_revision(r,private,include_extraction,catalogue=related,code=product.code) if r else None
    if private:
        x['revisions']=[serialize_revision(r,True,include_extraction) for r in g.db.scalars(select(Revision).where(Revision.product_id==product.id).order_by(Revision.number.desc()))]
    return x
