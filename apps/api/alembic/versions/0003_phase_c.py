"""Phase C bank statements and reconciliation cases."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_phase_c"
down_revision: str | None = "0002_phase_b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "bank_accounts",
    "bank_statements",
    "bank_transactions",
    "reconciliation_cases",
    "reconciliation_matches",
)

_TRIGGER_SQL = """
CREATE OR REPLACE FUNCTION guard_bank_transaction() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'bank transaction is immutable';
END;
$$;

CREATE TRIGGER bank_transactions_guard
BEFORE UPDATE OR DELETE ON bank_transactions
FOR EACH ROW
EXECUTE FUNCTION guard_bank_transaction();
"""

_GRANT_SQL = """
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'contabil_app') THEN
    GRANT SELECT, INSERT, UPDATE ON bank_accounts, bank_statements, reconciliation_cases, reconciliation_matches TO contabil_app;
    GRANT SELECT, INSERT ON bank_transactions TO contabil_app;
  END IF;
END
$$;
"""


def upgrade() -> None:
    op.create_table(
        "bank_accounts",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("legal_entity_id", sa.String(160), sa.ForeignKey("legal_entities.id"), nullable=False),
        sa.Column("account_id", sa.String(160), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("bank_code", sa.String(8), nullable=False),
        sa.Column("branch", sa.String(20), nullable=False),
        sa.Column("account_number_masked", sa.String(4), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("legal_entity_id", "account_id", name="uq_bank_accounts_entity_account"),
    )
    op.create_table(
        "bank_statements",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("bank_account_id", sa.String(160), sa.ForeignKey("bank_accounts.id"), nullable=False),
        sa.Column("document_id", sa.String(160), sa.ForeignKey("source_documents.id"), nullable=False),
        sa.Column("format", sa.String(8), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("closing_balance", sa.Numeric(20, 6), nullable=True),
        sa.Column("transactions_received", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("transactions_new", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("transactions_duplicate", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("error_message", sa.String(1000), nullable=True),
        sa.Column("created_by", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("format IN ('csv', 'ofx')", name="ck_bank_statements_format"),
        sa.CheckConstraint("status IN ('received', 'parsed', 'failed')", name="ck_bank_statements_status"),
    )
    op.create_table(
        "bank_transactions",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("bank_account_id", sa.String(160), sa.ForeignKey("bank_accounts.id"), nullable=False),
        sa.Column("statement_id", sa.String(160), sa.ForeignKey("bank_statements.id"), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("description", sa.String(2000), nullable=False),
        sa.Column("external_id", sa.String(200), nullable=True),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_bank_transactions_amount"),
        sa.CheckConstraint("direction IN ('inflow', 'outflow')", name="ck_bank_transactions_direction"),
        sa.UniqueConstraint("bank_account_id", "fingerprint", name="uq_bank_transactions_fingerprint"),
    )
    op.create_table(
        "reconciliation_cases",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("schema_version", sa.String(20), nullable=False),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("bank_account_id", sa.String(160), sa.ForeignKey("bank_accounts.id"), nullable=False),
        sa.Column("account_id", sa.String(160), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("transaction_id", sa.String(160), sa.ForeignKey("bank_transactions.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("candidates", postgresql.JSONB(), nullable=False),
        sa.Column("selected_candidate_id", sa.String(200), nullable=True),
        sa.Column("approved_by", sa.String(160), nullable=True),
        sa.Column("audit_event_id", sa.String(160), nullable=True),
        sa.Column("journal_id", sa.String(160), sa.ForeignKey("journal_entries.id"), nullable=True),
        sa.Column("reason", sa.String(2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('open', 'suggested', 'approved', 'rejected', 'reversed', 'ignored')",
            name="ck_reconciliation_cases_status",
        ),
        sa.UniqueConstraint("transaction_id", name="uq_reconciliation_cases_transaction"),
    )
    op.create_table(
        "reconciliation_matches",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("case_id", sa.String(160), sa.ForeignKey("reconciliation_cases.id"), nullable=False),
        sa.Column("journal_line_id", sa.String(160), sa.ForeignKey("journal_lines.id"), nullable=False),
        sa.Column("amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "uq_reconciliation_matches_active_line",
        "reconciliation_matches",
        ["journal_line_id"],
        unique=True,
        postgresql_where=sa.text("active"),
    )
    op.execute(_TRIGGER_SQL)
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
            USING (tenant_id = current_setting('app.tenant_id', true))
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true))
            """
        )
    op.execute(_GRANT_SQL)


def downgrade() -> None:
    for table in reversed(TENANT_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.drop_table(table)
    op.execute("DROP FUNCTION IF EXISTS guard_bank_transaction() CASCADE")
