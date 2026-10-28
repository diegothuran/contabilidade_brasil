"""Files and comments on a document request."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_portal_collaboration"
down_revision: str | None = "0010_exports_and_client_scope"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _grant(table: str) -> str:
    return f"""
    DO $$
    BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'contabil_app') THEN
        GRANT SELECT, INSERT, UPDATE ON {table} TO contabil_app;
      END IF;
    END
    $$;
    """


def _isolate(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON {table}
        USING (tenant_id = current_setting('app.tenant_id', true))
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true))
        """
    )
    op.execute(_grant(table))


def upgrade() -> None:
    op.create_table(
        "document_request_files",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("request_id", sa.String(160), sa.ForeignKey("document_requests.id"), nullable=False),
        sa.Column("document_id", sa.String(160), sa.ForeignKey("source_documents.id"), nullable=False),
        sa.Column("uploaded_by", sa.String(160), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("returned_reason", sa.String(2000), nullable=True),
        sa.CheckConstraint("state IN ('active', 'returned')", name="ck_request_files_state"),
    )
    op.create_index("ix_request_files_request", "document_request_files", ["tenant_id", "request_id"])
    _isolate("document_request_files")
    op.execute(
        """
        INSERT INTO document_request_files (
          id, tenant_id, request_id, document_id, uploaded_by, uploaded_at, state, returned_reason
        )
        SELECT id || '-file', tenant_id, id, document_id,
               COALESCE(received_by, requested_by), updated_at, 'active', NULL
        FROM document_requests
        WHERE document_id IS NOT NULL
        """
    )
    op.create_table(
        "document_request_comments",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("request_id", sa.String(160), sa.ForeignKey("document_requests.id"), nullable=False),
        sa.Column("author_ref", sa.String(160), nullable=False),
        sa.Column("author_kind", sa.String(20), nullable=False),
        sa.Column("body", sa.String(1000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("author_kind IN ('office', 'client')", name="ck_request_comments_kind"),
    )
    op.create_index("ix_request_comments_request", "document_request_comments", ["tenant_id", "request_id"])
    _isolate("document_request_comments")


def downgrade() -> None:
    for table in ("document_request_comments", "document_request_files"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(
            f"""
            DO $$
            BEGIN
              IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'contabil_app') THEN
                REVOKE SELECT, INSERT, UPDATE ON {table} FROM contabil_app;
              END IF;
            END
            $$;
            """
        )
        op.drop_table(table)
