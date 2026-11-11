"""Pagamentos com retenção na fonte, base da prévia da EFD-Reinf R-4000 (ADR 032)."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018_withholding_payments"
down_revision: str | None = "0017_ecd_conversion_date"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "withholding_payments"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("tenant_id", sa.String(160), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("legal_entity_id", sa.String(160), sa.ForeignKey("legal_entities.id"), nullable=False),
        sa.Column("period_id", sa.String(160), sa.ForeignKey("accounting_periods.id"), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("beneficiary_kind", sa.String(2), nullable=False),
        sa.Column("beneficiary_document", sa.String(14), nullable=False),
        sa.Column("beneficiary_name", sa.String(150), nullable=False),
        sa.Column("nature_code", sa.String(5), nullable=False),
        sa.Column("gross_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("ir_base", sa.Numeric(14, 2), nullable=True),
        sa.Column("ir_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("csrf_base", sa.Numeric(14, 2), nullable=True),
        sa.Column("csrf_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("description", sa.String(200), nullable=True),
        sa.Column("created_by", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("beneficiary_kind IN ('pj', 'pf')", name="ck_withholding_payments_kind"),
        sa.CheckConstraint(
            "(beneficiary_kind = 'pf' AND beneficiary_document ~ '^[0-9]{11}$') "
            "OR (beneficiary_kind = 'pj' AND beneficiary_document ~ '^[0-9A-Z]{12}[0-9]{2}$')",
            name="ck_withholding_payments_document",
        ),
        sa.CheckConstraint("nature_code ~ '^[0-9]{5}$'", name="ck_withholding_payments_nature"),
        sa.CheckConstraint("gross_amount > 0", name="ck_withholding_payments_gross"),
        sa.CheckConstraint(
            "ir_amount IS NULL OR (ir_base IS NOT NULL AND ir_amount > 0 AND ir_amount <= ir_base)",
            name="ck_withholding_payments_ir",
        ),
        sa.CheckConstraint("ir_base IS NULL OR ir_base > 0", name="ck_withholding_payments_ir_base"),
        sa.CheckConstraint(
            "(beneficiary_kind = 'pf' AND csrf_base IS NULL AND csrf_amount IS NULL) OR beneficiary_kind = 'pj'",
            name="ck_withholding_payments_csrf_pf",
        ),
        sa.CheckConstraint(
            "csrf_amount IS NULL OR (csrf_base IS NOT NULL AND csrf_amount > 0 AND csrf_amount <= csrf_base)",
            name="ck_withholding_payments_csrf",
        ),
        sa.CheckConstraint("csrf_base IS NULL OR csrf_base > 0", name="ck_withholding_payments_csrf_base"),
    )
    op.create_index("ix_withholding_payments_period", TABLE, ["tenant_id", "legal_entity_id", "period_id"])
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
            GRANT SELECT, INSERT, DELETE ON {TABLE} TO contabil_app;
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
            REVOKE SELECT, INSERT, DELETE ON {TABLE} FROM contabil_app;
          END IF;
        END
        $$;
        """
    )
    op.drop_index("ix_withholding_payments_period", table_name=TABLE)
    op.drop_table(TABLE)
