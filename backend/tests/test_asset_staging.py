import hashlib
from concurrent.futures import ThreadPoolExecutor
import pytest
from app.asset_staging import promote_if_absent


def test_verified_atomic_promotion_without_replacement(tmp_path):
    data=b'ISO-10303-21;\nTEST\nEND-ISO-10303-21;'
    digest=hashlib.sha256(data).hexdigest()
    assert promote_if_absent(tmp_path,'ifc.ifc',data,sha256=digest) is True
    assert promote_if_absent(tmp_path,'ifc.ifc',data,sha256=digest) is False
    assert (tmp_path/'ifc.ifc').read_bytes()==data
    assert list(tmp_path.glob('.stage-*'))==[]
    with pytest.raises(ValueError):
        promote_if_absent(tmp_path,'ifc.ifc',b'evil',sha256=hashlib.sha256(b'evil').hexdigest())
    assert (tmp_path/'ifc.ifc').read_bytes()==data


def test_safe_promotion_rejects_traversal_and_bad_hash(tmp_path):
    for key in ('../foo','subdir/file',''):
        with pytest.raises(ValueError):promote_if_absent(tmp_path,key,b'a',sha256=hashlib.sha256(b'a').hexdigest())
    with pytest.raises(ValueError):promote_if_absent(tmp_path,'test.ifc',b'a',sha256='0'*64)
    assert list(tmp_path.iterdir())==[]


def test_concurrent_promotion_never_replaces_winner(tmp_path):
    first=b'first';second=b'second'
    def publish(data):
        try:return promote_if_absent(tmp_path,'race.ifc',data,sha256=hashlib.sha256(data).hexdigest())
        except ValueError:return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(publish,(first,second)))
    assert results.count(True)==1
    assert (tmp_path/'race.ifc').read_bytes() in (first,second)
    assert list(tmp_path.glob('.stage-*'))==[]
