"""Phase A schema. SQL stays inside this module because the repository ignores *.sql files."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_phase_a"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

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
    "outbox_events",
)


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "app_users",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "memberships",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", sa.String(160), sa.ForeignKey("app_users.id"), nullable=False),
        sa.Column("roles", postgresql.ARRAY(sa.String(40)), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_memberships_tenant_user"),
    )
    op.create_table(
        "legal_entities",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("cnpj", sa.String(14), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "establishments",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("legal_entity_id", sa.String(160), sa.ForeignKey("legal_entities.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "charts_of_accounts",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("legal_entity_id", sa.String(160), sa.ForeignKey("legal_entities.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("legal_entity_id", name="uq_charts_entity"),
    )
    op.create_table(
        "accounts",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("legal_entity_id", sa.String(160), sa.ForeignKey("legal_entities.id"), nullable=False),
        sa.Column("chart_id", sa.String(160), sa.ForeignKey("charts_of_accounts.id"), nullable=False),
        sa.Column("parent_id", sa.String(160), sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("account_type", sa.String(20), nullable=False),
        sa.Column("postable", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("account_type IN ('asset', 'liability', 'equity', 'revenue', 'expense')", name="ck_accounts_type"),
        sa.UniqueConstraint("legal_entity_id", "code", name="uq_accounts_entity_code"),
    )
    op.create_table(
        "cost_centers",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("legal_entity_id", sa.String(160), sa.ForeignKey("legal_entities.id"), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("legal_entity_id", "code", name="uq_cost_centers_entity_code"),
    )
    op.create_table(
        "accounting_periods",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("legal_entity_id", sa.String(160), sa.ForeignKey("legal_entities.id"), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('open', 'closing', 'closed', 'reopened')", name="ck_periods_status"),
        sa.CheckConstraint("month BETWEEN 1 AND 12", name="ck_periods_month"),
        sa.UniqueConstraint("legal_entity_id", "fiscal_year", "month", name="uq_periods_entity_month"),
    )
    op.create_table(
        "reopen_requests",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("period_id", sa.String(80), sa.ForeignKey("accounting_periods.id"), nullable=False),
        sa.Column("reason", sa.String(2000), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("requested_by", sa.String(160), nullable=False),
        sa.Column("approved_by", sa.String(160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_reopen_status"),
    )
    op.create_table(
        "journal_entries",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("schema_version", sa.String(20), nullable=False),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("legal_entity_id", sa.String(160), sa.ForeignKey("legal_entities.id"), nullable=False),
        sa.Column("period_id", sa.String(80), sa.ForeignKey("accounting_periods.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(2000), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("source_id", sa.String(200), nullable=False),
        sa.Column("source_hash", sa.String(128), nullable=True),
        sa.Column("reverses_journal_id", sa.String(160), sa.ForeignKey("journal_entries.id"), nullable=True),
        sa.Column("reversal_journal_id", sa.String(160), sa.ForeignKey("journal_entries.id"), nullable=True),
        sa.Column("created_by", sa.String(160), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by", sa.String(160), nullable=True),
        sa.Column("audit_event_id", sa.String(160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'pending_approval', 'approved', 'published', 'reversed', 'rejected')",
            name="ck_journals_status",
        ),
        sa.CheckConstraint(
            "source_type IN ('manual', 'import', 'payable', 'receivable', 'bank', 'inventory', 'asset', 'fiscal_document', 'adjustment', 'reversal')",
            name="ck_journals_source",
        ),
    )
    op.create_table(
        "journal_lines",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("journal_id", sa.String(160), sa.ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.String(160), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("description", sa.String(1000), nullable=False),
        sa.Column("cost_center_id", sa.String(160), sa.ForeignKey("cost_centers.id"), nullable=True),
        sa.Column("dimension_values", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("side IN ('debit', 'credit')", name="ck_lines_side"),
        sa.CheckConstraint("amount > 0", name="ck_lines_amount"),
        sa.UniqueConstraint("journal_id", "line_no", name="uq_lines_journal_no"),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("schema_version", sa.String(20), nullable=False),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("actor_kind", sa.String(20), nullable=False),
        sa.Column("actor_ref", sa.String(160), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("target_type", sa.String(120), nullable=False),
        sa.Column("target_ref", sa.String(200), nullable=False),
        sa.Column("reason", sa.String(2000), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.Column("event_hash", sa.String(200), nullable=False),
        sa.Column("previous_hash", sa.String(200), nullable=True),
        sa.CheckConstraint(
            "event_type IN ('journal_created', 'journal_published', 'journal_reversed', 'period_reopened', 'reconciliation_approved', 'import_published', 'document_exported', 'permission_changed', 'obligation_transmitted', 'certificate_used', 'login', 'other')",
            name="ck_audit_type",
        ),
    )
    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_body", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "key", name="uq_idempotency_tenant_key"),
    )
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_journals_tenant_entity_period", "journal_entries", ["tenant_id", "legal_entity_id", "period_id", "status"])
    op.create_index("ix_lines_journal", "journal_lines", ["journal_id"])
    op.create_index("ix_lines_account", "journal_lines", ["tenant_id", "account_id"])
    op.create_index("ix_audit_tenant_time", "audit_events", ["tenant_id", "occurred_at", "id"])
    op.execute("CREATE INDEX ix_outbox_pending ON outbox_events (created_at) WHERE dispatched_at IS NULL")
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
    for table in reversed(
        [
            "outbox_events",
            "idempotency_keys",
            "audit_events",
            "journal_lines",
            "journal_entries",
            "reopen_requests",
            "accounting_periods",
            "cost_centers",
            "accounts",
            "charts_of_accounts",
            "establishments",
            "legal_entities",
            "memberships",
            "app_users",
            "tenants",
        ]
    ):
        op.drop_table(table)
    op.execute("DROP FUNCTION IF EXISTS assert_journal_balanced() CASCADE")
    op.execute("DROP FUNCTION IF EXISTS guard_journal_line() CASCADE")
    op.execute("DROP FUNCTION IF EXISTS guard_journal_entry() CASCADE")
    op.execute("DROP FUNCTION IF EXISTS audit_append_only() CASCADE")


_TRIGGER_SQL = """
CREATE OR REPLACE FUNCTION guard_journal_entry() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF OLD.status IN ('published', 'reversed') THEN
      RAISE EXCEPTION 'published journal is immutable';
    END IF;
    RETURN OLD;
  END IF;
  IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id THEN
    RAISE EXCEPTION 'published journal is immutable';
  END IF;
  IF OLD.status = 'reversed' THEN
    RAISE EXCEPTION 'published journal is immutable';
  END IF;
  IF OLD.status = 'published' THEN
    IF NEW.status = 'reversed'
       AND NEW.reversal_journal_id IS NOT NULL
       AND OLD.reversal_journal_id IS NULL
       AND NEW.schema_version IS NOT DISTINCT FROM OLD.schema_version
       AND NEW.legal_entity_id IS NOT DISTINCT FROM OLD.legal_entity_id
       AND NEW.period_id IS NOT DISTINCT FROM OLD.period_id
       AND NEW.currency IS NOT DISTINCT FROM OLD.currency
       AND NEW.entry_date IS NOT DISTINCT FROM OLD.entry_date
       AND NEW.description IS NOT DISTINCT FROM OLD.description
       AND NEW.source_type IS NOT DISTINCT FROM OLD.source_type
       AND NEW.source_id IS NOT DISTINCT FROM OLD.source_id
       AND NEW.source_hash IS NOT DISTINCT FROM OLD.source_hash
       AND NEW.reverses_journal_id IS NOT DISTINCT FROM OLD.reverses_journal_id
       AND NEW.created_by IS NOT DISTINCT FROM OLD.created_by
       AND NEW.published_at IS NOT DISTINCT FROM OLD.published_at
       AND NEW.published_by IS NOT DISTINCT FROM OLD.published_by
       AND NEW.audit_event_id IS NOT DISTINCT FROM OLD.audit_event_id
       AND NEW.created_at IS NOT DISTINCT FROM OLD.created_at
    THEN
      RETURN NEW;
    END IF;
    RAISE EXCEPTION 'published journal is immutable';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER journal_entries_guard
