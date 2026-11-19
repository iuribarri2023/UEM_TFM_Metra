"""Read the consolidated metra-demo catalogue and provenance index."""
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / 'data/metra-demo'
GROUPS = {'g': 'generic_solutions', 'p': 'manufacturer_solutions'}


def fingerprint(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


@lru_cache(maxsize=1)
def academic_index():
    return json.loads((DATA/'academic_values.json').read_text(encoding='utf-8'))


def academic_value(kind, code, path, value):
    return academic_index().get(f'{kind}:{code}', {}).get(path) == fingerprint(value)


def imported_payload(item, relative_path):
    """Persist each domain once. Identity and permissions belong to relational columns."""
    separate = {'code','name_es','assets','economic_data','environmental_data','description',
                'commercial_reference','composition'}
    payload = {k:v for k,v in item.items() if k not in separate}
    if 'description' in item:
        payload['description'] = item['description']
    payload['legacy_source'] = relative_path
    return payload


def runtime_technical(payload, kind, code):
    """Adapt historical snapshots without writing to them."""
    result = dict(payload)
    legacy = result.pop('legacy_payload', None)
    if isinstance(legacy,dict):
        # Keep historical specialized data that the old importer left only in the snapshot.
        for key, value in legacy.items():
            if key not in {'assets','economic_data','environmental_data','composition','properties','technical_performance'}:
                result.setdefault(key, value)
    if kind == 'p' and 'properties' not in result and isinstance(result.get('technical_data'),dict):
        result['properties'] = result['technical_data']
    archived = historical_academic(payload,kind,code)
    enabled = academic_enabled()
    performance = dict(result.get('technical_performance') or {})
    if archived and enabled:
        for key in ('overview','composition_scenario'):
            if key in archived:
                result.setdefault(key,archived[key])
        for key,value in archived.get('technical_performance',{}).items():
            # Only didactic additions, never replace measured or edited values.
            if key=='illustrative' or isinstance(value,dict) and 'value' in value and academic_value(
                    kind,code,f'/technical_performance/{key}/value',value['value']):
                # If a draft carries updated properties, avoid masking them.
                if key not in (result.get('properties') or {}):
                    performance.setdefault(key,value)
    if result.get('legacy_source'):
        for key,value in list(performance.items()):
            if key=='illustrative' and not enabled and academic_value(
                    kind,code,'/technical_performance/illustrative',value):
                performance.pop(key)
            elif isinstance(value,dict) and 'value' in value and academic_value(
                    kind,code,f'/technical_performance/{key}/value',value['value']):
                if enabled:
                    performance[key] = {**value,'source_type':'DEMO_SIMULATED','verification_status':'UNVERIFIED'}
                else:
                    performance[key] = {**value,'value':None}
        if not enabled:
            for key in ('overview','composition_scenario'):
                if key in result and academic_value(kind,code,'/'+key,result[key]):
                    result.pop(key)
    if performance or 'technical_performance' in result:
        result['technical_performance'] = performance
    return result


@lru_cache(maxsize=1)
def prior_storage_uris():
    # Only stable identity compatibility for existing assets. No technical values.
    return json.loads((DATA/'asset_identity.json').read_text(encoding='utf-8'))


@lru_cache(maxsize=1)
def historical_index():
    return json.loads((DATA/'historical_identity.json').read_text(encoding='utf-8'))


@lru_cache(maxsize=198)
def historical_record(kind, code, source):
    # Normalize old persisted source pointers without mutating existing SQL records.
    for legacy in ('v3', 'demo_metra'):
        source = source.replace(f'generic_solutions/{legacy}/', 'generic_solutions/metra-demo/', 1)
        source = source.replace(f'manufacturer_solutions/{legacy}/', 'manufacturer_solutions/metra-demo/', 1)
    candidate = (DATA/source).resolve()
    if not candidate.is_relative_to(DATA.resolve()) or not candidate.is_file():
        return {}
    doc = json.loads(candidate.read_text(encoding='utf-8'))
    return next((row for row in doc.get(GROUPS[kind], []) if row['code']==code), {})


def historical_academic(payload, kind, code):
    source = payload.get('legacy_source')
    if not isinstance(source,str):
        return {}
    original = payload.get('legacy_payload')
    if isinstance(original,dict):
        if historical_index().get(f'{kind}:{code}') != fingerprint(original):
            return {}
        return historical_record(kind,code,source)
    # Consolidated imports already have one snapshot. Only reuse the reference when
    # its measurement basis still matches, and never replace an authored reference.
    row=historical_record(kind,code,source)
    if not row or payload.get('functional_unit')!=row.get('functional_unit'):
        return {}
    if 'properties' in payload and kind=='p':
        return {}
    saved=payload.get('technical_performance') or {}
    bundled=row.get('technical_performance') or {}
    if any(saved.get(key)!=bundled.get(key) for key in ('surface_mass','total_thickness_mm','depth_mm')):
        return {}
    return row



def academic_enabled():
    return True  # Historical estimates are displayed with their original provenance.


def runtime_domain(value, archived, domain, kind, code):
    result = dict(value) if isinstance(value,dict) else {}
    old = result.pop('legacy', None)
    if isinstance(old, dict):
        result = {**old, **result}
    reference = archived.get(domain, {}).get('reference')
    if reference:
        result.setdefault('reference',reference)
    # The historical illustration stays in the stored snapshot, outside the live view.
    result.pop('illustrative',None)
    return result
