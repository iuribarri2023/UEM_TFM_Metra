"""Comparison service for the versioned Flask API."""

from .http_core import (
    CommercialSolution,
    GenericSolution,
    Revision,
    Subsystem,
    System,
    err,
    g,
    obj,
    pk,
    project,
    request,
)

from .solution_serializers import (
    serialize_generic,
    serialize_product,
)

def public_comparison_solution(kind, identity):
    """Return only public data; never inherit unpublished revisions or private document rights."""
    if kind == 'g':
        item = obj(GenericSolution, identity)
        if item.status != 'PUBLISHED':
            err('Solución no publicada', 'NOT_FOUND', 404)
        record = serialize_generic(item)
        title = record['name_es']
        unit = record['technical_data'].get('functional_unit')
        composition = record['composition']
        revision = None
        maker = None
    else:
        item = obj(CommercialSolution, identity)
        if item.availability != 'ACTIVE' or not item.published_revision_id:
            err('Producto no disponible', 'NOT_FOUND', 404)
        published = g.db.get(Revision, item.published_revision_id)
        if not published or published.status != 'APPROVED':
            err('Producto no publicado', 'NOT_FOUND', 404)
        record = serialize_product(item)
        rev = record['published']
        title = rev['name_es']
        unit = rev['functional_unit']
        composition = rev['technical_data'].get('composition', [])
        revision = rev['number']
        maker = record['manufacturer']['name']
    detail = record if kind == 'g' else rev
    sub = g.db.get(Subsystem, item.subsystem_id)
    system = g.db.get(System, sub.system_id) if sub else None
    return {
        'key': f'{kind}:{item.id}', 'id': str(item.id), 'kind': 'generic' if kind == 'g' else 'commercial',
        'name': title, 'code': item.code, 'manufacturer': maker,
        'subsystem_id': str(item.subsystem_id),
        'subsystem': sub.name_es if sub else None,
        'system_id': str(sub.system_id) if sub else None,
        'system': system.name_es if system else None,
        'functional_unit': unit, 'revision': revision,
        'status': record['status'] if kind == 'g' else rev['status'],
        'technical_data': detail['technical_data'], 'composition': composition,
        'economic_data': detail['economic_data'], 'environmental_data': detail['environmental_data'],
        'assets': detail['assets'], 'bim_status': detail['bim_status'],
        'canonical': project(g.db,item,detail,'generic' if kind=='g' else 'commercial'),
    }

def validate_comparison_context(solutions):
    a, b = solutions
    if not a['system_id'] or a['system_id'] != b['system_id'] or a['subsystem_id'] != b['subsystem_id']:
        err('Las soluciones deben pertenecer al mismo sistema y subsistema', 'INCOMPATIBLE_SUBSYSTEM', 422)
    for field in ('system_id','subsystem_id'):
        supplied = request.args.get(field)
        if supplied is not None and str(pk(supplied)) != a[field]:
            err('El contexto no corresponde a las soluciones seleccionadas', 'INCOMPATIBLE_SUBSYSTEM', 422)
