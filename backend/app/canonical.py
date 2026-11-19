"""Lossless read projection of a solution onto an explicit subsystem contract."""
import hashlib
import math

from .data_templates import fields_for, template_view

UNIT_ALIASES = {'m2': 'm²', 'm3': 'm³', 'ud': 'unit', 'pcs': 'unit',
                'W/m2K': 'W/(m²·K)', 'W/m²K': 'W/(m²·K)', 'kg/m2': 'kg/m²'}
CONVERSIONS = {('cm', 'mm'): 10, ('m', 'mm'): 1000, ('W', 'kW'): .001}
MISSING = {'', 'not_documented', 'not_assessed', 'not_available', 'unknown', 'project_specific'}


def unit_name(unit):
    return UNIT_ALIASES.get(unit, unit) if isinstance(unit, str) else None


def property_value(field, raw, *, assumed_unit=False):
    spec_unit = field.get('canonical_unit', field.get('unit', 'unit'))
    spec_type = field.get('value_type', field.get('type', 'string'))
    if isinstance(raw, dict):
        unit = unit_name(raw.get('unit'))
        value = raw.get('value')
        provenance = raw.get('source_type')
    else:
        unit, value, provenance = None, raw, None
    if value is None or isinstance(value, str) and value.strip().casefold() in MISSING:
        return None, 'MISSING'
    if spec_type == 'number':
        if type(value) not in (int, float) or abs(value) > 1e15 or not math.isfinite(value):
            return None, 'INVALID_TYPE'
        if unit is None and assumed_unit:
            unit = spec_unit
        if unit != spec_unit:
            factor = CONVERSIONS.get((unit, spec_unit))
            if factor is None or unit not in field.get('allowed_units', []):
                return None, 'INVALID_UNIT'
            value = round(value * factor, 10)
        if 'min' in field and value < field['min'] or 'max' in field and value > field['max']:
            return None, 'OUT_OF_RANGE'
    elif spec_type == 'boolean' and type(value) is not bool or spec_type in ('text', 'string') and not isinstance(value, str):
        return None, 'INVALID_TYPE'
    if field.get('enum') and value not in field['enum']:
        return None, 'OUT_OF_ENUM'
    allowed_sources = {'SOURCE_DECLARED','CALCULATED','DEMO_SIMULATED','LEGACY_SIMULATED','UNKNOWN'}
    source = provenance if provenance in allowed_sources else 'UNKNOWN'
    metadata = {key: raw[key] for key in ('source','method','date','reference')
                if isinstance(raw,dict) and isinstance(raw.get(key),str)}
    status = raw.get('verification_status') if isinstance(raw,dict) else None
    status = status if status in {'VERIFIED','UNVERIFIED','NOT_AVAILABLE'} else 'UNVERIFIED'
    return {'value': value, 'unit': spec_unit, 'source_type': source,
            'verification_status': status, **metadata}, 'PRESENT'


def property_groups(technical, prefer_performance=True):
    technical = technical if isinstance(technical, dict) else {}
    performance = technical.get('technical_performance')
    props = technical.get('properties')
    if prefer_performance and isinstance(props,dict):
        yield 'properties', {key:value for key,value in props.items()
                             if isinstance(value,dict) and 'value' in value and 'unit' in value}
    if prefer_performance and isinstance(performance, dict):
        yield 'technical_performance', performance
    if isinstance(props, dict):
        # Historical commercial nests the declared properties under the original template payload.
        inner = props.get('properties')
        yield 'properties.properties', inner if isinstance(inner, dict) else {}
        yield 'properties', props
    if not prefer_performance and isinstance(performance,dict):
        yield 'technical_performance', performance


def demo_value(field, code, overlay):
    props = overlay.get('technical', {})
    if not isinstance(props, dict):
        props = {}
    for key in (field['code'], *field.get('aliases', [])):
        candidate = props.get(key)
        if candidate is not None:
            value, _ = property_value(field, candidate)
            if value:
                return value['value']
    bounds = field.get('demo_range')
    if bounds:
        raw = hashlib.sha256(f'v4|{code}|{field["code"]}'.encode()).digest()
        fraction = int.from_bytes(raw[:8], 'big') / (2**64 - 1)
        return round(bounds[0] + (bounds[1] - bounds[0]) * fraction, 2)
    return None


