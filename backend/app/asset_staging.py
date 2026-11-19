"""Safe filesystem promotion for uploads/imported originals.

Filesystem rename and PostgreSQL commit are NOT one atomic transaction. Callers
must use a database transaction and run a storage audit after failures.
"""
from __future__ import annotations
import hashlib
import os
import tempfile
from pathlib import Path


def promote_if_absent(store:Path,key:str,payload:bytes,*,sha256:str):
    """Create a verified document via same-volume staging; never overwrite originals."""
    base=store.resolve()
    if not key or Path(key).name!=key or '/' in key or '\\' in key:
        raise ValueError('Invalid storage key')
    if hashlib.sha256(payload).hexdigest()!=sha256:
        raise ValueError('Source SHA-256 mismatch')
    base.mkdir(parents=True,exist_ok=True)
    target=base/key
    if target.exists() or target.is_symlink():
        if target.is_symlink() or not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest()!=sha256:
            raise ValueError('Existing document has wrong SHA-256 or is not a regular file')
        return False
    fd,tmp=tempfile.mkstemp(prefix='.stage-',suffix='.tmp',dir=base)
    try:
        with os.fdopen(fd,'wb') as out:
            out.write(payload)
            out.flush()
            os.fsync(out.fileno())
        if hashlib.sha256(Path(tmp).read_bytes()).hexdigest()!=sha256:
            raise IOError('Staged file failed integrity check')
        try:
            # Staging and destination share a filesystem. Linking is atomic and
            # fails if any entry, including a symlink, already owns this key.
            os.link(tmp,target,follow_symlinks=False)
        except FileExistsError:
            if target.is_symlink() or not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest()!=sha256:
                raise ValueError('Concurrent document with different digest')
            return False
        if hashlib.sha256(target.read_bytes()).hexdigest()!=sha256:
            raise IOError('Promoted file failed integrity check')
        return True
    finally:
        Path(tmp).unlink(missing_ok=True)
