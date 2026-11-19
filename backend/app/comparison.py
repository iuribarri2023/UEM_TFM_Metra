"""Public two-solution comparison contract; no inferred technical equivalences."""
from uuid import UUID

MAX_COMPARISON_ITEMS = 2


def parse_selection(value: str):
    """Legacy bare UUIDs are commercial; prefixed keys identify either kind."""
    if not isinstance(value, str):
        raise ValueError('Identificador inválido')
    value = value.strip()
    if ':' in value:
        kind, raw = value.split(':', 1)
    else:
        kind, raw = 'p', value
    if kind not in ('g', 'p'):
        raise ValueError('Tipo de solución inválido')
    try:
        identity = UUID(raw)
    except (ValueError, TypeError) as exc:
        raise ValueError('UUID inválido') from exc
    return kind, identity


def parse_pair(value: str):
    entries = [part.strip() for part in value.split(',') if part.strip()]
    if len(entries) != MAX_COMPARISON_ITEMS:
        raise ValueError('Selecciona exactamente dos soluciones')
    parsed = [parse_selection(item) for item in entries]
    if len(set(parsed)) != MAX_COMPARISON_ITEMS:
        raise ValueError('Selecciona dos soluciones diferentes')
    return parsed


def warnings_for(solutions):
    notes = []
    a, b = solutions
    if a['system_id'] != b['system_id']:
        notes.append('Sistemas distintos: las prestaciones no son automáticamente equivalentes.')
    if a['subsystem_id'] != b['subsystem_id']:
        notes.append('Subsistemas distintos: interpretar las propiedades según su función constructiva.')
    if not a['functional_unit'] or not b['functional_unit']:
        notes.append('Falta unidad funcional declarada: no calcular diferencias económicas o ambientales.')
    elif a['functional_unit'] != b['functional_unit']:
        notes.append('Unidades funcionales distintas: no calcular diferencias económicas o ambientales.')
    notes.append('EPD: su comparabilidad exige verificar indicador, módulo, unidad, alcance, fuente y método.')
    return notes
