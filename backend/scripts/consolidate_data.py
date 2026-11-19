"""Helpers to inspect the single active METRA demonstration catalogue.

Historical multi-version merge logic was removed with the inactive data archives.
No command in this module regenerates or overwrites catalogue records.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
GROUPS = ('generic_solutions', 'manufacturer_solutions')
CATALOGUE = BACKEND / 'data' / 'metra-demo'


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                             separators=(',', ':')).encode()).hexdigest()


def pointer(parts):
    return ''.join('/' + str(p).replace('~', '~0').replace('/', '~1') for p in parts)


def write(path, value):
    """Write explicitly requested reports (not historical catalogue migrations)."""
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def documents(root=CATALOGUE):
    """Iterate the current, active JSON manifests only."""
    for group in GROUPS:
        folder=root/group/'metra-demo'
        for path in sorted(folder.rglob('*.json')):
            doc=json.loads(path.read_text(encoding='utf-8'))
            if isinstance(doc.get(group),list):
                yield group,path,doc


def main():
    from scripts.catalogue_data import validate
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validate',action='store_true',help='Validate the active catalogue (read-only)')
    parser.parse_args()
    print(json.dumps(validate(),ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
