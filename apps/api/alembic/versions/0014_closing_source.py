"""Year-end closing journals get their own source type."""
from collections.abc import Sequence

from alembic import op

revision: str = "0014_closing_source"
down_revision: str | None = "0013_client_notices"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BEFORE = "'manual', 'import', 'payable', 'receivable', 'bank', 'inventory', 'asset', 'fiscal_document', 'adjustment', 'reversal'"


def upgrade() -> None:
    op.drop_constraint("ck_journals_source", "journal_entries", type_="check")
    op.create_check_constraint("ck_journals_source", "journal_entries", f"source_type IN ({BEFORE}, 'closing')")


def downgrade() -> None:
    op.drop_constraint("ck_journals_source", "journal_entries", type_="check")
    op.create_check_constraint("ck_journals_source", "journal_entries", f"source_type IN ({BEFORE})")
