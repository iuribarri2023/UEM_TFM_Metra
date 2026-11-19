"""Versioned HTTP endpoints for catalogue."""
import math
from ..consolidated_data import runtime_technical

from ..catalogue import catalogue_highlights, current_template, property_matches
from ..api_support import (
    Archetype,
    CommercialSolution,
    GenericAsset,
    GenericSolution,
    Manufacturer,
    Revision,
    RevisionAsset,
    RevisionGeneric,
    Subsystem,
    System,
    api,
    catalogue_filters,
    catalogue_generics,
    catalogue_order,
    catalogue_products,
    data,
    err,
    fields,
    func,
    g,
    obj,
    page_query,
    pk,
    project,
    public_query,
    request,
    select,
    serialize_generic,
    serialize_product,
    serialize_tax,
)


def filter_template_property(query, identity, technical, code_column, kind):
    code = request.args.get('property')
    if not code:
        return query
    subsystem = request.args.get('subsystem_id')
    if not subsystem:
        err('Selecciona un subsistema para filtrar una propiedad', 'VALIDATION', 422)
    sub = obj(Subsystem, subsystem)
    field = next((item for item in current_template(g.db, sub)['fields']
                  if item['code'] == code and item.get('type') == 'number'), None)
    if field is None:
        err('La propiedad numérica no pertenece a la plantilla', 'UNKNOWN_TEMPLATE_PROPERTY', 422)
    try:
        minimum = float(request.args['minimum']) if 'minimum' in request.args else None
        maximum = float(request.args['maximum']) if 'maximum' in request.args else None
        if any(value is not None and not math.isfinite(value) for value in (minimum, maximum)):
            raise ValueError
        if minimum is not None and maximum is not None and minimum > maximum:
            raise ValueError
    except ValueError:
        err('Intervalo de propiedad inválido', 'VALIDATION', 422)
    candidates = query.with_only_columns(identity, technical, code_column, maintain_column_froms=True)
    matches = [item_id for item_id, payload, item_code in g.db.execute(candidates)
               if property_matches(runtime_technical(payload,kind,item_code), field, minimum, maximum)]
    return query.where(identity.in_(matches))


@api.get('/systems')
def systems():
    q=select(System).where(System.archived==False).order_by(System.code)
    xs,meta=page_query(q);return data([serialize_tax(x) for x in xs],meta)



@api.get('/subsystems')
def subsystems():
    q=select(Subsystem).where(Subsystem.archived==False)
    if request.args.get('system_id'):q=q.where(Subsystem.system_id==pk(request.args['system_id']))
    xs,meta=page_query(q.order_by(Subsystem.code));return data([serialize_tax(x) for x in xs],meta)



@api.get('/archetypes')
def archetypes():
    q=select(Archetype).where(Archetype.archived==False)
    if request.args.get('subsystem_id'):q=q.where(Archetype.subsystem_id==pk(request.args['subsystem_id']))
    xs,meta=page_query(q.order_by(Archetype.code));return data([serialize_tax(x) for x in xs],meta)



@api.get('/generic-solutions')
def generics():
    q=select(GenericSolution).where(GenericSolution.status=='PUBLISHED')
    if request.args.get('subsystem_id'):q=q.where(GenericSolution.subsystem_id==pk(request.args['subsystem_id']))
    if request.args.get('archetype_id'):q=q.where(GenericSolution.archetype_id==pk(request.args['archetype_id']))
    if request.args.get('unit'):q=q.where(GenericSolution.technical_data['functional_unit'].astext==request.args['unit'])
    q = catalogue_filters(q, GenericSolution, GenericAsset, GenericAsset.generic_id,
                          GenericSolution.id, GenericSolution.name_es)
    q = filter_template_property(q, GenericSolution.id, GenericSolution.technical_data, GenericSolution.code, 'g')
    xs, meta = page_query(catalogue_order(q, GenericSolution.name_es, GenericSolution.code))
    result = catalogue_generics(xs)
    return data(catalogue_highlights(g.db, result) if request.args.get('template_summary') == '1' else result, meta)



