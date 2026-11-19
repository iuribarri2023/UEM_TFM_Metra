"""Pure domain tests; PostgreSQL E2E is separately run inside Docker Compose."""
from pathlib import Path
from app.source_reconciliation import (three_way, apply_source_paths, source_entries, source_values, fingerprint, clean)


def test_three_way_enumerates_all_editorial_cases():
    baseline={'same':1,'source':1,'dest':1,'converged':1,'conflict':1}
    incoming={'same':1,'source':2,'dest':1,'converged':2,'conflict':2}
    persisted={'same':1,'source':1,'dest':3,'converged':2,'conflict':3}
    outcomes=three_way(baseline,incoming,persisted)
    assert {key:val['operation'] for key,val in outcomes.items()} == {
        'same':'UNCHANGED','source':'SOURCE_ONLY','dest':'DESTINATION_ONLY',
        'converged':'CONVERGED','conflict':'CONFLICT'}
    assert baseline['conflict']==1 and incoming['conflict']==2 and persisted['conflict']==3


def test_nested_independent_properties_merge_without_changing_destination():
    old={'technical_data':{'thermal':{'value':1,'unit':'W'},'acoustic':{'value':30,'unit':'dB'}}}
    source={'technical_data':{'thermal':{'value':2,'unit':'W'},'acoustic':{'value':30,'unit':'dB'}}}
    target={'technical_data':{'thermal':{'value':1,'unit':'W'},'acoustic':{'value':40,'unit':'dB'}}}
    decisions=three_way(old,source,target)
    assert decisions['technical_data/thermal/value']['operation']=='SOURCE_ONLY'
    assert decisions['technical_data/acoustic/value']['operation']=='DESTINATION_ONLY'
    merged=apply_source_paths(target,source,['technical_data/thermal/value'])
    assert merged['technical_data']=={'thermal':{'value':2,'unit':'W'},'acoustic':{'value':40,'unit':'dB'}}
    assert target['technical_data']['thermal']['value']==1


def test_nested_conflict_delete_and_ambiguous_array():
    old={'technical_data':{'thermal':1,'acoustic':2,'layers':[{'value':1}]}}
    source={'technical_data':{'thermal':3,'layers':[{'value':2}]}}
    target={'technical_data':{'thermal':4,'acoustic':5,'layers':[{'value':3}]}}
    decisions=three_way(old,source,target)
    assert decisions['technical_data/thermal']['operation']=='CONFLICT'
    assert decisions['technical_data/acoustic']['operation']=='CONFLICT'
    assert decisions['technical_data/acoustic']['source']=={'$missing':True}
    assert decisions['technical_data/layers']['operation']=='CONFLICT'


def test_missing_and_null_are_distinct():
    decisions=three_way({'technical_data':{}},{'technical_data':{'value':None}},
                        {'technical_data':{}})
    assert decisions['technical_data/value']['operation']=='SOURCE_ONLY'
    assert decisions['technical_data/value']['previous']=={'$missing':True}


def test_fingerprint_is_json_order_independent_and_ignores_legacy_path():
    a={'metadata':{'b':2,'a':1},'legacy_source':'generic_solutions/demo_metra/file.json'}
    b={'metadata':{'a':1,'b':2},'legacy_source':'generic_solutions/metra-demo/file.json'}
    assert fingerprint(a)==fingerprint(b)
    assert clean(a)==clean(b)


def test_source_entries_unique_and_complete():
    root=Path(__file__).resolve().parents[1]/'data/metra-demo'
    entries=list(source_entries(root))
    assert len(entries)==185
    keys=[key for _,key,*_ in entries]
    assert len(set(keys))==len(keys)
    assert sum(key.startswith('g:') for key in keys)==94
    assert sum(key.startswith('p:') for key in keys)==91
    for kind,key,path,doc,item,payload in entries:
        assert key.endswith(item['code'])
        assert len(fingerprint(payload))==64
        assert 'legacy_source' not in payload['technical_data']


def test_source_payload_does_not_drop_nested_properties():
    item={'code':'X','name_es':'Test','technical_performance':{'k':{'value':9,'unit':'m'}},
          'composition':[{'code':'a','properties':{'custom':'yes'}}],
          'environmental_data':{'reference':{'note':'example'}},'properties':{'a':'b'}}
    path=Path('/tmp/catalogue/v3/test.json');root=Path('/tmp/catalogue')
    payload=source_values('g',item,path,root)
    assert payload['technical_data']['properties']=={'a':'b'}
    assert payload['technical_data']['technical_performance']['k']['value']==9
    assert payload['composition'][0]['properties']=={'custom':'yes'}
    assert payload['environmental_data']['reference']['note']=='example'
