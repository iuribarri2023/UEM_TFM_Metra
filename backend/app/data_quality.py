"""Inventory-level quality, aggregated from the same canonical projection as details."""
from collections import defaultdict

from sqlalchemy import select
from .consolidated_data import runtime_technical
from .canonical import canonical_solution
from .catalogue import current_template
from .models import CommercialSolution, GenericSolution, Revision, Subsystem


def quality_report(db, *, include_entries=False):
    subs = {row.id: row for row in db.scalars(select(Subsystem))}
    templates = {identity: current_template(db, sub) for identity, sub in subs.items()}
    counts = defaultdict(lambda: {'generic': 0, 'commercial': 0, 'fields': 0,
                                  'present': 0, 'missing': 0, 'invalid': 0, 'unmapped': 0, 'academic': 0})
    for subsystem in subs.values():
        if not subsystem.archived:
            counts[subsystem.code]
    entries = []
    sources = [('generic', item, item) for item in db.scalars(select(GenericSolution))]
    for item in db.scalars(select(CommercialSolution)):
        record = db.get(Revision, item.published_revision_id) if item.published_revision_id else db.scalar(
            select(Revision).where(Revision.product_id == item.id).order_by(Revision.number.desc()).limit(1))
        if record is not None:
            sources.append(('commercial', item, record))
    for kind, item, record in sources:
        subsystem = subs[item.subsystem_id]
        canonical = canonical_solution({'technical_data': runtime_technical(record.technical_data, 'g' if kind=='generic' else 'p', item.code)},
                                       kind=kind, code=item.code,
                                       classification={'subsystem_code': subsystem.code},
                                       template=templates[subsystem.id])
        aggregate = counts[subsystem.code]
        aggregate[kind] += 1
        for cell in canonical['properties'].values():
            aggregate['fields'] += 1
            category = 'academic' if cell['source_type']=='DEMO_SIMULATED' else {'PRESENT': 'present', 'MISSING': 'missing'}.get(cell['status'], 'invalid')
            aggregate[category] += 1
        aggregate['unmapped'] += len(canonical['quality']['unmapped_fields'])
        if include_entries:
            entries.append({'kind': kind, 'code': item.code, 'subsystem': subsystem.code, **canonical['quality']})
    return {'schema_version': '3.0', 'subsystems': dict(sorted(counts.items())),
            'solutions': sum(group['generic'] + group['commercial'] for group in counts.values()),
            'entries': entries}
