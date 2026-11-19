"""Recover fields omitted by the original V3 editorial publication."""
from alembic import op

revision = '0006_repair_legacy_data'
down_revision = '0005_component_links'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        WITH repaired AS (
            UPDATE commercial_solution_revisions AS published
            SET economic_data = CASE WHEN published.economic_data = '{}' THEN source.economic_data ELSE published.economic_data END,
                environmental_data = CASE WHEN published.environmental_data = '{}' THEN source.environmental_data ELSE published.environmental_data END
            FROM revision_origins AS origin
            JOIN commercial_solution_revisions AS source ON source.id = origin.parent_id
            WHERE published.id = origin.revision_id
              AND origin.message = 'Publicación editorial V3'
              AND published.status = 'APPROVED'
              AND source.status = 'REJECTED'
              AND source.product_id = published.product_id
              AND source.technical_data ? 'legacy_source'
              AND ((published.economic_data = '{}' AND source.economic_data <> '{}')
                OR (published.environmental_data = '{}' AND source.environmental_data <> '{}'))
            RETURNING published.id, source.id AS source_id
        )
        INSERT INTO audit_logs (id, at, action, entity, entity_id, detail)
        SELECT gen_random_uuid(), now(), 'REPAIR_LEGACY_DATA', 'revision', CAST(id AS text),
               jsonb_build_object('source_revision_id', source_id)
        FROM repaired
    """)


def downgrade():
    raise RuntimeError('Restaure la copia anterior para revertir esta migración')
