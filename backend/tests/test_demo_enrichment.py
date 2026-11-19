"""Active catalogue and model consistency."""
from scripts.catalogue_data import validate
from app.inventory import inventory

def test_active_data_fields_assets_and_models():
    report=validate()
    assert report['counts']=={'generic':94,'commercial':91}
    assert report['references']==185 and report['archived_ifcs']==0
    assert report['templates']==13
    assert all(not code.startswith('g:INS.') for code in inventory()['references'])
