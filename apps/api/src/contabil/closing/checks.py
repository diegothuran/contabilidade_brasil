from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from contabil.ledger.service import trial_balance
from contabil.periods.service import lock_period
from contabil.platform.conferences import Thresholds, load_thresholds
from contabil.platform.constants import EFFECTIVE_JOURNAL_STATUSES
from contabil.platform.money import format_signed
from contabil.platform.principal import Principal
from contabil.tables import Account, JournalEntry, JournalLine

DEBIT_NATURE = frozenset({"asset", "expense"})
CREDIT_NATURE = frozenset({"liability", "equity", "revenue"})


@dataclass(frozen=True)
class CheckRow:
    account_id: str
    code: str
    name: str
    account_type: str
    closing_balance: Decimal  # débito menos crédito
    last_movement: date | None


@dataclass(frozen=True)
class Check:
    kind: Literal["inverted_balance", "idle_balance"]
    account_id: str
    code: str
    name: str
    amount: Decimal
    explanation: str
    rule_version: str


def _idle_since(period_start: date, months: int) -> date:
    index = period_start.year * 12 + (period_start.month - 1) - (months - 1)
    return date(index // 12, index % 12 + 1, 1)


def evaluate_checks(
    rows: Sequence[CheckRow], period_start: date, period_end: date, thresholds: Thresholds
) -> list[Check]:
    del period_end
    since = _idle_since(period_start, thresholds.idle_balance_months)
    found: list[Check] = []
    for row in rows:
        balance = row.closing_balance
        if balance == 0:
            continue
        inverted_credit = row.account_type in DEBIT_NATURE and balance < 0
        inverted_debit = row.account_type in CREDIT_NATURE and balance > 0
        if inverted_credit or inverted_debit:
            side, nature = ("credor", "devedora") if inverted_credit else ("devedor", "credora")
            found.append(
                Check(
                    "inverted_balance",
                    row.account_id,
                    row.code,
                    row.name,
                    balance,
                    f"Saldo {side} numa conta de natureza {nature}. "
                    "Se for conta redutora (depreciação, prejuízo acumulado), ignore.",
                    thresholds.version,
                )
            )
        if row.last_movement is None or row.last_movement < since:
            found.append(
                Check(
                    "idle_balance",
                    row.account_id,
                    row.code,
                    row.name,
                    balance,
                    f"Saldo parado há {thresholds.idle_balance_months} meses ou mais. Confira se ainda é devido.",
                    thresholds.version,
                )
            )
    return sorted(found, key=lambda check: (check.kind, check.code))


def trial_balance_checks(session: Session, principal: Principal, period_id: str) -> dict:
    period = lock_period(session, principal.tenant_id, period_id)
    balance = trial_balance(session, principal, period.legal_entity_id, period.id)
    ids = [item["account_id"] for item in balance["rows"]]
    types = dict(
        session.execute(
            select(Account.id, Account.account_type).where(Account.tenant_id == principal.tenant_id, Account.id.in_(ids))
        ).all()
    )
    last = dict(
        session.execute(
            select(JournalLine.account_id, func.max(JournalEntry.entry_date))
            .join(JournalEntry, JournalEntry.id == JournalLine.journal_id)
            .where(
                JournalLine.tenant_id == principal.tenant_id,
                JournalLine.account_id.in_(ids),
                JournalEntry.tenant_id == principal.tenant_id,
                JournalEntry.legal_entity_id == period.legal_entity_id,
                JournalEntry.status.in_(EFFECTIVE_JOURNAL_STATUSES),
                JournalEntry.entry_date <= period.end_date,
            )
            .group_by(JournalLine.account_id)
        ).all()
    )
    rows = [
        CheckRow(
            item["account_id"],
            item["code"],
            item["name"],
            types[item["account_id"]],
            Decimal(item["closing_balance"]),
            last.get(item["account_id"]),
        )
        for item in balance["rows"]
    ]
    thresholds = load_thresholds()
    checks = evaluate_checks(rows, period.start_date, period.end_date, thresholds)
    return {
        "period_id": period.id,
        "rule_version": thresholds.version,
        "items": [
            {
                "kind": c.kind,
                "account_id": c.account_id,
                "code": c.code,
                "name": c.name,
                "amount": format_signed(c.amount),
                "explanation": c.explanation,
                "rule_version": c.rule_version,
            }
            for c in checks
        ],
    }
