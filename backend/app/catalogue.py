"""Resolve templates and canonical projections from live source records."""
from sqlalchemy import select
from uuid import UUID
from .canonical import canonical_solution
from .data_templates import fields_for, template_view
from .models import Archetype, DataTemplate, Subsystem, System


class TemplateProjectionIntegrityError(ValueError):
    """The stored revision cannot be represented by an available contract."""


def revision_template(db, subsystem, requested):
    if requested is None:
        raise TemplateProjectionIntegrityError('Commercial revision has no template version')
    exact=current_template(db,subsystem,requested)
    if exact is not None:
        return exact,None
    latest=db.scalar(select(DataTemplate).where(DataTemplate.subsystem_id==subsystem.id)
                     .order_by(DataTemplate.version.desc()).limit(1))
    if latest is None:
        raise TemplateProjectionIntegrityError('No Data Template is available for the subsystem')
    template=template_view(subsystem.code,subsystem.id,latest.version,latest.fields)
    warning={'code':'HISTORICAL_TEMPLATE_FALLBACK','requested_version':requested,
             'effective_version':latest.version,'subsystem_code':subsystem.code}
    return template,warning


def _validated_projection(record,kind,code,classification,template,warning):
    result=canonical_solution(record,kind=kind,code=code,classification=classification,template=template)
    if warning:
        invalid=[issue for issue in result['quality']['issues'] if issue['status'] not in ('MISSING',)]
        if invalid:
            raise TemplateProjectionIntegrityError(f'Fallback template rejects projected values: {invalid}')
        result['quality']['warnings']=[warning]
        result['traceability']['effective_template_version']=template['version']
    return result


def current_template(db, subsystem, version=None):
    query = select(DataTemplate).where(DataTemplate.subsystem_id == subsystem.id)
    if version is not None:
        query = query.where(DataTemplate.version == version)
    stored = db.scalar(query.order_by(DataTemplate.version.desc()).limit(1))
    if stored is None and version is not None:
        return None
    return template_view(subsystem.code, subsystem.id, stored.version if stored else 0,
                         stored.fields if stored else fields_for(subsystem.code))


def project(db, item, record, kind):
    sub = db.get(Subsystem, item.subsystem_id)
    system = db.get(System, sub.system_id)
    archetype = db.get(Archetype, item.archetype_id) if kind == 'generic' else None
    classification = {'system_code': system.code, 'subsystem_code': sub.code,
                      'system_id': str(system.id), 'subsystem_id': str(sub.id),
                      'archetype_code': archetype.code if archetype else None}
    template,warning=(revision_template(db,sub,record.get('template_version')) if kind=='commercial'
                      else (current_template(db,sub),None))
    return _validated_projection(record,kind,item.code,classification,template,warning)


def install_templates(db):
    """Append V4 once to each active subsystem, retaining all existing versions."""
    created = 0
    for sub in db.scalars(select(Subsystem).where(Subsystem.archived.is_(False)).with_for_update()):
        versions = list(db.scalars(select(DataTemplate).where(DataTemplate.subsystem_id == sub.id)
                                   .order_by(DataTemplate.version.desc())))
        if any(version.fields and version.fields[0].get('contract_version') == '4.0' for version in versions):
            continue
        version = versions[0].version + 1 if versions else 1
        db.add(DataTemplate(subsystem_id=sub.id, version=version, fields=fields_for(sub.code)))
        created += 1
    return created


def property_matches(technical, field, minimum, maximum):
    view = template_view('', '', 0, [field])
    projected = canonical_solution({'technical_data': technical}, kind='generic', code='',
                                   classification={'subsystem_code': ''}, template=view)
    value = projected['properties'][field['code']]['value']
    return (type(value) in (int, float) and (minimum is None or value >= minimum)
            and (maximum is None or value <= maximum))


def catalogue_highlights(db, records, commercial=False):
    """Add template summaries in one lookup per distinct subsystem, only when requested."""
    templates = {}
    for record in records:
        identity = record['subsystem_id']
        target = record['published'] if commercial else record
        if target is None:
            continue
        key=(identity,target.get('template_version') if commercial else None)
        if key not in templates:
            sub = db.get(Subsystem, UUID(identity))
            templates[key] = revision_template(db,sub,key[1]) if commercial else (current_template(db,sub),None)
        template,warning = templates[key]
        canonical = _validated_projection(target,'commercial' if commercial else 'generic',
                                          record['code'],{'subsystem_code':template['code']},template,warning)
        if warning:target['template_warning']=warning
        target['template_highlights'] = [
            {'label': field.get('name_es') or field.get('label') or field['code'],
             **canonical['properties'][field['code']]}
            for field in template['fields']
            if canonical['properties'][field['code']]['status'] == 'PRESENT'
        ][:2]
    return records
