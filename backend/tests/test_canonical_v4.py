import importlib.util
from pathlib import Path

from app.canonical import canonical_solution, property_value
from app.data_templates import fields_for

def test_canonical_values_keep_truth_and_flag_unknown_units():
    fields = fields_for('ENV.FAC')
    field = next(field for field in fields if field['code'] == 'total_thickness_mm')
    cell, status = property_value(field, {'value': 12, 'unit':'cm'})
    assert status == 'PRESENT' and cell['value'] == 120 and cell['unit'] == 'mm'
    assert property_value(field, {'value':12,'unit':'kg'}) == (None, 'INVALID_UNIT')
    assert property_value(field, {'value':True,'unit':'mm'}) == (None, 'INVALID_TYPE')
    assert property_value(field, 42) == (None, 'INVALID_UNIT')

def test_demo_fill_is_repeatable_and_does_not_mask_bad_source():
    record = {'technical_data': {'properties': {'total_thickness_mm': 170,
                                                'surface_mass': {'value': 30,'unit':'kW'}}}}
    kwargs = dict(kind='generic', code='fixture', classification={'subsystem_code':'ENV.FAC'},
                  overlay={'source_type':'DEMO_SIMULATED','verification_status':'UNVERIFIED'})
    first = canonical_solution(record, **kwargs)
    assert canonical_solution(record, **kwargs) == first
    fields = first['properties']
    assert fields['total_thickness_mm']['value'] == 170
    assert fields['total_thickness_mm']['source_type'] == 'UNKNOWN'
    assert fields['surface_mass']['status'] == 'INVALID_UNIT'
    assert fields['thermal_transmittance']['source_type'] == 'DEMO_SIMULATED'
    assert fields['fire_resistance']['status'] == 'MISSING'


def test_provenance_is_not_invented():
    fields=fields_for('ENV.FAC')
    field=next(x for x in fields if x['code']=='total_thickness_mm')
    cell,status=property_value(field, {'value':170,'unit':'mm'})
    assert status=='PRESENT' and cell['source_type']=='UNKNOWN' and cell['verification_status']=='UNVERIFIED'
    declared,status=property_value(field, {'value':170,'unit':'mm','source_type':'SOURCE_DECLARED'})
    assert declared['source_type']=='SOURCE_DECLARED'
    assert property_value(field,None)==(None,'MISSING')
