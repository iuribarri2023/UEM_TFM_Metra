"""Filesystem/SHA/atomic-cache tests; do not claim IFC rendering was executed."""
import hashlib
from pathlib import Path
import pytest
from app import ifc_thumbnails


def test_derivative_key_is_content_addressed_and_invalid_digest_is_rejected(tmp_path):
    root=tmp_path.resolve()
    first=ifc_thumbnails.thumbnail_path(root,'a'*64)
    assert first==root/'.ifc-thumbnails'/('ax-v2-'+'a'*64+'.svg')
    with pytest.raises(ValueError):ifc_thumbnails.thumbnail_path(root,'../../secret')


def test_cache_is_idempotent_and_original_is_preserved(tmp_path,monkeypatch):
    original=b'IFC mock bytes only for cache verification'
    root=tmp_path.resolve();source=root/'source.ifc';source.write_bytes(original)
    digest=hashlib.sha256(original).hexdigest()
    calls=[]
    def fake_renderer(path):
        calls.append(path)
        return '<svg xmlns="http://www.w3.org/2000/svg"/>'
    monkeypatch.setattr(ifc_thumbnails,'render_thumbnail',fake_renderer)
    assert ifc_thumbnails.cache_thumbnail(root,source,digest)
    assert ifc_thumbnails.cache_thumbnail(root,source,digest)
    assert calls==[source]
    assert source.read_bytes()==original
    assert ifc_thumbnails.thumbnail_path(root,digest).is_file()
    assert not ifc_thumbnails.cache_thumbnail(root,source,'b'*64)
    assert not ifc_thumbnails.cache_thumbnail(root,root.parent/'outside.ifc',digest)
