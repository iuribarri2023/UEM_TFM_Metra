"""Dependency-light invariants for the delivery; database tests live separately."""
from hashlib import sha256
from pathlib import Path
import json
import re

BACKEND=Path(__file__).resolve().parents[1]
DATA=BACKEND/'data/metra-demo'
MANIFEST=json.loads((DATA/'inventory.json').read_text(encoding='utf-8'))


def test_active_hashes_and_references_are_consistent():
    assert (MANIFEST['counts']['generic'],MANIFEST['counts']['commercial'])==(94,91)
    assert len(MANIFEST['references'])==185
    assert len(MANIFEST['active_sha256'])==185
    assert 'retired_sha256' not in MANIFEST
    for relative,digest in MANIFEST['active_sha256'].items():
        assert '/metra-demo/' in relative
        assert sha256((DATA/relative).read_bytes()).hexdigest()==digest


def test_all_ifc_are_free_of_previous_metadata_markers():
    project=BACKEND.parent
    models=list(project.rglob('*.ifc'))
    assert len(models)==186  # 185 published-corpus assets + 1 isolated fixture
    for model in models:
        payload=model.read_bytes()
        assert payload.startswith(b'ISO-10303-21;')
        assert not re.search(rb'OpenAI|ChatGPT',payload,re.IGNORECASE),str(model)


def test_only_one_operating_corpus_exists():
    assert DATA.is_dir()
    assert not (BACKEND/'data/v3').exists()
    assert not (BACKEND/'data/archive').exists()
    for collection in ('generic_solutions','manufacturer_solutions'):
        assert (DATA/collection/'metra-demo').is_dir()
        assert not (DATA/collection/'v3').exists()