BEFORE UPDATE OR DELETE ON journal_entries
FOR EACH ROW
EXECUTE FUNCTION guard_journal_entry();

CREATE OR REPLACE FUNCTION guard_journal_line() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  journal_status text;
  target_journal text;
BEGIN
  target_journal := COALESCE(NEW.journal_id, OLD.journal_id);
  SELECT status INTO journal_status FROM journal_entries WHERE id = target_journal;
  IF journal_status IN ('published', 'reversed') THEN
    RAISE EXCEPTION 'published journal is immutable';
  END IF;
  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER journal_lines_guard
BEFORE INSERT OR UPDATE OR DELETE ON journal_lines
FOR EACH ROW
EXECUTE FUNCTION guard_journal_line();

CREATE OR REPLACE FUNCTION assert_journal_balanced() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  target_id text;
  journal_status text;
  debit_total numeric(20, 6);
  credit_total numeric(20, 6);
  line_count integer;
BEGIN
  IF TG_TABLE_NAME = 'journal_lines' THEN
    target_id := COALESCE(NEW.journal_id, OLD.journal_id);
  ELSE
    target_id := COALESCE(NEW.id, OLD.id);
  END IF;
  SELECT status INTO journal_status FROM journal_entries WHERE id = target_id;
  IF journal_status IS NULL OR journal_status NOT IN ('published', 'reversed') THEN
    RETURN NULL;
  END IF;
  SELECT
    COALESCE(SUM(amount) FILTER (WHERE side = 'debit'), 0),
    COALESCE(SUM(amount) FILTER (WHERE side = 'credit'), 0),
    COUNT(*)
  INTO debit_total, credit_total, line_count
  FROM journal_lines
  WHERE journal_id = target_id;
  IF line_count < 2 OR debit_total <> credit_total THEN
    RAISE EXCEPTION 'journal is not balanced';
  END IF;
  RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER journal_entries_balanced
AFTER INSERT OR UPDATE ON journal_entries
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION assert_journal_balanced();

CREATE CONSTRAINT TRIGGER journal_lines_balanced
AFTER INSERT OR UPDATE OR DELETE ON journal_lines
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION assert_journal_balanced();

CREATE OR REPLACE FUNCTION audit_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'audit events are append-only';
END;
$$;

CREATE TRIGGER audit_events_append_only
BEFORE UPDATE OR DELETE ON audit_events
FOR EACH ROW
EXECUTE FUNCTION audit_append_only();
"""

_GRANT_SQL = """
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'contabil_app') THEN
    GRANT USAGE ON SCHEMA public TO contabil_app;
    GRANT SELECT ON tenants, app_users TO contabil_app;
    GRANT SELECT ON memberships, legal_entities, establishments, charts_of_accounts, cost_centers TO contabil_app;
    GRANT SELECT, INSERT ON accounts, journal_lines, audit_events, idempotency_keys, outbox_events TO contabil_app;
    GRANT SELECT, INSERT, UPDATE ON journal_entries, accounting_periods, reopen_requests TO contabil_app;
  END IF;
END
$$;
"""
