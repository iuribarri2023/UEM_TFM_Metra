from app.validation import check_template,discrepancies
from types import SimpleNamespace

def test_template_required_and_unit():
    t=SimpleNamespace(fields=[{'code':'thickness','unit':'mm','type':'number','required':True,'min':1}])
    assert check_template(t,{})==['Falta propiedad obligatoria: thickness']
    assert check_template(t,{'thickness':{'value':20,'unit':'mm'}})==[]
    assert check_template(t,{'thickness':{'value':-2,'unit':'mm'}})

def test_explicit_ifc_mismatch_blocking():
    t=SimpleNamespace(fields=[{'code':'mass','ifc_mapping':'Pset_WallCommon.Mass'}])
    result=discrepancies(t,{'mass':{'value':1,'unit':'kg'}},{'mapped_properties':{'Pset_WallCommon.Mass':2}})
    assert result[0]['blocking']