@api.get('/generic-solutions/<id>')
def generic_detail(id):
    x=obj(GenericSolution,id)
    if x.status!='PUBLISHED':err('Recurso no encontrado','NOT_FOUND',404)
    value=serialize_generic(x)
    value['canonical']=project(g.db,x,value,'generic')
    return data(value)



@api.get('/manufacturers')
def manufacturers():
    if request.args.get('scope') == 'catalogue':
        visible = (public_query().where(CommercialSolution.manufacturer_id == Manufacturer.id)
                   .with_only_columns(CommercialSolution.id).correlate(Manufacturer))
        rows, meta = page_query(select(Manufacturer).where(visible.exists()).order_by(Manufacturer.name, Manufacturer.id))
        return data([fields(row, ['id', 'name']) for row in rows], meta)
    q=select(Manufacturer).where(Manufacturer.status=='ACTIVE',Manufacturer.contact_public==True).order_by(Manufacturer.name)
    xs,meta=page_query(q)
    return data([fields(x,['id','name','description','website','public_email']) for x in xs],meta)



@api.get('/manufacturers/<id>')
def manufacturer_detail(id):
    m=obj(Manufacturer,id)
    if m.status!='ACTIVE' or not m.contact_public:err('No encontrado','NOT_FOUND',404)
    f=['id','name','description']+(['website','public_email'] if m.contact_public else [])
    return data(fields(m,f))



@api.get('/catalogue/counts')
def catalogue_counts():
    generic_counts = select(GenericSolution.subsystem_id, func.count()).where(
        GenericSolution.status == 'PUBLISHED').group_by(GenericSolution.subsystem_id)
    product_counts = (public_query()
        .with_only_columns(CommercialSolution.subsystem_id, func.count())
        .group_by(CommercialSolution.subsystem_id))
    return data({
        'generics': {str(key): count for key, count in g.db.execute(generic_counts)},
        'products': {str(key): count for key, count in g.db.execute(product_counts)},
    })



@api.get('/products')
def products():
    q=public_query()
    if request.args.get('subsystem_id'):q=q.where(CommercialSolution.subsystem_id==pk(request.args['subsystem_id']))
    if request.args.get('manufacturer_id'):q=q.where(CommercialSolution.manufacturer_id==pk(request.args['manufacturer_id']))
    if request.args.get('archetype_id'):
        linked = select(RevisionGeneric.revision_id).join(GenericSolution).where(
            RevisionGeneric.revision_id==Revision.id, GenericSolution.status=='PUBLISHED',
            GenericSolution.archetype_id==pk(request.args['archetype_id']))
        q=q.where(linked.exists())
    if request.args.get('unit'):q=q.where(Revision.functional_unit==request.args['unit'])
    q = catalogue_filters(q, CommercialSolution, RevisionAsset, RevisionAsset.revision_id,
                          Revision.id, Revision.name_es)
    q = filter_template_property(q, CommercialSolution.id, Revision.technical_data, CommercialSolution.code, 'p')
    xs, meta = page_query(catalogue_order(q, Revision.name_es, CommercialSolution.code))
    result = catalogue_products(xs)
    return data(catalogue_highlights(g.db, result, commercial=True) if request.args.get('template_summary') == '1' else result, meta)



@api.get('/products/<id>')
def product_detail(id):
    p=obj(CommercialSolution,id)
    revision=g.db.get(Revision,p.published_revision_id) if p.published_revision_id else None
    if p.availability!='ACTIVE' or not revision or revision.status!='APPROVED':
        err('No encontrado','NOT_FOUND',404)
    value=serialize_product(p)
    value['published']['canonical'] = project(g.db, p, value['published'], 'commercial')
    return data(value)

