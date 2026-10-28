from __future__ import annotations

from decimal import Decimal

from contabil.platform.auth import format_utc
from contabil.platform.money import format_amount
from contabil.tables import JournalEntry, JournalLine


def line_dict(line: JournalLine) -> dict:
    return {
        "line_id": line.id,
        "account_id": line.account_id,
        "side": line.side,
        "amount": format_amount(line.amount),
        "description": line.description,
        "cost_center_id": line.cost_center_id,
        "dimension_values": line.dimension_values or {},
    }


def journal_dict(journal: JournalEntry, lines: list[JournalLine]) -> dict:
    return {
        "schema_version": journal.schema_version,
        "journal_id": journal.id,
        "tenant_id": journal.tenant_id,
        "legal_entity_id": journal.legal_entity_id,
        "period_id": journal.period_id,
        "status": journal.status,
        "currency": journal.currency,
        "entry_date": journal.entry_date.isoformat(),
        "description": journal.description,
        "lines": [line_dict(line) for line in lines],
        "source": {
            "source_type": journal.source_type,
            "source_id": journal.source_id,
            "source_hash": journal.source_hash,
            "reverses_journal_id": journal.reverses_journal_id,
        },
        "created_by": journal.created_by,
        "published_at": format_utc(journal.published_at) if journal.published_at else None,
        "published_by": journal.published_by,
        "audit_event_id": journal.audit_event_id,
    }


def totals(lines: list[JournalLine]) -> tuple[Decimal, Decimal]:
    debit = sum((line.amount for line in lines if line.side == "debit"), Decimal("0"))
    credit = sum((line.amount for line in lines if line.side == "credit"), Decimal("0"))
    return debit, credit
