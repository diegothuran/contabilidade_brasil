"""Sugestão de contrapartida por modelo de linguagem e custo por lote, só de inserção (ADR 035)."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023_account_suggestions"
down_revision: str | None = "0021_journal_line_guards"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SUGGESTIONS = "account_suggestions"
RUNS = "suggestion_runs"


def _protect(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON {table}
        USING (tenant_id = current_setting('app.tenant_id', true))
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true))
        """
    )
    op.execute(
        f"""
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'contabil_app') THEN
            GRANT SELECT, INSERT ON {table} TO contabil_app;
          END IF;
        END
        $$;
        """
    )


def _unprotect(table: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
    op.execute(
        f"""
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'contabil_app') THEN
            REVOKE SELECT, INSERT ON {table} FROM contabil_app;
          END IF;
        END
        $$;
        """
    )


def upgrade() -> None:
    op.create_table(
        SUGGESTIONS,
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("legal_entity_id", sa.String(160), sa.ForeignKey("legal_entities.id"), nullable=False),
        sa.Column("case_id", sa.String(160), sa.ForeignKey("reconciliation_cases.id"), nullable=False),
        sa.Column("account_id", sa.String(160), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("confidence", sa.String(10), nullable=False),
        sa.Column("justification", sa.String(300), nullable=False),
        sa.Column("source", sa.String(10), nullable=False),
        sa.Column("provider_version", sa.String(120), nullable=False),
        sa.Column("operation_id", sa.String(160), sa.ForeignKey("operations.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("confidence IN ('alta', 'média', 'baixa')", name="ck_account_suggestions_confidence"),
        sa.CheckConstraint("source IN ('model')", name="ck_account_suggestions_source"),
    )
    op.create_index("ix_account_suggestions_case", SUGGESTIONS, ["tenant_id", "case_id", "created_at"])
    _protect(SUGGESTIONS)
    op.create_table(
        RUNS,
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("operation_id", sa.String(160), sa.ForeignKey("operations.id"), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("prompt_version", sa.String(40), nullable=False),
        sa.Column("transactions_sent", sa.Integer(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("stop_reason", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("transactions_sent >= 0", name="ck_suggestion_runs_sent"),
    )
    op.create_index("ix_suggestion_runs_day", RUNS, ["tenant_id", "created_at"])
    _protect(RUNS)


def downgrade() -> None:
    _unprotect(RUNS)
    op.drop_index("ix_suggestion_runs_day", table_name=RUNS)
    op.drop_table(RUNS)
    _unprotect(SUGGESTIONS)
    op.drop_index("ix_account_suggestions_case", table_name=SUGGESTIONS)
    op.drop_table(SUGGESTIONS)
