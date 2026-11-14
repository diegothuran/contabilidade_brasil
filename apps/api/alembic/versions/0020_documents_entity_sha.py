"""O mesmo arquivo pode entrar em empresas diferentes do mesmo escritório (decisão D3)."""
from collections.abc import Sequence

from alembic import op

revision: str = "0020_documents_entity_sha"
down_revision: str | None = "0019_external_refs_entity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_documents_tenant_sha", "source_documents", type_="unique")
    op.execute(
        """
        CREATE UNIQUE INDEX uq_documents_entity_sha
        ON source_documents (tenant_id, legal_entity_id, sha256)
        WHERE legal_entity_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_documents_office_sha
        ON source_documents (tenant_id, sha256)
        WHERE legal_entity_id IS NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_documents_office_sha")
    op.execute("DROP INDEX IF EXISTS uq_documents_entity_sha")
    op.create_unique_constraint("uq_documents_tenant_sha", "source_documents", ["tenant_id", "sha256"])
