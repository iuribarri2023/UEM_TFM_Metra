"""Pure contract tests: strict pair validation is independent of the DB/API runtime."""
import pytest
from app.comparison import MAX_COMPARISON_ITEMS, parse_pair, warnings_for

A='11111111-1111-4111-8111-111111111111'
B='22222222-2222-4222-8222-222222222222'
C='33333333-3333-4333-8333-333333333333'


def test_exactly_two_with_generic_commercial_and_legacy_keys():
    assert MAX_COMPARISON_ITEMS == 2
    assert [kind for kind,_ in parse_pair(f'g:{A},{B}')] == ['g','p']
    assert [kind for kind,_ in parse_pair(f'p:{A},p:{B}')] == ['p','p']
    assert [kind for kind,_ in parse_pair(f'g:{A},g:{B}')] == ['g','g']


@pytest.mark.parametrize('ids', ['','p:'+A,f'{A},{B},{C}',f'{A},{A}',f'p:{A},{A}',f'unknown:{A},{B}'])
def test_reject_incomplete_duplicate_or_three_solutions(ids):
    with pytest.raises(ValueError):parse_pair(ids)


def test_warning_when_subsystem_or_functional_unit_differ():
    a={'system_id':'x','subsystem_id':'a','functional_unit':'m2'}
    b={'system_id':'y','subsystem_id':'b','functional_unit':'m3'}
    messages=' '.join(warnings_for([a,b]))
    assert 'Sistemas distintos' in messages
    assert 'Subsistemas distintos' in messages
    assert 'Unidades funcionales distintas' in messages
    assert 'EPD' in messages
