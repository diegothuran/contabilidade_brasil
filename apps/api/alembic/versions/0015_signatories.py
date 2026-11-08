"""Professional registration (CRC) of office users and the signatories of each company (ADR 030)."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_signatories"
down_revision: str | None = "0014_closing_source"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("professional_registrations", "entity_signatories")


def _secure(table: str) -> None:
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
            GRANT SELECT, INSERT, UPDATE ON {table} TO contabil_app;
          END IF;
        END
        $$;
        """
    )


def upgrade() -> None:
    op.create_table(
        "professional_registrations",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", sa.String(160), sa.ForeignKey("app_users.id"), nullable=False),
        sa.Column("cpf", sa.String(11), nullable=False),
        sa.Column("crc_uf", sa.String(2), nullable=False),
        sa.Column("crc_number", sa.String(20), nullable=False),
        sa.Column("crc_category", sa.String(20), nullable=False),
        sa.Column("regularity_number", sa.String(40), nullable=True),
        sa.Column("regularity_valid_until", sa.Date(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_professional_registrations_user"),
        sa.CheckConstraint("crc_category IN ('contador', 'tecnico')", name="ck_professional_registrations_category"),
    )
    op.create_table(
        "entity_signatories",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("legal_entity_id", sa.String(160), sa.ForeignKey("legal_entities.id"), nullable=False),
        sa.Column("accountant_user_id", sa.String(160), sa.ForeignKey("app_users.id"), nullable=True),
        sa.Column("legal_rep_name", sa.String(200), nullable=True),
        sa.Column("legal_rep_cpf", sa.String(11), nullable=True),
        sa.Column("legal_rep_role", sa.String(40), nullable=True),
        sa.Column("updated_by", sa.String(160), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("legal_entity_id", name="uq_entity_signatories_entity"),
    )
    for table in TABLES:
        _secure(table)


def downgrade() -> None:
    for table in reversed(TABLES):
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
