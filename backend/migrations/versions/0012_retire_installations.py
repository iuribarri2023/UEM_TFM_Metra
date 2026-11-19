"""Withdraw installations without changing revision snapshots or deleting documents."""
from alembic import op

revision = '0012_retire_installations'
down_revision = '0011_archive_demo_overlays'
branch_labels = None
depends_on = None


def upgrade():
    # Record before state for any eventual editorial review.
    for table, field in [('generic_solutions','status'),('commercial_solutions','availability')]:
        op.execute(f"""
          INSERT INTO audit_logs (id, at, action, entity, entity_id, detail)
          SELECT gen_random_uuid(), CURRENT_TIMESTAMP, 'RETIRE_INSTALLATIONS',
                 '{table}', r.id::text, jsonb_build_object('previous',r.{field})
          FROM {table} r JOIN subsystems s ON s.id=r.subsystem_id
          JOIN systems t ON t.id=s.system_id
          WHERE t.code='INS' AND r.{field}<>'ARCHIVED'
        """)
        op.execute(f"""UPDATE {table} r SET {field}='ARCHIVED'
          FROM subsystems s JOIN systems t ON t.id=s.system_id
          WHERE r.subsystem_id=s.id AND t.code='INS'""")
    op.execute("""UPDATE archetypes a SET archived=true FROM subsystems s
        JOIN systems t ON t.id=s.system_id WHERE a.subsystem_id=s.id AND t.code='INS'""")
    op.execute("""UPDATE subsystems s SET archived=true FROM systems t
        WHERE s.system_id=t.id AND t.code='INS'""")
    op.execute("UPDATE systems SET archived=true WHERE code='INS'")


def downgrade():
    raise RuntimeError('Restaurar la copia previa para recuperar estados editoriales.')
