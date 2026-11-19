"""Immutable storage key algorithm for the bundled catalogue.

The namespace `v3` is an identity prefix written into historical volume keys,
NOT an active dataset path/version. Changing it would duplicate or orphan assets
when updating existing PostgreSQL installations. All callers share this helper.
"""
from hashlib import sha256

STORAGE_NAMESPACE = 'v3'


def storage_key(collection: str, code: str, original_uri: str) -> str:
    return sha256(f'{STORAGE_NAMESPACE}:{collection}:{code}:{original_uri}'.encode()).hexdigest()+'.ifc'
