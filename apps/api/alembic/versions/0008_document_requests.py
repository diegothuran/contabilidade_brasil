"""Document requests for a competence."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_document_requests"
down_revision: str | None = "0007_close_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_GRANT_SQL = """
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'contabil_app') THEN
    GRANT SELECT, INSERT, UPDATE ON document_requests TO contabil_app;
  END IF;
END
$$;
"""

_REVOKE_SQL = """
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'contabil_app') THEN
    REVOKE SELECT, INSERT, UPDATE ON document_requests FROM contabil_app;
  END IF;
END
$$;
"""


def upgrade() -> None:
    op.create_table(
        "document_requests",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("legal_entity_id", sa.String(160), sa.ForeignKey("legal_entities.id"), nullable=False),
        sa.Column("period_id", sa.String(80), sa.ForeignKey("accounting_periods.id"), nullable=False),
        sa.Column("document_type", sa.String(40), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("document_id", sa.String(160), sa.ForeignKey("source_documents.id"), nullable=True),
        sa.Column("requested_by", sa.String(160), nullable=False),
        sa.Column("received_by", sa.String(160), nullable=True),
        sa.Column("confirmed_by", sa.String(160), nullable=True),
        sa.Column("cancelled_by", sa.String(160), nullable=True),
        sa.Column("cancel_reason", sa.String(2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('open', 'received', 'confirmed', 'cancelled')",
            name="ck_document_requests_status",
        ),
    )
    op.execute("ALTER TABLE document_requests ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE document_requests FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON document_requests
        USING (tenant_id = current_setting('app.tenant_id', true))
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true))
        """
    )
    op.execute(_GRANT_SQL)


def downgrade() -> None:
    op.execute(_REVOKE_SQL)
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON document_requests")
    op.drop_table("document_requests")
