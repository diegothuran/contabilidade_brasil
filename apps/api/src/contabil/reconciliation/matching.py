from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from contabil.platform.constants import EFFECTIVE_JOURNAL_STATUSES
from contabil.tables import BankAccount, BankTransaction, JournalEntry, JournalLine, ReconciliationMatch

_WORD = re.compile(r"[0-9A-Za-zÀ-ÿ]{3,}")


def score_candidate(
    tx_date: date,
    tx_description: str,
    line_date: date,
    line_description: str,
) -> tuple[float, list[str], list[str]]:
    explanation = ["Valor idêntico"]
    fields = ["amount"]
    score = Decimal("0.6")
    days = abs((line_date - tx_date).days)
    if days == 0:
        score += Decimal("0.3")
        explanation.append("Data igual")
    else:
        score += Decimal("0.2")
        explanation.append("Data a 1 dia" if days == 1 else f"Data a {days} dias")
    fields.append("date")
    shared = _words(tx_description) & _words(line_description)
    if shared:
        score += Decimal("0.1")
        explanation.append("Histórico compatível: " + sorted(shared)[0])
        fields.append("description")
    return round(float(score), 2), explanation, fields


def find_candidates(
    session: Session,
    *,
    tenant_id: str,
    bank: BankAccount,
    transaction: BankTransaction,
    tolerance_days: int,
) -> list[dict]:
    side = "debit" if transaction.direction == "inflow" else "credit"
    window = timedelta(days=tolerance_days)
    active_match = (
        select(ReconciliationMatch.id)
        .where(
            ReconciliationMatch.journal_line_id == JournalLine.id,
            ReconciliationMatch.tenant_id == tenant_id,
            ReconciliationMatch.active.is_(True),
        )
        .exists()
    )
    rows = session.execute(
        select(JournalLine, JournalEntry.entry_date, JournalEntry.description)
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_id)
        .where(
            JournalEntry.tenant_id == tenant_id,
            JournalEntry.legal_entity_id == bank.legal_entity_id,
            JournalEntry.status.in_(EFFECTIVE_JOURNAL_STATUSES),
            JournalLine.tenant_id == tenant_id,
            JournalLine.account_id == bank.account_id,
            JournalLine.side == side,
            JournalLine.amount == transaction.amount,
            JournalEntry.entry_date >= transaction.transaction_date - window,
            JournalEntry.entry_date <= transaction.transaction_date + window,
            ~active_match,
        )
    ).all()
    ranked: list[tuple[float, int, str, dict]] = []
    for line, entry_date, journal_description in rows:
        history = f"{line.description} {journal_description}"
        score, explanation, fields = score_candidate(
            transaction.transaction_date,
            transaction.description,
            entry_date,
            history,
        )
        ranked.append(
            (
                score,
                abs((entry_date - transaction.transaction_date).days),
                line.id,
                {
                    "candidate_id": line.id,
                    "candidate_type": "journal",
                    "score": score,
                    "explanation": explanation,
                    "matched_fields": fields,
                },
            )
        )
    ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
    return [item[3] for item in ranked[:20]]


def _words(value: str) -> set[str]:
    return {word.casefold() for word in _WORD.findall(value or "")}
