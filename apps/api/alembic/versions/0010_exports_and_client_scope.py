"""Operational export and the company bound to a client login."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_exports_and_client_scope"
down_revision: str | None = "0009_membership_own_select"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_GRANT_SQL = """
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'contabil_app') THEN
    GRANT SELECT, INSERT, UPDATE ON operational_exports TO contabil_app;
  END IF;
END
$$;
"""

_REVOKE_SQL = """
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'contabil_app') THEN
    REVOKE SELECT, INSERT, UPDATE ON operational_exports FROM contabil_app;
  END IF;
END
$$;
"""


def upgrade() -> None:
    op.add_column("memberships", sa.Column("legal_entity_id", sa.String(160), nullable=True))
    op.create_foreign_key(
        "fk_memberships_legal_entity",
        "memberships",
        "legal_entities",
        ["legal_entity_id"],
        ["id"],
    )
    op.execute(
        """
        ALTER TABLE memberships
        ADD CONSTRAINT ck_memberships_client_scope
        CHECK (
          NOT ('client' = ANY(roles))
          OR (legal_entity_id IS NOT NULL AND roles = ARRAY['client']::character varying(40)[])
        )
        """
    )
    op.create_table(
        "operational_exports",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("legal_entity_id", sa.String(160), sa.ForeignKey("legal_entities.id"), nullable=False),
        sa.Column("period_id", sa.String(80), sa.ForeignKey("accounting_periods.id"), nullable=False),
        sa.Column("operation_id", sa.String(160), sa.ForeignKey("operations.id"), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("created_by", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("operation_id", name="uq_operational_exports_operation"),
    )
    op.execute("ALTER TABLE operational_exports ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE operational_exports FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON operational_exports
        USING (tenant_id = current_setting('app.tenant_id', true))
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true))
        """
    )
    op.execute(_GRANT_SQL)


def downgrade() -> None:
    op.execute(_REVOKE_SQL)
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON operational_exports")
    op.drop_table("operational_exports")
    op.execute("ALTER TABLE memberships DROP CONSTRAINT IF EXISTS ck_memberships_client_scope")
    op.drop_constraint("fk_memberships_legal_entity", "memberships", type_="foreignkey")
    op.drop_column("memberships", "legal_entity_id")
