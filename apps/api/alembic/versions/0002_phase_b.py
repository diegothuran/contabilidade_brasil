"""Phase B documents and import batches."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_phase_b"
down_revision: str | None = "0001_phase_a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "source_documents",
    "import_batches",
    "import_batch_files",
    "import_rows",
    "external_refs",
    "import_batch_journals",
    "import_reports",
    "operations",
)


def upgrade() -> None:
    op.create_table(
        "source_documents",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("schema_version", sa.String(20), nullable=False),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("legal_entity_id", sa.String(160), sa.ForeignKey("legal_entities.id"), nullable=True),
        sa.Column("document_type", sa.String(40), nullable=False),
        sa.Column("competence", sa.String(7), nullable=True),
        sa.Column("file_name", sa.String(300), nullable=False),
        sa.Column("media_type", sa.String(160), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("object_ref", sa.String(1000), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("source_ref", sa.String(300), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_by", sa.String(160), nullable=True),
        sa.Column("retention_policy_id", sa.String(160), nullable=False),
        sa.Column("legal_hold", sa.Boolean(), nullable=False),
        sa.Column("retain_until", sa.Date(), nullable=True),
        sa.Column("classification", sa.String(160), nullable=True),
        sa.Column("derived_versions", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "document_type IN ('invoice', 'bank_statement', 'receipt', 'contract', 'tax_file', 'government_response', 'journal_support', 'other')",
            name="ck_documents_type",
        ),
        sa.CheckConstraint(
            "source_type IN ('upload', 'email', 'api', 'government', 'import', 'generated')",
            name="ck_documents_source",
        ),
        sa.UniqueConstraint("tenant_id", "sha256", name="uq_documents_tenant_sha"),
    )
    op.create_table(
        "import_batches",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("schema_version", sa.String(20), nullable=False),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("legal_entity_id", sa.String(160), sa.ForeignKey("legal_entities.id"), nullable=False),
        sa.Column("source_system", sa.String(160), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=True),
        sa.Column("period_id", sa.String(80), sa.ForeignKey("accounting_periods.id"), nullable=True),
        sa.Column("created_by", sa.String(160), nullable=False),
        sa.Column("published_by", sa.String(160), nullable=True),
        sa.Column("rows_received", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_valid", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rows_invalid", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("debit_total", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("credit_total", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("difference", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("reconciliation_report_id", sa.String(160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("mode IN ('dry_run', 'publish', 'rollback')", name="ck_batches_mode"),
        sa.CheckConstraint(
            "status IN ('received', 'validating', 'ready', 'published', 'partially_published', 'failed', 'rolled_back')",
            name="ck_batches_status",
        ),
    )
    op.create_table(
        "import_batch_files",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("batch_id", sa.String(160), sa.ForeignKey("import_batches.id"), nullable=False),
        sa.Column("document_id", sa.String(160), sa.ForeignKey("source_documents.id"), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.CheckConstraint(
            "kind IN ('chart_of_accounts', 'opening_balance', 'journal', 'customer', 'supplier', 'bank', 'xml', 'other')",
            name="ck_batch_files_kind",
        ),
    )
    op.create_table(
        "import_rows",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("batch_id", sa.String(160), sa.ForeignKey("import_batches.id"), nullable=False),
        sa.Column("file_id", sa.String(160), sa.ForeignKey("import_batch_files.id"), nullable=False),
        sa.Column("row_no", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(200), nullable=True),
        sa.Column("raw", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("error_message", sa.String(1000), nullable=True),
        sa.CheckConstraint("status IN ('valid', 'invalid', 'already_imported')", name="ck_import_rows_status"),
    )
    op.create_table(
        "external_refs",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("source_system", sa.String(160), nullable=False),
        sa.Column("entity_type", sa.String(40), nullable=False),
        sa.Column("external_id", sa.String(200), nullable=False),
        sa.Column("internal_id", sa.String(160), nullable=False),
        sa.Column("batch_id", sa.String(160), sa.ForeignKey("import_batches.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "source_system", "entity_type", "external_id", name="uq_external_refs"),
    )
    op.create_table(
        "import_batch_journals",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("batch_id", sa.String(160), sa.ForeignKey("import_batches.id"), nullable=False),
        sa.Column("journal_id", sa.String(160), sa.ForeignKey("journal_entries.id"), nullable=False),
        sa.Column("external_id", sa.String(200), nullable=False),
    )
    op.create_table(
        "import_reports",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("batch_id", sa.String(160), sa.ForeignKey("import_batches.id"), nullable=False),
        sa.Column("rows", postgresql.JSONB(), nullable=False),
        sa.Column("debit_total", sa.Numeric(20, 6), nullable=False),
        sa.Column("credit_total", sa.Numeric(20, 6), nullable=False),
        sa.Column("difference", sa.Numeric(20, 6), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("batch_id", name="uq_import_reports_batch"),
    )
    op.create_table(
        "operations",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("kind", sa.String(80), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("correlation_id", sa.String(80), nullable=False),
        sa.Column("target_ref", sa.String(200), nullable=False),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('accepted', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_operations_status",
        ),
    )
    op.add_column("outbox_events", sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("outbox_events", sa.Column("last_error", sa.String(500), nullable=True))
    op.add_column("outbox_events", sa.Column("dead_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("DROP INDEX IF EXISTS ix_outbox_pending")
    op.execute(
        "CREATE INDEX ix_outbox_pending ON outbox_events (created_at) WHERE dispatched_at IS NULL AND dead_at IS NULL"
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
    op.execute("DROP FUNCTION IF EXISTS guard_source_document() CASCADE")
    op.execute("DROP INDEX IF EXISTS ix_outbox_pending")
    op.drop_column("outbox_events", "dead_at")
    op.drop_column("outbox_events", "last_error")
    op.drop_column("outbox_events", "attempts")
    op.execute("CREATE INDEX ix_outbox_pending ON outbox_events (created_at) WHERE dispatched_at IS NULL")


_TRIGGER_SQL = """
CREATE OR REPLACE FUNCTION guard_source_document() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'source document is immutable';
  END IF;
  IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
     OR NEW.schema_version IS DISTINCT FROM OLD.schema_version
     OR NEW.sha256 IS DISTINCT FROM OLD.sha256
     OR NEW.object_ref IS DISTINCT FROM OLD.object_ref
     OR NEW.file_name IS DISTINCT FROM OLD.file_name
     OR NEW.media_type IS DISTINCT FROM OLD.media_type
     OR NEW.size_bytes IS DISTINCT FROM OLD.size_bytes
     OR NEW.document_type IS DISTINCT FROM OLD.document_type
     OR NEW.legal_entity_id IS DISTINCT FROM OLD.legal_entity_id
     OR NEW.competence IS DISTINCT FROM OLD.competence
     OR NEW.source_type IS DISTINCT FROM OLD.source_type
     OR NEW.source_ref IS DISTINCT FROM OLD.source_ref
     OR NEW.received_at IS DISTINCT FROM OLD.received_at
     OR NEW.received_by IS DISTINCT FROM OLD.received_by
  THEN
    RAISE EXCEPTION 'source document is immutable';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER source_documents_guard
BEFORE UPDATE OR DELETE ON source_documents
FOR EACH ROW
EXECUTE FUNCTION guard_source_document();
"""

_GRANT_SQL = """
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'contabil_app') THEN
    GRANT SELECT, INSERT ON source_documents, import_rows, import_batch_files, import_batch_journals, import_reports, external_refs TO contabil_app;
    GRANT UPDATE (classification, derived_versions, retention_policy_id, legal_hold, retain_until) ON source_documents TO contabil_app;
    GRANT SELECT, INSERT, UPDATE ON import_batches, operations TO contabil_app;
  END IF;
END
$$;
"""
