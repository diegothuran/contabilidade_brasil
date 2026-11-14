"""Empresa na chave de external_refs: cada empresa do escritório tem sua própria memória de importação."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019_external_refs_entity"
down_revision: str | None = "0018_withholding_payments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("external_refs", sa.Column("legal_entity_id", sa.String(160), nullable=True))
    op.execute(
        """
        UPDATE external_refs AS ref
        SET legal_entity_id = batch.legal_entity_id
        FROM import_batches AS batch
        WHERE batch.id = ref.batch_id
        """
    )
    op.alter_column("external_refs", "legal_entity_id", nullable=False)
    op.create_foreign_key(
        "fk_external_refs_legal_entity", "external_refs", "legal_entities", ["legal_entity_id"], ["id"]
    )
    op.drop_constraint("uq_external_refs", "external_refs", type_="unique")
    op.create_unique_constraint(
        "uq_external_refs",
        "external_refs",
        ["tenant_id", "legal_entity_id", "source_system", "entity_type", "external_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_external_refs", "external_refs", type_="unique")
    op.create_unique_constraint(
        "uq_external_refs", "external_refs", ["tenant_id", "source_system", "entity_type", "external_id"]
    )
    op.drop_constraint("fk_external_refs_legal_entity", "external_refs", type_="foreignkey")
    op.drop_column("external_refs", "legal_entity_id")
