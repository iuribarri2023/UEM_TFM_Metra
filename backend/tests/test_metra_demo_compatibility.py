"""Contract tests for migrating operating paths without migrating asset identities."""
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

from app.asset_identity import storage_key, STORAGE_NAMESPACE
from app.consolidated_data import historical_record, DATA
from app.source_reconciliation import DATASET, store_baseline


def test_storage_keys_stable_for_existing_asset_volume():
    assert STORAGE_NAMESPACE == 'v3'  # persisted namespace: not the active folder
    expected = sha256(b'v3:generic_solutions:TEST:source.ifc').hexdigest()+'.ifc'
    assert storage_key('generic_solutions','TEST','source.ifc') == expected
    assert DATASET == 'metra-demo'


def test_legacy_source_pointers_resolve_to_current_corpus():
    assert DATA.name == 'metra-demo'
    previous='generic_solutions/v3/ENV/CUB/ENV.CUB.PL-CON.json'
    new='generic_solutions/metra-demo/ENV/CUB/ENV.CUB.PL-CON.json'
    assert (DATA/new).is_file()
    original=historical_record('g','ENV.CUB.PL-CON.GS001',previous)
    renamed=historical_record('g','ENV.CUB.PL-CON.GS001',new)
    assert original==renamed and original['code']=='ENV.CUB.PL-CON.GS001'


def test_existing_baseline_keeps_identity_and_relabels_dataset():
    state=SimpleNamespace(dataset='v3', baseline={}, source_hash='', pending={}, status='PENDING')
    class Stub:
        def get(self,model,key):
            assert key == 'g:TEST'
            return state
    result=store_baseline(Stub(),'g:TEST',{'name_es':'No mutar identidad'})
    assert result is state
    assert state.dataset=='metra-demo' and state.status=='SYNCED'
    assert state.baseline=={'name_es':'No mutar identidad'}
