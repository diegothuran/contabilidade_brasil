"""Dados da escrituração da ECD por empresa (ADR 031)."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_ecd_registration"
down_revision: str | None = "0015_signatories"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "ecd_registrations"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("legal_entity_id", sa.String(160), sa.ForeignKey("legal_entities.id"), nullable=False),
        sa.Column("uf", sa.String(2), nullable=False),
        sa.Column("municipality_ibge", sa.String(7), nullable=False),
        sa.Column("registry_kind", sa.String(20), nullable=False),
        sa.Column("nire", sa.String(11), nullable=True),
        sa.Column("registry_date", sa.Date(), nullable=True),
        sa.Column("special_situation", sa.String(1), nullable=True),
        sa.Column("book_number", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.String(160), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("legal_entity_id", name="uq_ecd_registrations_entity"),
        sa.CheckConstraint("registry_kind IN ('junta', 'cartorio')", name="ck_ecd_registrations_kind"),
        sa.CheckConstraint(
            "(registry_kind = 'junta' AND nire IS NOT NULL) OR (registry_kind = 'cartorio' AND nire IS NULL)",
            name="ck_ecd_registrations_nire",
        ),
        sa.CheckConstraint("municipality_ibge ~ '^[0-9]{7}$'", name="ck_ecd_registrations_municipality"),
        sa.CheckConstraint("nire IS NULL OR nire ~ '^[0-9]{11}$'", name="ck_ecd_registrations_nire_digits"),
        sa.CheckConstraint(
            "special_situation IS NULL OR special_situation IN ('1', '2', '3', '4')", name="ck_ecd_registrations_special"
        ),
        sa.CheckConstraint("book_number > 0", name="ck_ecd_registrations_book"),
    )
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


def downgrade() -> None:
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
    op.drop_table(TABLE)