def canonical_solution(record, *, kind, code, classification, template=None, overlay=None, prefer_performance=True):
    sub = classification['subsystem_code']
    template = template or template_view(sub, classification.get('subsystem_id', ''), 0, fields_for(sub))
    groups = list(property_groups(record.get('technical_data'), prefer_performance))
    properties = {}
    recognized = set()
    for field in template['fields']:
        key = field['code']
        aliases = tuple(dict.fromkeys((key, *field.get('aliases', []))))
        recognized.update(aliases)
        value, status, path = None, 'MISSING', None
        for prefix, group in groups:
            for alias in aliases:
                if alias not in group:
                    continue
                candidate, state = property_value(field, group[alias], assumed_unit=alias in field.get('aliases', []))
                if state != 'MISSING' and status == 'MISSING':
                    status, path = state, f'{prefix}.{alias}'
                if candidate:
                    value, status, path = candidate, state, f'{prefix}.{alias}'
                    break
            if value:
                break
        if value is None and status == 'MISSING' and overlay:
            illustrative = demo_value(field, code, overlay)
            if illustrative is not None:
                value = {'value': illustrative, 'unit': field.get('unit', 'unit'),
                         'source_type': 'DEMO_SIMULATED', 'verification_status': 'UNVERIFIED'}
                status, path = 'PRESENT', 'academic_overlay'
        properties[key] = {'value': None, 'unit': field.get('unit', 'unit'),
                           'source_type': 'MISSING', 'verification_status': 'NOT_AVAILABLE',
                           **(value or {}), 'status': status, 'source_path': path}
    issues = [{'code': key, 'status': cell['status']} for key, cell in properties.items() if cell['status'] != 'PRESENT']
    unknown = sorted({key for _, group in groups for key in group if key not in recognized and key != 'properties'})
    technical = record.get('technical_data') or {}
    return {
        'schema_version': '3.0', 'id': record.get('id'), 'kind': kind, 'code': code,
        'name_es': record.get('name_es'), 'classification': classification,
        'template': template, 'functional_unit': unit_name(record.get('functional_unit') or technical.get('functional_unit')),
        'properties': properties,
        'composition': composition_rows(record.get('composition') or technical.get('composition')),
        'economic': declared_domain(record.get('economic_data'), 'economic'),
        'environmental': declared_domain(record.get('environmental_data'), 'environmental'),
        'assets': record.get('assets') or [],

        'quality': {'issues': issues, 'unmapped_fields': unknown},
        'traceability': {'revision_id': record.get('id') if kind == 'commercial' else None,
                         'revision': record.get('number'), 'capture_template_version': record.get('template_version'),
                         'status': record.get('status')},
    }


def composition_rows(value):
    if not isinstance(value, list):
        return []
    rows = []
    for index, layer in enumerate(value, 1):
        if not isinstance(layer, dict):
            continue
        details = layer.get('properties') if isinstance(layer.get('properties'), dict) else {}
        thickness = layer.get('thickness_mm', details.get('thickness_mm'))
        rows.append({
            'order': index, 'code': layer.get('code') or layer.get('key') or layer.get('slot_code'),
            'name_es': layer.get('name_es') or layer.get('name'),
            'material': layer.get('material') or details.get('material_label_es'),
            'role': layer.get('role'), 'thickness_mm': thickness if type(thickness) in (int,float) else None,
            'source_type': layer.get('source_type') if layer.get('source_type') in
                ('SOURCE_DECLARED','CALCULATED','DEMO_SIMULATED','LEGACY_SIMULATED') else 'UNKNOWN',
            'verification_status': 'UNVERIFIED',
        })
    return rows


def declared_domain(value, domain):
    if not isinstance(value, dict):
        value = {}
    legacy = value.get('legacy') if isinstance(value.get('legacy'), dict) else value
    rows = []
    simulation_markers = {'simulated_source_workbook','provisional_poc_assumption','assumed_poc'}
    basis = next((legacy[key] for key in ('price_basis','value_status','assessment_status','value_basis')
                  if isinstance(legacy.get(key),str) and legacy[key] in simulation_markers), None)
    for entry in value.get('declared', []) if isinstance(value.get('declared'), list) else []:
        if isinstance(entry, dict) and 'value' in entry:
            row={key: entry.get(key) for key in ('label','value','unit','source','method','date','module')}
            row['source_type']=entry.get('source_type') if entry.get('source_type') in ('SOURCE_DECLARED','CALCULATED','DEMO_SIMULATED') else 'UNKNOWN'
            row['verification_status']='UNVERIFIED'
            rows.append(row)
    keys = ('unit_cost', 'indicative_price') if domain == 'economic' else (
        'gwp_a1_a3_kgco2e_per_fu', 'gwp_a1_a3_kgco2e_m2')
    for key in keys:
        if type(legacy.get(key)) not in (int, float):
            continue
        unit = legacy.get('unit') if domain == 'economic' else (
            'kgCO₂e/m²' if key.endswith('_m2') else None)
        rows.append({'label': key, 'value': legacy[key], 'unit': unit,
                     'source': 'Estimación académica sin verificar' if basis else 'Inventario METRA-DEMO',
                     'source_type': 'LEGACY_SIMULATED' if basis else 'UNKNOWN',
                     'verification_status': 'UNVERIFIED',
                     'basis': basis, 'module': 'A1–A3' if domain == 'environmental' else None})
    return {'values': rows, 'status': legacy.get('status') or legacy.get('assessment_status'),
            'currency': legacy.get('currency') if domain == 'economic' else None,
            'source_type': ('UNKNOWN' if rows else 'MISSING'),
            'verification_status': 'UNVERIFIED' if rows else 'NOT_AVAILABLE'}
