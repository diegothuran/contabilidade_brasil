from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select

from contabil.platform.auth import apply_tenant
from contabil.platform.db import session_factory
from contabil.signatories.service import signatories_for
from contabil.signatories.validators import valid_cpf
from contabil.tables import AccountingPeriod, EcdRegistration, JournalEntry, JournalLine, LegalEntity, Membership, OperationalExport


def test_pilot_samples_are_idempotent_and_skip_statements_without_storage(monkeypatch, world):
    del world
    monkeypatch.delenv("OBJECT_STORAGE_BUCKET", raising=False)
    monkeypatch.delenv("OBJECT_STORAGE_ACCESS_KEY", raising=False)
    from contabil.pilot_samples import load_samples

    first = load_samples("tenant_demo")
    second = load_samples("tenant_demo")
    assert first["statements"] == "skipped"
    assert len(first["created"]) == 5
    assert second["created"] == []
    assert len(second["skipped"]) == 5
    session = session_factory(admin=True)()
    try:
        apply_tenant(session, "tenant_demo")
        names = session.scalars(select(LegalEntity.name).where(LegalEntity.tenant_id == "tenant_demo", LegalEntity.name.contains("(teste)"))).all()
        assert len(names) == 5
        clients = session.scalars(
            select(Membership.legal_entity_id).where(Membership.tenant_id == "tenant_demo", Membership.user_id.like("cliente-%"))
        ).all()
        assert {company["legal_entity_id"] for company in first["created"]} <= set(clients)
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
            months = set(
                session.scalars(
                    select(AccountingPeriod.month)
                    .join(JournalEntry, JournalEntry.period_id == AccountingPeriod.id)
                    .where(JournalEntry.legal_entity_id == company["legal_entity_id"], JournalEntry.status == "published")
                ).all()
            )
            today = date.today()
            open_months = set(
                session.scalars(
                    select(AccountingPeriod.month).where(
                        AccountingPeriod.legal_entity_id == company["legal_entity_id"],
                        AccountingPeriod.fiscal_year == today.year,
                        AccountingPeriod.month <= today.month,
                        AccountingPeriod.status.in_(("open", "reopened")),
                    )
                ).all()
            )
            assert open_months <= months, company["name"]
        by_story = {company["story"]: company["legal_entity_id"] for company in first["created"]}
        closing = session.scalars(
            select(JournalEntry.status).where(JournalEntry.legal_entity_id == by_story["banco"], JournalEntry.source_type == "closing")
        ).all()
        assert closing == ["pending_approval"], first["notes"]
        exports = session.scalar(select(func.count()).select_from(OperationalExport).where(OperationalExport.legal_entity_id == by_story["fechada"]))
        assert exports == 1, first["notes"]
        for story, entity_id in by_story.items():
            found = signatories_for(session, "tenant_demo", entity_id)
            if story == "vazia":
                assert found is None
                continue
            assert found is not None and found.accountant is not None, story
            assert found.accountant.crc.startswith("CRC-PE ")
            assert found.legal_representative is not None and valid_cpf(found.legal_representative.cpf or "")
        ecd = session.scalars(select(EcdRegistration).where(EcdRegistration.tenant_id == "tenant_demo")).all()
        assert [(row.legal_entity_id, row.uf, row.municipality_ibge, row.registry_kind) for row in ecd] == [
            (by_story["banco"], "PE", "2611606", "junta")
        ]
        assert ecd[0].nire.startswith("26")
    finally:
        session.close()


def test_litoral_samples_register_the_market_in_a_cartorio_and_generate_an_ecd_preview(world):
    del world
    from contabil.exports.service import ECD_PREVIEW_KIND
    from contabil.pilot_samples import load_samples
    from tests.integration.test_ecd_preview import _drain

    loaded = load_samples("tenant_demo", "litoral")
    assert loaded["statements"] == "imported"
    by_story = {company["story"]: company["legal_entity_id"] for company in loaded["created"]}
    _drain()
    session = session_factory(admin=True)()
    try:
        apply_tenant(session, "tenant_demo")
        row = session.scalar(select(EcdRegistration).where(EcdRegistration.legal_entity_id == by_story["mercado"]))
        assert (row.uf, row.municipality_ibge, row.registry_kind, row.nire) == ("PE", "2611606", "cartorio", None)
        export = session.scalar(
            select(OperationalExport).where(OperationalExport.legal_entity_id == by_story["mercado"], OperationalExport.kind == ECD_PREVIEW_KIND)
        )
        assert export is not None and export.payload is not None, loaded["notes"]
        assert export.payload["transmittable"] is False
        codes = {issue["code"] for issue in export.payload["issues"]}
        assert "closing_missing" in codes
        assert "registration_missing" not in codes
        assert export.payload["checks"]["block_counts"] is True
    finally:
        session.close()
