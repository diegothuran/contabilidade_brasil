"""Let the app role insert the office membership created by an admin invite."""
from collections.abc import Sequence

from alembic import op

revision: str = "0006_user_invite"
down_revision: str | None = "0005_legal_entity_create"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_GRANT_SQL = """
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'contabil_app') THEN
    GRANT INSERT ON app_users, memberships TO contabil_app;
  END IF;
END
$$;
"""

_REVOKE_SQL = """
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'contabil_app') THEN
    REVOKE INSERT ON app_users, memberships FROM contabil_app;
  END IF;
END
$$;
"""


def upgrade() -> None:
    op.execute(_GRANT_SQL)


def downgrade() -> None:
    op.execute(_REVOKE_SQL)
