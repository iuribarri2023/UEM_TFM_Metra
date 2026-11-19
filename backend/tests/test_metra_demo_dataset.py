"""Offline dataset contract tests. These do not exercise Docker/PostgreSQL/IfcOpenShell."""
from pathlib import Path
from importlib.util import spec_from_file_location,module_from_spec

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/import_metra_demo.py'
spec=spec_from_file_location('metra_demo_import',SCRIPT)
module=module_from_spec(spec)
spec.loader.exec_module(module)
ROOT=Path(__file__).resolve().parents[1]/'data/metra-demo'


def test_embedded_metra_demo_json_and_ifc_manifest():
    generic=list(module.source_documents(ROOT,'generic_solutions'))
    commercial=list(module.source_documents(ROOT,'manufacturer_solutions'))
    assert len(generic)>0 and len(commercial)>0
    assert sum(len(d['generic_solutions']) for _,d in generic)==94
    assert sum(len(d['manufacturer_solutions']) for _,d in commercial)==91
    found=[]
    for typ,items in (('generic_solutions',generic),('manufacturer_solutions',commercial)):
        for document,payload in items:
            for entry in payload[typ]:
                for uri in module.ifc_uris(entry):
                    path=module.get_asset_path(document,ROOT,typ,uri)
                    assert path is not None,(document,uri)
                    found.append(path)
    assert len(found)==185
    assert len(set(found))==185
    assert len(list(ROOT.rglob('*.ifc')))==185  # Only active originals are distributed.


def test_file_path_traversal_rejected(tmp_path):
    root=tmp_path/'root';root.mkdir()
    outside=tmp_path/'other.ifc';outside.write_bytes(b'UNTRUSTED')
    import pytest
    with pytest.raises(ValueError):
        module.safe_source(root/'../other.ifc',root)


def test_no_legacy_asset_is_published_by_importer():
    source=SCRIPT.read_text()
    assert "status='DRAFT'" in source
    assert "availability='SUSPENDED'" in source
    assert "status='REJECTED'" in source
    assert 'public_download_allowed=False' in source
    assert 'public_view_allowed=False' in source
