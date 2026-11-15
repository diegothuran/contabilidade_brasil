"""Resumo do mês para o empresário, publicado pelo escritório (ADR 034)."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022_client_summaries"
down_revision: str | None = "0021_journal_line_guards"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "client_summaries"

_GUARD = """
CREATE OR REPLACE FUNCTION guard_client_summary() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'client summary cannot be deleted';
  END IF;
  IF OLD.status <> 'draft' AND NEW.payload IS DISTINCT FROM OLD.payload THEN
    RAISE EXCEPTION 'published client summary payload is immutable';
  END IF;
  RETURN NEW;
END;
$$;
"""


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("legal_entity_id", sa.String(160), sa.ForeignKey("legal_entities.id"), nullable=False),
        sa.Column("period_id", sa.String(160), sa.ForeignKey("accounting_periods.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_by", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_by", sa.String(160), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("withdrawn_reason", sa.String(500), nullable=True),
        sa.CheckConstraint("status IN ('draft', 'published', 'withdrawn')", name="ck_client_summaries_status"),
    )
    op.create_index(
        "uq_client_summaries_period",
        TABLE,
        ["tenant_id", "period_id"],
        unique=True,
        postgresql_where=sa.text("status <> 'withdrawn'"),
    )
    op.create_index("ix_client_summaries_entity", TABLE, ["tenant_id", "legal_entity_id", "status"])
    op.execute(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON {TABLE}
        USING (tenant_id = current_setting('app.tenant_id', true))
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true))
        """
    )
    op.execute(
        f"""
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'contabil_app') THEN
            GRANT SELECT, INSERT, UPDATE ON {TABLE} TO contabil_app;
          END IF;
        END
        $$;
        """
    )
    op.execute(_GUARD)
    op.execute(
        f"CREATE TRIGGER guard_client_summary BEFORE UPDATE OR DELETE ON {TABLE} "
        "FOR EACH ROW EXECUTE FUNCTION guard_client_summary()"
    )


def downgrade() -> None:
    op.execute(f"DROP TRIGGER IF EXISTS guard_client_summary ON {TABLE}")
    op.execute("DROP FUNCTION IF EXISTS guard_client_summary()")
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {TABLE}")
    op.execute(
        f"""
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'contabil_app') THEN
            REVOKE SELECT, INSERT, UPDATE ON {TABLE} FROM contabil_app;
          END IF;
        END
        $$;
        """
    )
    op.drop_index("ix_client_summaries_entity", table_name=TABLE)
    op.drop_index("uq_client_summaries_period", table_name=TABLE)
    op.drop_table(TABLE)
