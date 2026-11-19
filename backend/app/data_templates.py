"""Semantically curated V4 fields. Alias paths carry the unit asserted by the legacy corpus."""
from copy import deepcopy


def number(code, label, unit, aliases=(), bounds=None, group='Geometría', maximum=None):
    return {
        'code': code, 'name_es': label, 'label': label, 'description_es': label,
        'value_type': 'number', 'type': 'number', 'canonical_unit': unit, 'unit': unit,
        'allowed_units': list({'mm': ('mm', 'cm', 'm'), 'kW': ('kW', 'W')}.get(unit, (unit,))),
        'required': False, 'applicability': 'both', 'min': 0,
        **({'max': maximum} if maximum is not None else {}),
        'display_group': group, 'category': 'performance', 'ifc_mapping': None,
        'source_policy': 'explicit_alias_and_unit', 'verification_policy': 'unverified_by_platform',
        'comparison_policy': 'same_property_unit_and_context', 'aliases': list(aliases),
        'demo_range': bounds,
    }


def text_field(code, label, aliases=(), group='Identificación técnica'):
    field = number(code, label, 'unit', aliases, group=group)
    field.pop('min')
    return {**field, 'type': 'string', 'value_type': 'string', 'comparison_policy': 'descriptive'}


THICKNESS = number('total_thickness_mm', 'Espesor total', 'mm',
                   ('total_thickness_mm', 'thickness_mm'), (70, 250))
MASS = number('surface_mass', 'Masa superficial', 'kg/m²',
              ('surface_mass_kg_m2', 'mass_kg_m2', 'surface_mass_kg_m2_reference'), (25, 125), 'Magnitudes físicas')
WIDTH = number('module_width_mm', 'Ancho de referencia', 'mm',
               ('module_width_mm', 'reference_width_mm', 'width_mm'), (600, 2400))
HEIGHT = number('module_height_mm', 'Altura de referencia', 'mm',
                ('module_height_mm', 'reference_height_mm'), (900, 2600))
THERMAL_U = number('thermal_transmittance', 'Transmitancia térmica U', 'W/(m²·K)',
                   ('u_value_w_m2k', 'uw_w_m2k', 'thermal_transmittance'), (.25, .65), 'Térmica')
THERMAL_R = number('thermal_resistance', 'Resistencia térmica R', 'm²·K/W',
                   ('thermal_resistance_m2k_w', 'thermal_resistance'), (2.5, 5.2), 'Térmica')
RW = number('rw_db', 'Índice ponderado de reducción sonora Rw', 'dB', ('rw_db',), (29, 50), 'Acústica')
RA = number('ra_dba', 'Aislamiento acústico RA', 'dBA', ('airborne_sound_insulation_ra_dba',), group='Acústica')
RATR = number('ratr_dba', 'Aislamiento acústico RA,tr', 'dBA', ('airborne_sound_insulation_ra_tr_dba',), group='Acústica')
FIRE = text_field('fire_resistance', 'Resistencia al fuego declarada', ('fire_resistance',), 'Fuego')
MATERIAL = text_field('primary_material', 'Material principal', ('primary_material', 'structural_material', 'structure_material'))
STRUCTURAL_DEPTH = number('depth_mm', 'Canto total', 'mm', ('total_depth_mm', 'depth_mm'), (175, 360))
LENGTH = number('reference_length_mm', 'Longitud de referencia', 'mm', ('reference_model_length_mm', 'length_mm'), (2500, 6500))
POWER = number('nominal_power_kw', 'Potencia nominal', 'kW', ('nominal_power_kw', 'rated_power_kw'), (2, 18), 'Energía')
STRUCTURAL = text_field('structural_system', 'Sistema resistente', ('structural_system', 'structural_role'))
DENSITY = number('density_kg_m3', 'Densidad del material', 'kg/m³', ('density_kg_m3',), group='Magnitudes físicas')
TECH = text_field('technology', 'Tecnología', ('technology',))
CARRIER = text_field('energy_carrier', 'Vector energético', ('energy_carrier',))
WATER = text_field('waterproofing', 'Sistema de impermeabilización', ('waterproofing',), 'Estanqueidad')

BASE = [text_field('system_type', 'Configuración constructiva', ('system_type', 'construction_type')),
        MATERIAL, text_field('delivery_state', 'Forma de suministro', ('delivery_state', 'delivery_form'))]

FAMILIES = {
    'EST.PIL': [WIDTH, LENGTH, STRUCTURAL, DENSITY, FIRE],
    'EST.MUR': [THICKNESS, HEIGHT, MASS, STRUCTURAL, DENSITY, FIRE],
    'EST.FOR': [STRUCTURAL_DEPTH, LENGTH, WIDTH, MASS, STRUCTURAL, FIRE],
    'EST.VIG': [STRUCTURAL_DEPTH, WIDTH, LENGTH, STRUCTURAL, FIRE],
    'ENV.FAC': [THICKNESS, WIDTH, HEIGHT, MASS, THERMAL_U, RW, RA, RATR, WATER, FIRE],
    'ENV.CUB': [THICKNESS, MASS, THERMAL_R, WATER, FIRE, text_field('roof_type', 'Tipo de cubierta', ('roof_type',))],
    'ENV.VEN': [WIDTH, HEIGHT, THERMAL_U, RW, text_field('frame_material', 'Material del marco', ('frame_material',)),
                text_field('glazing_type', 'Tipo de acristalamiento', ('glazing_type',))],
    'INT.PAR': [THICKNESS, HEIGHT, MASS, RW, RA, FIRE],
    'INT.TRA': [THICKNESS, MASS, THERMAL_R, RW, FIRE],
    'INT.PUE': [WIDTH, HEIGHT, THICKNESS, RW, FIRE],
    'INT.SUE': [THICKNESS, MASS, THERMAL_R, FIRE, text_field('surface_finish', 'Acabado superficial', ('surface_finish',))],
    'INT.TEC': [THICKNESS, MASS, RW, FIRE],
    'MOD.BAN': [WIDTH, HEIGHT, LENGTH, number('module_area_m2', 'Superficie del módulo', 'm²',
                ('module_area_m2',), group='Geometría'), FIRE],
}

GROUPS = ['Identificación', 'Clasificación', 'Prestaciones', 'Composición',
          'Economía', 'Ambiente', 'Documentación', 'Trazabilidad']


def fields_for(code):
    fields = deepcopy(BASE + FAMILIES.get(code, []))
    for index, field in enumerate(fields, 1):
        field.update(display_order=index, contract_version='4.0')
    return fields


def template_view(code, subsystem_id, version, fields):
    return {
        'code': code, 'subsystem_id': str(subsystem_id), 'version': version,
        'schema_version': '3.0', 'groups': GROUPS, 'fields': fields,
        'representations': ['canonical-json', 'technical-table', 'comparison-matrix'],
    }
