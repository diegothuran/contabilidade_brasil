"""Let a person read their own office memberships."""
from collections.abc import Sequence

from alembic import op

revision: str = "0009_membership_own_select"
down_revision: str | None = "0008_document_requests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_POLICY = """
CREATE POLICY membership_own_select ON memberships
FOR SELECT
USING (
  current_setting('app.user_id', true) <> ''
  AND user_id = current_setting('app.user_id', true)
)
"""


def upgrade() -> None:
    op.execute(_POLICY)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS membership_own_select ON memberships")
