"""DRE e Balanço gerenciais montados a partir do tipo e da hierarquia das contas (ADR 029).

Não seguem layout oficial: os grupos são as contas raiz do plano da empresa. O layout da
Lei 6.404 depende do plano de contas real (perguntas 18 e 53 do caderno do contador).
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from contabil.ledger.csv_export import balance_sheet_csv, income_statement_csv, period_label
from contabil.ledger.service import account_sums
from contabil.periods.service import require_period
from contabil.platform.money import format_signed
from contabil.platform.principal import Principal
from contabil.signatories.editing import statement_signatories
from contabil.tables import Account, AccountingPeriod, LegalEntity
from contabil.tenancy.service import require_entity

ZERO = Decimal("0")
SECTION_TITLES = {
    "asset": "Ativo",
    "liability": "Passivo",
    "equity": "Patrimônio líquido",
    "revenue": "Receitas",
    "expense": "Despesas",
}
UNCLOSED_RESULT = "Resultado do exercício não encerrado"


def _load(session: Session, principal: Principal, legal_entity_id: str, period_id: str) -> tuple[LegalEntity, AccountingPeriod, list[Account]]:
    entity = require_entity(session, principal.tenant_id, legal_entity_id)
    period = require_period(session, principal.tenant_id, entity.id, period_id, for_posting=False)
    accounts = list(
        session.scalars(
            select(Account)
            .where(Account.tenant_id == principal.tenant_id, Account.legal_entity_id == entity.id)
            .order_by(Account.code)
        ).all()
    )
    return entity, period, accounts


def _root(account: Account, by_id: dict[str, Account]) -> Account:
    current = account
    seen = {current.id}
    while current.parent_id and current.parent_id in by_id and current.parent_id not in seen:
        current = by_id[current.parent_id]
        seen.add(current.id)
    return current


def _groups(accounts: list[Account], account_type: str, values: dict[str, dict[str, Decimal]], columns: tuple[str, ...]) -> list[dict]:
    """Contas lançáveis do tipo, agrupadas pela conta raiz. Só entram linhas com algum valor."""
    by_id = {account.id: account for account in accounts}
    groups: dict[str, dict] = {}
    for account in accounts:
        if account.account_type != account_type or not account.postable:
            continue
        root = _root(account, by_id)
        group = groups.setdefault(
            root.id,
            {"code": root.code, "name": root.name, "rows": [], **{column: ZERO for column in columns}},
        )
        amounts = {column: values[column].get(account.id, ZERO) for column in columns}
        for column in columns:
            group[column] += amounts[column]
        if any(amount != 0 for amount in amounts.values()):
            group["rows"].append({"account_id": account.id, "code": account.code, "name": account.name, **amounts})
    return sorted(groups.values(), key=lambda group: group["code"])


def _format(groups: list[dict], columns: tuple[str, ...]) -> list[dict]:
    return [
        {
            **group,
            **{column: format_signed(group[column]) for column in columns},
            "rows": [{**row, **{column: format_signed(row[column]) for column in columns}} for row in group["rows"]],
        }
        for group in groups
    ]


def _total(groups: list[dict], column: str) -> Decimal:
    return sum((group[column] for group in groups), ZERO)


def _presented(sums: dict[str, Decimal], accounts: list[Account], credit_types: set[str]) -> dict[str, Decimal]:
    """Saldo com o sinal de leitura: positivo na natureza da conta (devedora ou credora)."""
    kinds = {account.id: account.account_type for account in accounts}
    return {account_id: (-amount if kinds.get(account_id) in credit_types else amount) for account_id, amount in sums.items()}


def income_statement(session: Session, principal: Principal, legal_entity_id: str, period_id: str) -> dict:
    entity, period, accounts = _load(session, principal, legal_entity_id, period_id)
    month = account_sums(session, principal.tenant_id, entity.id, AccountingPeriod.id == period.id, exclude_closing=True)
    year = account_sums(
        session,
        principal.tenant_id,
        entity.id,
        AccountingPeriod.fiscal_year == period.fiscal_year,
        AccountingPeriod.end_date <= period.end_date,
        exclude_closing=True,
    )
    columns = ("month", "year_to_date")
    values = {
        "month": _presented(month, accounts, {"revenue"}),
        "year_to_date": _presented(year, accounts, {"revenue"}),
    }
    revenue = _groups(accounts, "revenue", values, columns)
    expense = _groups(accounts, "expense", values, columns)
    totals = {
        "revenue": {column: _total(revenue, column) for column in columns},
        "expense": {column: _total(expense, column) for column in columns},
    }
    result = {column: totals["revenue"][column] - totals["expense"][column] for column in columns}
    return {
        "legal_entity_id": entity.id,
        "period_id": period.id,
        "currency": entity.currency,
        "fiscal_year": period.fiscal_year,
        "month": period.month,
        "sections": [
            {"account_type": "revenue", "title": SECTION_TITLES["revenue"], "groups": _format(revenue, columns),
             **{column: format_signed(totals["revenue"][column]) for column in columns}},
            {"account_type": "expense", "title": SECTION_TITLES["expense"], "groups": _format(expense, columns),
             **{column: format_signed(totals["expense"][column]) for column in columns}},
        ],
        "result": {column: format_signed(result[column]) for column in columns},
        "signatories": statement_signatories(session, principal.tenant_id, entity.id),
    }


def balance_sheet(session: Session, principal: Principal, legal_entity_id: str, period_id: str) -> dict:
    entity, period, accounts = _load(session, principal, legal_entity_id, period_id)
    sums = account_sums(session, principal.tenant_id, entity.id, AccountingPeriod.end_date <= period.end_date)
    columns = ("balance",)
    values = {"balance": _presented(sums, accounts, {"liability", "equity", "revenue"})}
    sections = []
    totals: dict[str, Decimal] = {}
    for account_type in ("asset", "liability", "equity"):
        groups = _groups(accounts, account_type, values, columns)
        totals[account_type] = _total(groups, "balance")
        sections.append({"account_type": account_type, "title": SECTION_TITLES[account_type], "groups": _format(groups, columns)})
    # Receita menos despesa ainda não transferida para o PL pelo encerramento.
    unclosed = sum(
        (-sums.get(account.id, ZERO) for account in accounts if account.account_type in ("revenue", "expense")),
        ZERO,
    )
    totals["equity"] += unclosed
    sections[2]["unclosed_result"] = format_signed(unclosed)
    for section in sections:
        section["balance"] = format_signed(totals[section["account_type"]])
    liabilities_and_equity = totals["liability"] + totals["equity"]
    return {
        "legal_entity_id": entity.id,
        "period_id": period.id,
        "currency": entity.currency,
        "fiscal_year": period.fiscal_year,
        "month": period.month,
        "sections": sections,
        "total_assets": format_signed(totals["asset"]),
        "total_liabilities_and_equity": format_signed(liabilities_and_equity),
        "difference": format_signed(totals["asset"] - liabilities_and_equity),
        "signatories": statement_signatories(session, principal.tenant_id, entity.id),
    }


def _export(session: Session, principal: Principal, legal_entity_id: str, period_id: str, prefix: str, build, render) -> tuple[str, str]:
    report = build(session, principal, legal_entity_id, period_id)
    entity = require_entity(session, principal.tenant_id, legal_entity_id)
    period = require_period(session, principal.tenant_id, entity.id, period_id, for_posting=False)
    content = render(
        entity_name=entity.name,
        cnpj=entity.cnpj,
        period=period_label(period.fiscal_year, period.month),
        generated_at=datetime.now(timezone.utc),
        report=report,
    )
    return f"{prefix}-{entity.cnpj}-{period.fiscal_year:04d}-{period.month:02d}.csv", content


def income_statement_csv_export(session: Session, principal: Principal, legal_entity_id: str, period_id: str) -> tuple[str, str]:
    return _export(session, principal, legal_entity_id, period_id, "dre", income_statement, income_statement_csv)


def balance_sheet_csv_export(session: Session, principal: Principal, legal_entity_id: str, period_id: str) -> tuple[str, str]:
    return _export(session, principal, legal_entity_id, period_id, "balanco", balance_sheet, balance_sheet_csv)
