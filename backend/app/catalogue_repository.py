"""Catalogue repository for the versioned Flask API."""

from .http_core import (
    Asset,
    CommercialSolution,
    GenericAsset,
    GenericSlot,
    Manufacturer,
    Revision,
    RevisionAsset,
    RevisionGeneric,
    Subsystem,
    defaultdict,
    err,
    func,
    g,
    or_,
    pk,
    request,
    select,
)

from .solution_serializers import (
    serialize_generic,
    serialize_product,
)

def catalogue_assets(link_model, association, ids):
    grouped=defaultdict(list)
    rows=g.db.execute(select(association,Asset,link_model).select_from(Asset).join(link_model,Asset.id==link_model.asset_id)
                      .where(association.in_(ids)).order_by(Asset.id))
    for target,asset,policy in rows:
        grouped[target].append((asset,policy))
    return grouped

def catalogue_generics(rows):
    if not rows:return []
    ids=[item.id for item in rows]
    slots=defaultdict(list)
    for slot in g.db.scalars(select(GenericSlot).where(GenericSlot.generic_solution_id.in_(ids),GenericSlot.archived==False)
                             .order_by(GenericSlot.slot_order,GenericSlot.id)):
        slots[slot.generic_solution_id].append(slot)
    linked=catalogue_assets(GenericAsset,GenericAsset.generic_id,ids)
    return [serialize_generic(item,catalogue=(slots[item.id],linked[item.id])) for item in rows]

def catalogue_products(rows):
    if not rows:return []
    revision_ids={item.published_revision_id for item in rows}
    manufacturers={item.id:item for item in g.db.scalars(
        select(Manufacturer).where(Manufacturer.id.in_({row.manufacturer_id for row in rows})))}
    revisions={item.id:item for item in g.db.scalars(select(Revision).where(Revision.id.in_(revision_ids)))}
    linked=catalogue_assets(RevisionAsset,RevisionAsset.revision_id,revision_ids)
    generics=defaultdict(list)
    for revision,generic in g.db.execute(select(RevisionGeneric.revision_id,RevisionGeneric.generic_id)
                                        .where(RevisionGeneric.revision_id.in_(revision_ids)).order_by(RevisionGeneric.generic_id)):
        generics[revision].append(generic)
    return [serialize_product(row,catalogue=(manufacturers[row.manufacturer_id],revisions.get(row.published_revision_id),
            (generics[row.published_revision_id],linked[row.published_revision_id]))) for row in rows]

def catalogue_order(query, name, code):
    sort = request.args.get('sort', 'code')
    if sort == 'name':
        return query.order_by(func.lower(name), code)
    if sort != 'code':
        err('Orden no admitido', 'VALIDATION', 422)
    return query.order_by(code)

def catalogue_filters(query, model, link, link_id, target_id, name):
    if request.args.get('system_id'):
        query = query.where(model.subsystem_id.in_(select(Subsystem.id).where(
            Subsystem.system_id == pk(request.args['system_id']))))
    term = request.args.get('q', '').strip()[:150]
    if term:
        query = query.where(or_(name.icontains(term, autoescape=True),
                                model.code.icontains(term, autoescape=True)))
    for file_type in ('IFC', 'BC3', 'EPD'):
        if request.args.get(file_type.lower()) == '1':
            visible = select(link.asset_id).join(Asset, Asset.id == link.asset_id).where(
                link_id == target_id, Asset.file_type == file_type,
                Asset.processing_status == 'VALID',
                or_(link.public_view_allowed, link.public_download_allowed))
            query = query.where(visible.exists())
    return query

def public_query():
    return select(CommercialSolution).join(Revision,CommercialSolution.published_revision_id==Revision.id).where(
      CommercialSolution.availability=='ACTIVE',Revision.status=='APPROVED')
