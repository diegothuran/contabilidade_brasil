"""Pacote do mês para a revisão por IA (ADR 036).

Só agregados que o sistema já calcula: balancete, movimento das três competências anteriores,
indicadores da DRE, conferências e contagens de pendência. Não leva nome nem CNPJ da empresa,
ids internos, descrição de transação, histórico de lançamento ou documento.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from contabil.closing.checks import trial_balance_checks
from contabil.ledger.service import account_sums, trial_balance
from contabil.platform.principal import Principal
from contabil.tables import Account, AccountingPeriod, BankAccount

PACKET_VERSION = "pacote-1"
PREVIOUS_MONTHS = 3
INDICATOR_KEYS = ("receita", "despesa", "resultado", "dinheiro_em_conta")
PENDING_KEYS = (
    "lancamentos_rascunho",
    "lancamentos_pendentes",
    "lancamentos_aprovados_nao_publicados",
    "casos_conciliacao_pendentes",
    "pedidos_documento_abertos",
    "alertas_extrato",
)
_STATUS = {"open": "aberta", "closed": "fechada"}


@dataclass(frozen=True)
class AccountLine:
    code: str
    name: str
    account_type: str
    opening: Decimal
    debit: Decimal
    credit: Decimal
    closing: Decimal
    previous_moves: tuple[Decimal | None, ...]


CENT = Decimal("0.01")


def _text(value: Decimal | str | None) -> str | None:
    """Duas casas, para o modelo ler reais e centavos sem ambiguidade."""
    if value is None:
        return None
    return format(Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP), "f")


def compose_packet(
    *,
    competence: str,
    period_status: str,
    accounts: Sequence[AccountLine],
    indicators: Mapping[str, tuple[Decimal | str, Sequence[Decimal | str | None]]],
    checks: Sequence[Mapping[str, str]],
    pending: Mapping[str, int],
) -> dict:
    """Função pura. Conta sem saldo e sem movimento em nenhum dos meses fica fora."""
    contas = []
    for line in accounts:
        values = (line.opening, line.debit, line.credit, line.closing, *[value for value in line.previous_moves if value is not None])
        if all(Decimal(value) == 0 for value in values):
            continue
        contas.append(
            {
                "codigo": line.code,
                "nome": line.name,
                "tipo": line.account_type,
                "saldo_anterior": _text(line.opening),
                "debito": _text(line.debit),
                "credito": _text(line.credit),
                "saldo_atual": _text(line.closing),
                "movimento_meses_anteriores": [_text(value) for value in line.previous_moves],
            }
        )
    return {
        "versao": PACKET_VERSION,
        "competencia": competence,
        "status_competencia": _STATUS.get(period_status, period_status),
        "contas": contas,
        "indicadores": {
            key: {"mes": _text(month), "meses_anteriores": [_text(value) for value in previous]}
            for key, (month, previous) in indicators.items()
        },
        "conferencias": [
            {"id": f"c{index + 1}", "tipo": check["kind"], "conta": check["code"], "valor": _text(check["amount"])}
            for index, check in enumerate(checks)
        ],
        "pendencias": {key: int(value) for key, value in pending.items()},
    }


def packet_sha256(packet: Mapping) -> str:
    canonical = json.dumps(packet, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def packet_refs(packet: Mapping) -> set[str]:
    """Evidências que um ponto da revisão pode citar."""
    refs = {f"conta:{item['codigo']}" for item in packet.get("contas", [])}
    refs |= {f"conferencia:{item['id']}" for item in packet.get("conferencias", [])}
    refs |= {f"indicador:{key}" for key in packet.get("indicadores", {})}
    refs |= {f"pendencia:{key}" for key in packet.get("pendencias", {})}
    return refs


def _previous_periods(session: Session, tenant_id: str, period: AccountingPeriod) -> list[AccountingPeriod | None]:
    """As três competências anteriores, da mais antiga à mais recente; None quando não existe."""
    index = period.fiscal_year * 12 + period.month - 1
    found: list[AccountingPeriod | None] = []
    for back in range(PREVIOUS_MONTHS, 0, -1):
        year, month = divmod(index - back, 12)
        found.append(
            session.scalar(
                select(AccountingPeriod).where(
                    AccountingPeriod.tenant_id == tenant_id,
                    AccountingPeriod.legal_entity_id == period.legal_entity_id,
                    AccountingPeriod.fiscal_year == year,
                    AccountingPeriod.month == month + 1,
                )
            )
        )
    return found


def _month_sums(session: Session, tenant_id: str, entity_id: str, period: AccountingPeriod | None) -> dict[str, Decimal] | None:
    if period is None:
        return None
    return account_sums(session, tenant_id, entity_id, AccountingPeriod.id == period.id, exclude_closing=True)


def _result_lines(sums: Mapping[str, Decimal] | None, types: Mapping[str, str]) -> tuple[Decimal, Decimal] | None:
    if sums is None:
        return None
    revenue = -sum((value for account_id, value in sums.items() if types.get(account_id) == "revenue"), Decimal("0"))
    expense = sum((value for account_id, value in sums.items() if types.get(account_id) == "expense"), Decimal("0"))
    return revenue, expense


def build_packet(session: Session, principal: Principal, period: AccountingPeriod, pending: Mapping[str, int]) -> dict:
    """Lê o razão da empresa da competência. `pending` vem do fechamento (contagens já calculadas)."""
    tenant_id = principal.tenant_id
    entity_id = period.legal_entity_id
    balance = trial_balance(session, principal, entity_id, period.id)
    types = dict(
        session.execute(
            select(Account.id, Account.account_type).where(Account.tenant_id == tenant_id, Account.legal_entity_id == entity_id)
        ).all()
    )
    previous = [_month_sums(session, tenant_id, entity_id, item) for item in _previous_periods(session, tenant_id, period)]
    accounts = [
        AccountLine(
            code=row["code"],
            name=row["name"],
            account_type=types.get(row["account_id"], ""),
            opening=Decimal(row["opening_balance"]),
            debit=Decimal(row["debit"]),
            credit=Decimal(row["credit"]),
            closing=Decimal(row["closing_balance"]),
            previous_moves=tuple(None if sums is None else sums.get(row["account_id"], Decimal("0")) for sums in previous),
        )
        for row in balance["rows"]
    ]
    current = _result_lines(_month_sums(session, tenant_id, entity_id, period), types) or (Decimal("0"), Decimal("0"))
    earlier = [_result_lines(sums, types) for sums in previous]
    bank_accounts = set(
        session.scalars(
            select(BankAccount.account_id).where(BankAccount.tenant_id == tenant_id, BankAccount.legal_entity_id == entity_id)
        ).all()
    )
    cash = sum((Decimal(row["closing_balance"]) for row in balance["rows"] if row["account_id"] in bank_accounts), Decimal("0"))
    indicators = {
        "receita": (current[0], [None if item is None else item[0] for item in earlier]),
        "despesa": (current[1], [None if item is None else item[1] for item in earlier]),
        "resultado": (current[0] - current[1], [None if item is None else item[0] - item[1] for item in earlier]),
        "dinheiro_em_conta": (cash, []),
    }
    checks = trial_balance_checks(session, principal, period.id, balance=balance)["items"]
    return compose_packet(
        competence=f"{period.fiscal_year:04d}-{period.month:02d}",
        period_status=period.status,
        accounts=accounts,
        indicators=indicators,
        checks=checks,
        pending=pending,
    )
