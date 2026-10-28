"""Client notice log and the preference to receive mail."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_client_notices"
down_revision: str | None = "0012_client_submissions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "memberships",
        sa.Column("notify_client", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "notification_log",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("request_id", sa.String(160), sa.ForeignKey("document_requests.id"), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("notice_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("request_id", "kind", "notice_date", name="uq_notification_log_once"),
    )
    op.execute("ALTER TABLE notification_log ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE notification_log FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON notification_log
        USING (tenant_id = current_setting('app.tenant_id', true))
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true))
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'contabil_app') THEN
            GRANT SELECT, INSERT ON notification_log TO contabil_app;
          END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON notification_log")
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'contabil_app') THEN
            REVOKE SELECT, INSERT ON notification_log FROM contabil_app;
          END IF;
        END
        $$;
        """
    )
    op.drop_table("notification_log")
    op.drop_column("memberships", "notify_client")
