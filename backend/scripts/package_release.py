"""Build and verify the source-only METRA_corrected_final.zip distribution."""
import hashlib
import json
import os
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT=Path(__file__).resolve().parents[2]
OUTPUT=ROOT/'METRA_corrected_final.zip'
EXCLUDED_DIRS={'.git','.angular','.pytest_cache','.ruff_cache','__pycache__',
               '.venv','venv','node_modules','dist','local-assets','test-results'}
EXCLUDED_SUFFIXES={'.pyc','.pyo','.log','.dump','.backup','.sqlite','.db','.p12','.pfx','.pem','.key'}
REQUIRED={'README.md','compose.yaml','compose.e2e.yaml','.env.example',
          'backend/Dockerfile','backend/requirements.txt','backend/migrations/versions/0014_metra_demo_source.py',
          'backend/data/metra-demo/inventory.json','backend/app/source_reconciliation.py',
          'frontend/Dockerfile','frontend/package.json','frontend/src/app/features/catalogue.component.ts',
          'docs/CORRECTIVE_MAINTENANCE_REPORT.md','docs/TEST_RESULTS_FINAL.md'}


def include(relative):
    if any(part in EXCLUDED_DIRS for part in relative.parts[:-1]):return False
    name=relative.name.lower()
    if name=='.env' or name.startswith('.env.') and name!='.env.example':return False
    if name=='asset-rights.json' or name=='metra_corrected_final.zip':return False
    if relative.suffix.lower() in EXCLUDED_SUFFIXES:return False
    return True


def main():
    manifest=json.loads((ROOT/'backend/data/metra-demo/inventory.json').read_text(encoding='utf-8'))
    for relative,expected in manifest['active_sha256'].items():
        source=ROOT/'backend/data/metra-demo'/relative
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest()!=expected:
            raise RuntimeError('Canonical IFC SHA-256 mismatch: '+relative)
    members=[]
    for directory,dirs,files in os.walk(ROOT):
        dirs[:]=sorted(name for name in dirs if name not in EXCLUDED_DIRS)
        for name in sorted(files):
            path=Path(directory)/name
            relative=path.relative_to(ROOT)
            if include(relative):members.append((path,relative.as_posix()))
    names={name for _,name in members}
    if not REQUIRED<=names:raise RuntimeError('Distribution source files are missing')
    if sum(name.startswith('backend/data/metra-demo/') and name.endswith('.ifc') for name in names)!=185:
        raise RuntimeError('Distribution must include exactly 185 canonical IFCs')
    with ZipFile(OUTPUT,'w',compression=ZIP_DEFLATED,compresslevel=6) as archive:
        for path,name in members:archive.write(path,name)
    with ZipFile(OUTPUT) as archive:
        if archive.testzip() is not None or set(archive.namelist())!=names:
            raise RuntimeError('ZIP integrity or member list mismatch')
        for name in ('backend/data/metra-demo/inventory.json','compose.yaml',
                     'backend/app/source_reconciliation.py'):
            if hashlib.sha256(archive.read(name)).digest()!=hashlib.sha256((ROOT/name).read_bytes()).digest():
                raise RuntimeError('ZIP source hash mismatch: '+name)
    print(f'{OUTPUT} | {len(names)} files | {OUTPUT.stat().st_size} bytes | '
          f'SHA256 {hashlib.sha256(OUTPUT.read_bytes()).hexdigest()}')


if __name__=='__main__':main()
