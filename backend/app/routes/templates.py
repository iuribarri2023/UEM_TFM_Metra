"""Versioned HTTP endpoints for templates."""
from ..api_support import (
    DataTemplate,
    Subsystem,
    TemplateDTO,
    api,
    audit,
    current_template,
    data,
    dto,
    err,
    fields,
    g,
    obj,
    page_query,
    quality_report,
    request,
    role,
    select,
)


@api.get('/data-templates/<subsystem_code>')
def template_public(subsystem_code):
    sub=g.db.scalar(select(Subsystem).where(Subsystem.code==subsystem_code,Subsystem.archived==False))
    if not sub:err('No encontrado','NOT_FOUND',404)
    raw_version = request.args.get('version')
    version = request.args.get('version', type=int)
    if raw_version is not None and (version is None or version < 1):
        err('Versión de plantilla inválida', 'VALIDATION', 422)
    template = current_template(g.db, sub, version)
    if template is None:
        err('Versión de plantilla no encontrada', 'NOT_FOUND', 404)
    return data(template)



@api.get('/admin/data-quality')
@role('ADMIN')
def admin_data_quality():
    return data(quality_report(g.db, include_entries=request.args.get('entries') == '1'))



@api.get('/admin/templates/<subsystem_code>/versions')
@role('ADMIN')
def admin_template_versions(subsystem_code):
    sub = g.db.scalar(select(Subsystem).where(Subsystem.code == subsystem_code))
    if not sub:
        err('Subsistema no encontrado', 'NOT_FOUND', 404)
    rows, meta = page_query(select(DataTemplate).where(DataTemplate.subsystem_id == sub.id)
                            .order_by(DataTemplate.version.desc()))
    return data([fields(row, ['id','version','fields']) for row in rows], meta)



@api.post('/admin/templates')
@role('ADMIN')
def create_template():
    b=dto(TemplateDTO);sub=obj(Subsystem,b.subsystem_id,True)
    previous = g.db.scalar(select(DataTemplate).where(DataTemplate.subsystem_id==sub.id)
                           .order_by(DataTemplate.version.desc()).limit(1))
    incoming = {field['code']: field for field in b.fields}
    for field in previous.fields if previous else []:
        candidate = incoming.get(field['code'])
        if candidate is None or any(candidate.get(key) != field.get(key) for key in ('type','unit')):
            err('Conserva el código, tipo y unidad de campos existentes. Añade un código para una magnitud diferente.',
                'INCOMPATIBLE_TEMPLATE_VERSION',422)
        # Keep aliases and semantic metadata unless explicitly replaced.
        for key in ('aliases','canonical_unit','value_type','contract_version','comparison_policy'):
            if key in field and key in candidate and candidate[key] != field[key]:
                err('La semántica de un código existente no puede modificarse', 'INCOMPATIBLE_TEMPLATE_VERSION',422)
        incoming[field['code']] = {**field, **candidate}
    if request.args.get('preview') == '1':
        return data({'next_version': (previous.version if previous else 0)+1, 'fields': list(incoming.values())})
    x=DataTemplate(subsystem_id=sub.id,version=(previous.version if previous else 0)+1,fields=list(incoming.values()))
    g.db.add(x);g.db.flush();audit('TEMPLATE_VERSION','template',x.id)
    return data(fields(x,['id','version','fields']),status=201)

