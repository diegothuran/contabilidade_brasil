"""Data da conversão de sociedade simples em empresária no cadastro da ECD (ADR 031)."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_ecd_conversion_date"
down_revision: str | None = "0016_ecd_registration"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ecd_registrations", sa.Column("conversion_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("ecd_registrations", "conversion_date")
