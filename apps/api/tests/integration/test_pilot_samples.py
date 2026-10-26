from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select

from contabil.platform.auth import apply_tenant
from contabil.platform.db import session_factory
from contabil.tables import JournalEntry, JournalLine, LegalEntity


def test_pilot_samples_are_idempotent_and_skip_statements_without_storage(monkeypatch, world):
    del world
    monkeypatch.delenv("OBJECT_STORAGE_BUCKET", raising=False)
    monkeypatch.delenv("OBJECT_STORAGE_ACCESS_KEY", raising=False)
    from contabil.pilot_samples import load_samples

    first = load_samples("tenant_demo")
    second = load_samples("tenant_demo")
    assert first["statements"] == "skipped"
    assert len(first["created"]) == 3
    assert second["created"] == []
    assert len(second["skipped"]) == 3
    session = session_factory(admin=True)()
    try:
        apply_tenant(session, "tenant_demo")
        names = session.scalars(select(LegalEntity.name).where(LegalEntity.tenant_id == "tenant_demo", LegalEntity.name.contains("(teste)"))).all()
        assert len(names) == 3
        for company in first["created"]:
            debit = session.scalar(
                select(func.coalesce(func.sum(JournalLine.amount), 0))
                .join(JournalEntry, JournalEntry.id == JournalLine.journal_id)
                .where(
                    JournalEntry.legal_entity_id == company["legal_entity_id"],
                    JournalEntry.status == "published",
                    JournalLine.side == "debit",
                )
            )
            credit = session.scalar(
                select(func.coalesce(func.sum(JournalLine.amount), 0))
                .join(JournalEntry, JournalEntry.id == JournalLine.journal_id)
                .where(
                    JournalEntry.legal_entity_id == company["legal_entity_id"],
                    JournalEntry.status == "published",
                    JournalLine.side == "credit",
                )
            )
            assert Decimal(debit) == Decimal(credit)
            assert Decimal(debit) > 0
    finally:
        session.close()
