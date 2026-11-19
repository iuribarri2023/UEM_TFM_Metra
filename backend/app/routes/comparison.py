"""Versioned HTTP endpoints for comparison."""
from ..api_support import (
    CommercialSolution,
    Revision,
    api,
    data,
    err,
    g,
    obj,
    parse_pair,
    public_comparison_solution,
    request,
    serialize_product,
    validate_comparison_context,
    warnings_for,
)


@api.get('/solutions/compare')
def solutions_compare():
    try:
        selections = parse_pair(request.args.get('ids', ''))
    except ValueError as exc:
        err(str(exc), 'VALIDATION', 422)
    solutions = [public_comparison_solution(kind, identity) for kind, identity in selections]
    validate_comparison_context(solutions)
    return data({'solutions': solutions, 'warnings': warnings_for(solutions),
                 'same_subsystem': solutions[0]['subsystem_id'] == solutions[1]['subsystem_id'],
                 'same_functional_unit': bool(solutions[0]['functional_unit']) and
                       solutions[0]['functional_unit'] == solutions[1]['functional_unit']})



@api.get('/products/compare')
def compare():
    """Backward compatible product-only endpoint, now always limited to exactly two."""
    try:
        selections = parse_pair(request.args.get('ids', ''))
    except ValueError as exc:
        err(str(exc), 'VALIDATION', 422)
    if any(kind != 'p' for kind, _ in selections):
        err('Esta ruta admite únicamente productos comerciales', 'VALIDATION', 422)
    xs = [obj(CommercialSolution, identity) for _, identity in selections]
    if any(p.availability != 'ACTIVE' or not p.published_revision_id for p in xs):
        err('Producto no disponible', 'NOT_FOUND', 404)
    rr = [g.db.get(Revision, p.published_revision_id) for p in xs]
    if any(not r or r.status != 'APPROVED' for r in rr):
        err('Producto no publicado', 'NOT_FOUND', 404)
    unit = rr[0].functional_unit if rr[0].functional_unit == rr[1].functional_unit else None
    solutions = [public_comparison_solution('p', p.id) for p in xs]
    validate_comparison_context(solutions)
    return data({'functional_unit': unit, 'products': [serialize_product(p) for p in xs],
                 'warnings': warnings_for(solutions)})

