"""Linha não troca de journal e TRUNCATE não apaga livro nem trilha de auditoria."""
from collections.abc import Sequence

from alembic import op

revision: str = "0021_journal_line_guards"
down_revision: str | None = "0020_documents_entity_sha"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_GUARDED = ("audit_events", "journal_entries", "journal_lines")

_LINE_GUARD = """
CREATE OR REPLACE FUNCTION guard_journal_line() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  journal_status text;
BEGIN
  IF TG_OP = 'UPDATE' AND NEW.journal_id IS DISTINCT FROM OLD.journal_id THEN
    RAISE EXCEPTION 'journal line cannot move to another journal';
  END IF;
  IF TG_OP IN ('UPDATE', 'DELETE') THEN
    SELECT status INTO journal_status FROM journal_entries WHERE id = OLD.journal_id;
    IF journal_status IN ('published', 'reversed') THEN
      RAISE EXCEPTION 'published journal is immutable';
    END IF;
  END IF;
  IF TG_OP IN ('INSERT', 'UPDATE') THEN
    SELECT status INTO journal_status FROM journal_entries WHERE id = NEW.journal_id;
    IF journal_status IN ('published', 'reversed') THEN
      RAISE EXCEPTION 'published journal is immutable';
    END IF;
  END IF;
  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  END IF;
  RETURN NEW;
END;
$$;
"""

_OLD_LINE_GUARD = """
CREATE OR REPLACE FUNCTION guard_journal_line() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  journal_status text;
  target_journal text;
BEGIN
  target_journal := COALESCE(NEW.journal_id, OLD.journal_id);
  SELECT status INTO journal_status FROM journal_entries WHERE id = target_journal;
  IF journal_status IN ('published', 'reversed') THEN
    RAISE EXCEPTION 'published journal is immutable';
  END IF;
  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  END IF;
  RETURN NEW;
END;
$$;
"""

# A limpeza dos testes de integração liga app.allow_truncate na própria transação.
# Fora disso, nem o dono das tabelas apaga o livro com TRUNCATE sem desligar o trigger.
_TRUNCATE_GUARD = """
CREATE OR REPLACE FUNCTION block_truncate() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF current_setting('app.allow_truncate', true) = 'on' THEN
    RETURN NULL;
  END IF;
  RAISE EXCEPTION '% is append-only and cannot be truncated', TG_TABLE_NAME;
END;
$$;
"""


def upgrade() -> None:
    op.execute(_LINE_GUARD)
    op.execute(_TRUNCATE_GUARD)
    for table in _GUARDED:
        op.execute(
            f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON {table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION block_truncate()"
        )


def downgrade() -> None:
    for table in _GUARDED:
        op.execute(f"DROP TRIGGER IF EXISTS {table}_no_truncate ON {table}")
    op.execute("DROP FUNCTION IF EXISTS block_truncate()")
    op.execute(_OLD_LINE_GUARD)
