"""Close runs, checklist decisions and immutable snapshots."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_close_runs"
down_revision: str | None = "0006_user_invite"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = ("close_runs", "close_run_decisions", "close_snapshots")

_TRIGGER_SQL = """
CREATE OR REPLACE FUNCTION guard_close_snapshot() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'close snapshot is immutable';
END;
$$;

CREATE TRIGGER close_snapshots_guard
BEFORE UPDATE OR DELETE ON close_snapshots
FOR EACH ROW
EXECUTE FUNCTION guard_close_snapshot();
"""

_GRANT_SQL = """
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'contabil_app') THEN
    GRANT SELECT, INSERT, UPDATE ON close_runs, close_run_decisions TO contabil_app;
    GRANT SELECT, INSERT ON close_snapshots TO contabil_app;
  END IF;
END
$$;
"""

_REVOKE_SQL = """
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'contabil_app') THEN
    REVOKE SELECT, INSERT, UPDATE ON close_runs, close_run_decisions FROM contabil_app;
    REVOKE SELECT, INSERT ON close_snapshots FROM contabil_app;
  END IF;
END
$$;
"""


def upgrade() -> None:
    op.create_table(
        "close_runs",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("legal_entity_id", sa.String(160), sa.ForeignKey("legal_entities.id"), nullable=False),
        sa.Column("period_id", sa.String(80), sa.ForeignKey("accounting_periods.id"), nullable=False),
        sa.Column("run_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("checklist_version", sa.String(40), nullable=False),
        sa.Column("closed_by", sa.String(160), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("snapshot_sha256", sa.String(64), nullable=True),
        sa.Column("reopened_reason", sa.String(2000), nullable=True),
        sa.Column("audit_event_id", sa.String(160), nullable=True),
        sa.Column("created_by", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("period_id", "run_number", name="uq_close_runs_period_number"),
        sa.CheckConstraint("status IN ('open', 'closed', 'reopened', 'cancelled')", name="ck_close_runs_status"),
    )
    op.create_table(
        "close_run_decisions",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("close_run_id", sa.String(160), sa.ForeignKey("close_runs.id"), nullable=False),
        sa.Column("item_id", sa.String(160), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("reason", sa.String(2000), nullable=True),
        sa.Column("decided_by", sa.String(160), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("close_run_id", "item_id", name="uq_close_run_decisions_item"),
        sa.CheckConstraint("status IN ('completed', 'not_applicable')", name="ck_close_run_decisions_status"),
    )
    op.create_table(
        "close_snapshots",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("close_run_id", sa.String(160), sa.ForeignKey("close_runs.id"), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("close_run_id", name="uq_close_snapshots_run"),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_close_runs_one_open ON close_runs (period_id) WHERE status = 'open'"
    )
    op.execute(_TRIGGER_SQL)
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
            USING (tenant_id = current_setting('app.tenant_id', true))
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true))
            """
        )
    op.execute(_GRANT_SQL)


def downgrade() -> None:
    op.execute(_REVOKE_SQL)
    op.execute("DROP TRIGGER IF EXISTS close_snapshots_guard ON close_snapshots")
    op.execute("DROP FUNCTION IF EXISTS guard_close_snapshot() CASCADE")
    op.execute("DROP INDEX IF EXISTS uq_close_runs_one_open")
    for table in reversed(TENANT_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.drop_table(table)
