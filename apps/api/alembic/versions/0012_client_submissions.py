"""A document the client sends before the office opens a request."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_client_submissions"
down_revision: str | None = "0011_portal_collaboration"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "client_submissions",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("legal_entity_id", sa.String(160), sa.ForeignKey("legal_entities.id"), nullable=False),
        sa.Column("document_id", sa.String(160), sa.ForeignKey("source_documents.id"), nullable=False),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("submitted_by", sa.String(160), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("classified_request_id", sa.String(160), sa.ForeignKey("document_requests.id"), nullable=True),
        sa.Column("discard_reason", sa.String(2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('new', 'classified', 'discarded')", name="ck_client_submissions_status"),
    )
    op.execute("ALTER TABLE client_submissions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE client_submissions FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON client_submissions
        USING (tenant_id = current_setting('app.tenant_id', true))
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true))
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'contabil_app') THEN
            GRANT SELECT, INSERT, UPDATE ON client_submissions TO contabil_app;
          END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON client_submissions")
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'contabil_app') THEN
            REVOKE SELECT, INSERT, UPDATE ON client_submissions FROM contabil_app;
          END IF;
        END
        $$;
        """
    )
    op.drop_table("client_submissions")
