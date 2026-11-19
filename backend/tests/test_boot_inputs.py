import json

import pytest
from app.inventory import inventory
from scripts.boot_credentials import credentials,read_rights


def test_initial_admin_requires_a_configured_password(monkeypatch,tmp_path):
    monkeypatch.setenv('METRA_ADMIN_EMAIL','initial@example.com')
    monkeypatch.delenv('METRA_ADMIN_PASSWORD_FILE',raising=False)
    monkeypatch.delenv('METRA_ADMIN_PASSWORD',raising=False)
    with pytest.raises(ValueError,match='contraseña inicial'):
        credentials()
    file=tmp_path/'secret'
    file.write_text('only-for-test-Long-Password-2026!\n')
    monkeypatch.setenv('METRA_ADMIN_PASSWORD_FILE',str(file))
    assert credentials()[0]=='initial@example.com'


def test_rights_reject_wrong_bytes_and_keep_permissions_independent(monkeypatch,tmp_path):
    manifest=inventory()
    key,path=next(iter(manifest['references'].items()))
    file=tmp_path/'rights.json'
    monkeypatch.setenv('METRA_ASSET_RIGHTS_FILE',str(file))
    entry={'solution':key,'sha256':'invalid','view':True,'download':False,'evidence':'fixture'}
    file.write_text(json.dumps([entry]))
    with pytest.raises(ValueError,match='SHA-256'):
        read_rights(manifest)
    entry['sha256']=manifest['active_sha256'][path]
    file.write_text(json.dumps([entry]))
    assert read_rights(manifest)[key]['download'] is False
