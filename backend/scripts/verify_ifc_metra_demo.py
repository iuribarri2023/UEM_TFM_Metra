"""Audit IFC metadata transformations against the private ZIP of original models.

Always checks STEP structure and preserved GUID strings. When IfcOpenShell is installed,
also parses both files and compares IFC schemas, GlobalIds and representation graphs.
The original backup ZIP is never modified or copied into the project.

Usage:
  python scripts/verify_ifc_metra_demo.py --backup /private/METRA_IFC_originales_respaldo.zip
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import tempfile
import zipfile
from pathlib import Path

BACKEND=Path(__file__).resolve().parents[1]
PROJECT=BACKEND.parent
AUDIT=PROJECT/'docs/audit/IFC_METADATA_CHANGES.json'


def mask_strings(source:bytes)->bytes:
    """Produce the exact STEP byte stream with only strings masked ('' escaping aware)."""
    out=bytearray();start=0;i=0;inside=False
    while i<len(source):
        if source[i]==39:
            if inside and i+1<len(source) and source[i+1]==39:
                i+=2;continue
            if inside:
                out.extend(b"'__STRING__'");inside=False
            else:
                out.extend(source[start:i]);inside=True
            i+=1;start=i
        else:
            i+=1
    if inside:
        raise ValueError('Cadena STEP sin terminación')
    out.extend(source[start:]);return bytes(out)


def inspect(original:bytes,updated:bytes)->None:
    for data in (original,updated):
        if not data.startswith(b'ISO-10303-21;') or b'END-ISO-10303-21;' not in data:
            raise ValueError('Delimitadores STEP ausentes')
    if mask_strings(original)!=mask_strings(updated):
        raise ValueError('Estructura STEP modificada fuera de cadenas')
    if re.search(rb'OpenAI|ChatGPT',updated,re.IGNORECASE):
        raise ValueError('Metadatos antiguos aún presentes')
    original_guid=re.findall(rb"'([A-Za-z0-9_$]{22})'",original)
    final_guid=re.findall(rb"'([A-Za-z0-9_$]{22})'",updated)
    if original_guid!=final_guid:
        raise ValueError('Cambio de GlobalIds')


def parse_pair(original:bytes,updated:bytes)->None:
    import ifcopenshell
    with tempfile.TemporaryDirectory() as temp:
        a=Path(temp)/'before.ifc';b=Path(temp)/'after.ifc'
        a.write_bytes(original);b.write_bytes(updated)
        before=ifcopenshell.open(str(a));after=ifcopenshell.open(str(b))
        if before.schema!=after.schema:
            raise ValueError('Esquema IFC cambiado')
        if [x.GlobalId for x in before.by_type('IfcRoot')]!=[x.GlobalId for x in after.by_type('IfcRoot')]:
            raise ValueError('IfcRoot cambió')
        if [(e.id(),e.is_a()) for e in before]!=[(e.id(),e.is_a()) for e in after]:
            raise ValueError('Grafo de entidades alterado')
        if [e.id() for e in before.by_type('IfcRepresentation')]!=[e.id() for e in after.by_type('IfcRepresentation')]:
            raise ValueError('Representaciones geométricas alteradas')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup',type=Path,required=True)
    args=parser.parse_args()
    changes=json.loads(AUDIT.read_text(encoding='utf-8'))
    try:
        import ifcopenshell  # noqa:F401
        has_ifc=True
    except ImportError:
        has_ifc=False
    with zipfile.ZipFile(args.backup) as original_zip:
        for change in changes:
            old_name=change['source']
            new_name=(old_name
                .replace('backend/data/v3/', 'backend/data/metra-demo/',1)
                .replace('/generic_solutions/v3/', '/generic_solutions/metra-demo/',1)
                .replace('/manufacturer_solutions/v3/', '/manufacturer_solutions/metra-demo/',1))
            original=original_zip.read(old_name)
            updated=(PROJECT/new_name).read_bytes()
            if hashlib.sha256(original).hexdigest()!=change['original_sha256'] or hashlib.sha256(updated).hexdigest()!=change['updated_sha256']:
                raise ValueError('Hash no coincide: '+new_name)
            inspect(original,updated)
            if has_ifc:
                parse_pair(original,updated)
    print(json.dumps({'files_checked':len(changes),'step_preserved':True,'ifcopenshell_checked':has_ifc},ensure_ascii=False))
    if not has_ifc:
        print('AVISO: IfcOpenShell no está instalado; no se ha ejecutado parseo BIM de ambos modelos')


if __name__=='__main__':main()
