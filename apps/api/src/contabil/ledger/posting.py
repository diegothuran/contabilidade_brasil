from __future__ import annotations

from sqlalchemy.orm import Session

from contabil.ledger.schemas import JournalCreate
from contabil.ledger.service import approve_journal, create_journal, publish_journal, submit_journal
from contabil.platform.principal import Principal


def publish_balanced(session: Session, preparer: Principal, approver: Principal, body: JournalCreate) -> str:
    created = create_journal(session, preparer, body)
    journal_id = created["journal_id"]
    submit_journal(session, preparer, journal_id)
    approve_journal(session, approver, journal_id)
    publish_journal(session, approver, journal_id)
    return journal_id
