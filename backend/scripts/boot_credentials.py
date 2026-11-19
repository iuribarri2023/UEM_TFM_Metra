"""First-boot input validation. No credentials are written to logs."""
import json
import os
from pathlib import Path
import re

from pydantic import EmailStr, TypeAdapter, ValidationError


def credentials():
    try:
        email=TypeAdapter(EmailStr).validate_python(os.getenv('METRA_ADMIN_EMAIL','')).lower()
    except ValidationError:
        raise ValueError('Configura un METRA_ADMIN_EMAIL válido.') from None
    filename=os.getenv('METRA_ADMIN_PASSWORD_FILE')
    password=Path(filename).read_text(encoding='utf-8').rstrip('\r\n') if filename else os.getenv('METRA_ADMIN_PASSWORD','')
    if len(password)<14 or len(password)>256 or len(set(password))<8:
        raise ValueError('Configura una contraseña inicial de 14 a 256 caracteres con suficiente variedad.')
    return email,password


def read_rights(manifest):
    filename=os.getenv('METRA_ASSET_RIGHTS_FILE')
    if not filename:
        return {}
    entries=json.loads(Path(filename).read_text(encoding='utf-8'))
    if not isinstance(entries,list):
        raise ValueError('El manifiesto de derechos debe ser una lista.')
    result={}
    for entry in entries:
        if not isinstance(entry,dict) or set(entry)!={'solution','sha256','view','download','evidence'}:
            raise ValueError('Entrada de derechos con campos incorrectos.')
        key=entry['solution']
        if not isinstance(key,str) or key not in manifest['references'] or key in result:
            raise ValueError('Código de derechos desconocido o duplicado.')
        if entry['sha256']!=manifest['active_sha256'][manifest['references'][key]]:
            raise ValueError('El derecho no corresponde al SHA-256 del original.')
        if type(entry['view']) is not bool or type(entry['download']) is not bool:
            raise ValueError('Los permisos deben ser booleanos independientes.')
        if not isinstance(entry['evidence'],str) or not entry['evidence'].strip():
            raise ValueError('La autorización requiere una referencia documental de derechos.')
        result[key]=entry
    return result
