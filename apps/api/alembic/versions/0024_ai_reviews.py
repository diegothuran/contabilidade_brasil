"""Revisão do mês por IA: revisão, pontos e decisões (ADR 036)."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0024_ai_reviews"
down_revision: str | None = "0023_account_suggestions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REVIEWS = "ai_reviews"
FINDINGS = "ai_review_findings"
DECISIONS = "ai_review_decisions"
# O worker muda o estado da revisão; pontos e decisões são só de inserção.
GRANTS = {REVIEWS: "SELECT, INSERT, UPDATE", FINDINGS: "SELECT, INSERT", DECISIONS: "SELECT, INSERT"}


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
            GRANT {GRANTS[table]} ON {table} TO contabil_app;
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
            REVOKE {GRANTS[table]} ON {table} FROM contabil_app;
          END IF;
        END
        $$;
        """
    )


def upgrade() -> None:
    op.create_table(
        REVIEWS,
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("legal_entity_id", sa.String(160), sa.ForeignKey("legal_entities.id"), nullable=False),
        sa.Column("period_id", sa.String(160), sa.ForeignKey("accounting_periods.id"), nullable=False),
        sa.Column("operation_id", sa.String(160), sa.ForeignKey("operations.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("prompt_version", sa.String(40), nullable=False),
        sa.Column("packet_version", sa.String(40), nullable=False),
        sa.Column("input_sha256", sa.String(64), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stop_reason", sa.String(40), nullable=True),
        sa.Column("requested_by", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('requested', 'completed', 'incomplete', 'failed')", name="ck_ai_reviews_status"),
    )
    op.create_index("ix_ai_reviews_period", REVIEWS, ["tenant_id", "period_id", "created_at"])
    op.create_index("ix_ai_reviews_day", REVIEWS, ["tenant_id", "created_at"])
    _protect(REVIEWS)
    op.create_table(
        FINDINGS,
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("review_id", sa.String(160), sa.ForeignKey("ai_reviews.id"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("relevance", sa.String(10), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("explanation", sa.String(600), nullable=False),
        sa.Column("evidence", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("relevance IN ('alta', 'média', 'baixa')", name="ck_ai_review_findings_relevance"),
    )
    op.create_index("ix_ai_review_findings_review", FINDINGS, ["tenant_id", "review_id", "position"])
    _protect(FINDINGS)
    op.create_table(
        DECISIONS,
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("finding_id", sa.String(160), sa.ForeignKey("ai_review_findings.id"), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("decided_by", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("decision IN ('procede', 'nao_procede')", name="ck_ai_review_decisions_decision"),
    )
    op.create_index("ix_ai_review_decisions_finding", DECISIONS, ["tenant_id", "finding_id", "created_at"])
    _protect(DECISIONS)


def downgrade() -> None:
    for table, index in (
        (DECISIONS, "ix_ai_review_decisions_finding"),
        (FINDINGS, "ix_ai_review_findings_review"),
    ):
        _unprotect(table)
        op.drop_index(index, table_name=table)
        op.drop_table(table)
    _unprotect(REVIEWS)
    op.drop_index("ix_ai_reviews_day", table_name=REVIEWS)
    op.drop_index("ix_ai_reviews_period", table_name=REVIEWS)
    op.drop_table(REVIEWS)
