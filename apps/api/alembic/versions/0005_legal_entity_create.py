"""Let the app role create a company and keep the CNPJ unique per office."""
from collections.abc import Sequence

from alembic import op

revision: str = "0005_legal_entity_create"
down_revision: str | None = "0004_force_rls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_GRANT_SQL = """
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'contabil_app') THEN
    GRANT INSERT ON legal_entities, establishments, charts_of_accounts TO contabil_app;
  END IF;
END
$$;
"""

_REVOKE_SQL = """
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'contabil_app') THEN
    REVOKE INSERT ON legal_entities, establishments, charts_of_accounts FROM contabil_app;
  END IF;
END
$$;
"""


def upgrade() -> None:
    op.create_unique_constraint("uq_legal_entities_tenant_cnpj", "legal_entities", ["tenant_id", "cnpj"])
    op.execute(_GRANT_SQL)


def downgrade() -> None:
    op.execute(_REVOKE_SQL)
    op.drop_constraint("uq_legal_entities_tenant_cnpj", "legal_entities", type_="unique")
