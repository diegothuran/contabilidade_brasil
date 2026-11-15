from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
import datetime as dt
from decimal import Decimal
from typing import Literal

from contabil.platform.conferences import Thresholds
from contabil.platform.money import format_amount
from contabil.reconciliation.statement_parser import normalize_description

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
    window = max(thresholds.duplicate_payment_window_days, thresholds.own_transfer_window_days)
    ordered = sorted(transactions, key=lambda t: (t.date, t.transaction_id))
    alerts: list[Alert] = []
    for i, a in enumerate(ordered):
        for b in ordered[i + 1 :]:
            days = (b.date - a.date).days
            if days > window:
                break
            if a.amount != b.amount:
                continue
            ids = tuple(sorted((a.transaction_id, b.transaction_id)))
            value = format_amount(a.amount)
            if (
                a.bank_account_id == b.bank_account_id
                and a.direction == b.direction == "outflow"
                and days <= thresholds.duplicate_payment_window_days
                and _similar(a.description, b.description)
            ):
                alerts.append(
                    Alert(
                        "duplicate_payment",
                        ids,
                        f"Pagamento de R$ {value} repetido em {days} dia(s) com histórico parecido. Confira se não é duplicidade.",
                        thresholds.version,
                    )
                )
            elif (
                a.bank_account_id != b.bank_account_id
                and a.legal_entity_id == b.legal_entity_id
                and {a.direction, b.direction} == {"inflow", "outflow"}
                and days <= thresholds.own_transfer_window_days
            ):
                alerts.append(
                    Alert(
                        "own_transfer",
                        ids,
                        f"Saída e entrada de R$ {value} entre contas da mesma empresa. Parece transferência entre contas próprias.",
                        thresholds.version,
                    )
                )
    return alerts


def alert_dict(alert: Alert) -> dict:
    return {
        "kind": alert.kind,
        "transaction_ids": list(alert.transaction_ids),
        "explanation": alert.explanation,
        "rule_version": alert.rule_version,
    }
