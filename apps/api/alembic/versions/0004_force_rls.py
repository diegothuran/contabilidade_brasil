"""Force row level security for the single pilot credential."""
from collections.abc import Sequence

from alembic import op

revision: str = "0004_force_rls"
down_revision: str | None = "0003_phase_c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# outbox_events stays without FORCE: the relay reads every tenant.
TENANT_TABLES = (
    "memberships",
    "legal_entities",
    "establishments",
    "charts_of_accounts",
    "accounts",
    "cost_centers",
    "accounting_periods",
    "reopen_requests",
    "journal_entries",
    "journal_lines",
    "audit_events",
    "idempotency_keys",
    "source_documents",
    "import_batches",
    "import_batch_files",
    "import_rows",
    "external_refs",
    "import_batch_journals",
    "import_reports",
    "operations",
    "bank_accounts",
    "bank_statements",
    "bank_transactions",
    "reconciliation_cases",
    "reconciliation_matches",
)


def upgrade() -> None:
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
