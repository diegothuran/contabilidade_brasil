from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
import datetime as dt
from decimal import Decimal
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from contabil.platform.conferences import Thresholds, load_thresholds
from contabil.platform.money import format_amount
from contabil.reconciliation.statement_parser import normalize_description
from contabil.tables import AccountingPeriod, BankAccount, BankTransaction

_WORD = re.compile(r"[^\W\d_]{3,}", re.UNICODE)


@dataclass(frozen=True)
class AlertTx:
    transaction_id: str
    bank_account_id: str
    legal_entity_id: str
    date: dt.date
    amount: Decimal
    direction: str
    description: str


@dataclass(frozen=True)
class Alert:
    kind: Literal["duplicate_payment", "own_transfer"]
    transaction_ids: tuple[str, ...]
    explanation: str
    rule_version: str


def _similar(a: str, b: str) -> bool:
    na, nb = normalize_description(a), normalize_description(b)
    if na == nb:
        return True
    return len(set(_WORD.findall(na)) & set(_WORD.findall(nb))) >= 2


def statement_alerts(transactions: Sequence[AlertTx], thresholds: Thresholds) -> list[Alert]:
    """Duplicidade sai por grupo; transferência entre contas próprias sai por par.

    Saídas iguais repetidas (tarifas, por exemplo) formam um grupo só: cada par de mesmo valor,
    histórico parecido e dentro da janela liga as duas transações, e o grupo é o componente ligado.
    """
    window = max(thresholds.duplicate_payment_window_days, thresholds.own_transfer_window_days)
    ordered = sorted(transactions, key=lambda t: (t.date, t.transaction_id))
    parent = list(range(len(ordered)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    transfers: list[tuple[int, Alert]] = []
    linked: set[int] = set()
    for i, a in enumerate(ordered):
        for j in range(i + 1, len(ordered)):
            b = ordered[j]
            days = (b.date - a.date).days
            if days > window:
                break
            if a.amount != b.amount:
                continue
            if (
                a.bank_account_id == b.bank_account_id
                and a.direction == b.direction == "outflow"
                and days <= thresholds.duplicate_payment_window_days
                and _similar(a.description, b.description)
            ):
                linked.update((i, j))
                root_a, root_b = find(i), find(j)
                if root_a != root_b:
                    parent[max(root_a, root_b)] = min(root_a, root_b)
            elif (
                a.bank_account_id != b.bank_account_id
                and a.legal_entity_id == b.legal_entity_id
                and {a.direction, b.direction} == {"inflow", "outflow"}
                and days <= thresholds.own_transfer_window_days
            ):
                transfers.append(
                    (
                        i,
                        Alert(
                            "own_transfer",
                            tuple(sorted((a.transaction_id, b.transaction_id))),
                            f"Saída e entrada de R$ {format_amount(a.amount)} entre contas da mesma empresa. "
                            "Parece transferência entre contas próprias.",
                            thresholds.version,
                        ),
                    )
                )
    groups: dict[int, list[int]] = {}
    for index in sorted(linked):
        groups.setdefault(find(index), []).append(index)
    duplicates: list[tuple[int, Alert]] = []
    for root, members in groups.items():
        items = [ordered[index] for index in members]
        span = (items[-1].date - items[0].date).days
        when = "no mesmo dia" if span == 0 else f"em {span} dia(s)"
        duplicates.append(
            (
                root,
                Alert(
                    "duplicate_payment",
                    tuple(sorted(item.transaction_id for item in items)),
                    f"{len(items)} pagamentos de R$ {format_amount(items[0].amount)} com histórico parecido {when}. "
                    "Confira se não é duplicidade.",
                    thresholds.version,
                ),
            )
        )
    merged = sorted(duplicates + transfers, key=lambda item: (item[0], item[1].kind, item[1].transaction_ids))
    return [alert for _index, alert in merged]


def alert_dict(alert: Alert) -> dict:
    return {
        "kind": alert.kind,
        "transaction_ids": list(alert.transaction_ids),
        "explanation": alert.explanation,
        "rule_version": alert.rule_version,
    }


def _window(thresholds: Thresholds) -> dt.timedelta:
    return dt.timedelta(days=max(thresholds.duplicate_payment_window_days, thresholds.own_transfer_window_days))


def _entity_alerts(
    session: Session, tenant_id: str, legal_entity_id: str, start: dt.date, end: dt.date
) -> list[Alert]:
    thresholds = load_thresholds()
    margin = _window(thresholds)
    rows = session.execute(
        select(BankTransaction, BankAccount.legal_entity_id)
        .join(BankAccount, BankAccount.id == BankTransaction.bank_account_id)
        .where(
            BankTransaction.tenant_id == tenant_id,
            BankAccount.tenant_id == tenant_id,
            BankAccount.legal_entity_id == legal_entity_id,
            BankTransaction.transaction_date >= start - margin,
            BankTransaction.transaction_date <= end + margin,
        )
    ).all()
    items = [
        AlertTx(
            row.id,
            row.bank_account_id,
            entity_id,
            row.transaction_date,
            row.amount,
            row.direction,
            row.description,
        )
        for row, entity_id in rows
    ]
    return statement_alerts(items, thresholds)


# O caso mostra no máximo 20 alertas (schemas/reconciliation-case.schema.json).
MAX_ALERTS_PER_CASE = 20


def alerts_by_transaction(alerts: Sequence[Alert], wanted: set[str], limit: int = MAX_ALERTS_PER_CASE) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for alert in alerts:
        for transaction_id in alert.transaction_ids:
            if transaction_id in wanted:
                items = result.setdefault(transaction_id, [])
                if len(items) < limit:
                    items.append(alert_dict(alert))
    return result


def alerts_for_transactions(
    session: Session, tenant_id: str, legal_entity_id: str, transactions: Sequence[BankTransaction]
) -> dict[str, list[dict]]:
    if not transactions:
        return {}
    wanted = {item.id for item in transactions}
    dates = [item.transaction_date for item in transactions]
    return alerts_by_transaction(_entity_alerts(session, tenant_id, legal_entity_id, min(dates), max(dates)), wanted)


def period_alert_count(
    session: Session,
    tenant_id: str,
    legal_entity_id: str,
    period: AccountingPeriod,
    *,
    bank_account_id: str | None = None,
) -> int:
    """Alertas distintos (grupo de duplicidade ou par de transferência) com alguma transação dentro da competência (da conta, quando informada)."""
    inside = {
        row.id
        for row in session.scalars(
            select(BankTransaction)
            .join(BankAccount, BankAccount.id == BankTransaction.bank_account_id)
            .where(
                BankTransaction.tenant_id == tenant_id,
                BankAccount.tenant_id == tenant_id,
                BankAccount.legal_entity_id == legal_entity_id,
                BankTransaction.transaction_date >= period.start_date,
                BankTransaction.transaction_date <= period.end_date,
                *([BankTransaction.bank_account_id == bank_account_id] if bank_account_id else []),
            )
        )
    }
    alerts = _entity_alerts(session, tenant_id, legal_entity_id, period.start_date, period.end_date)
    return sum(1 for alert in alerts if inside.intersection(alert.transaction_ids))
