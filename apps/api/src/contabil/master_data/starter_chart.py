from __future__ import annotations

import calendar
from collections.abc import Callable
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from contabil.tables import Account, AccountingPeriod, ChartOfAccounts

STARTER_CHART_NAME = "Modelo mínimo de teste (não referencial)"

ACCOUNT_SPECS = (
    ("1", "Ativo", "asset", False, None),
    ("1.1.01", "Caixa", "asset", True, "1"),
    ("1.1.02", "Bancos", "asset", True, "1"),
    ("2", "Passivo", "liability", False, None),
    ("2.1.01", "Fornecedores", "liability", True, "2"),
    ("3", "Patrimônio líquido", "equity", False, None),
    ("3.1.01", "Capital social", "equity", True, "3"),
    ("3.2.01", "Lucros ou prejuízos acumulados", "equity", True, "3"),
    ("4", "Receitas", "revenue", False, None),
    ("4.1.01", "Receita de serviços", "revenue", True, "4"),
    ("5", "Despesas", "expense", False, None),
    ("5.1.01", "Despesas de serviços", "expense", True, "5"),
)


def add_starter_chart(
    session: Session,
    *,
    tenant_id: str,
    legal_entity_id: str,
    chart_id: str,
    chart_name: str,
    account_id: Callable[[str], str],
) -> None:
    session.add(ChartOfAccounts(id=chart_id, tenant_id=tenant_id, legal_entity_id=legal_entity_id, name=chart_name))
    session.flush()
    for spec in ACCOUNT_SPECS:
        if spec[4] is None:
            _add_account(session, tenant_id, legal_entity_id, chart_id, account_id, spec)
    session.flush()
    for spec in ACCOUNT_SPECS:
        if spec[4] is not None:
            _add_account(session, tenant_id, legal_entity_id, chart_id, account_id, spec)


def add_open_year(
    session: Session,
    *,
    tenant_id: str,
    legal_entity_id: str,
    year: int,
    period_id: Callable[[int, int], str],
) -> int:
    for month in range(1, 13):
        last_day = calendar.monthrange(year, month)[1]
        session.add(
            AccountingPeriod(
                id=period_id(year, month),
                tenant_id=tenant_id,
                legal_entity_id=legal_entity_id,
                fiscal_year=year,
                month=month,
                start_date=date(year, month, 1),
                end_date=date(year, month, last_day),
                status="open",
            )
        )
    return 12


def _add_account(session: Session, tenant_id: str, legal_entity_id: str, chart_id: str, account_id, spec: tuple) -> None:
    code, name, account_type, postable, parent = spec
    session.add(
        Account(
            id=account_id(code),
            tenant_id=tenant_id,
            legal_entity_id=legal_entity_id,
            chart_id=chart_id,
            parent_id=None if parent is None else account_id(parent),
            code=code,
            name=name,
            account_type=account_type,
            postable=postable,
            active=True,
        )
    )


def ensure_retained_earnings(session: Session, tenant_id: str, entity_id: str) -> None:
    """Cria 3.2.01 nas empresas do modelo mínimo criadas antes da ADR 029. Não mexe em plano importado."""
    account_id = f"{entity_id}-3.2.01"
    if session.get(Account, account_id) is not None:
        return
    chart = session.scalar(
        select(ChartOfAccounts).where(ChartOfAccounts.tenant_id == tenant_id, ChartOfAccounts.legal_entity_id == entity_id)
    )
    parent = session.get(Account, f"{entity_id}-3")
    if chart is None or parent is None or parent.account_type != "equity":
        return
    session.add(
        Account(
            id=account_id,
            tenant_id=tenant_id,
            legal_entity_id=entity_id,
            chart_id=chart.id,
            parent_id=parent.id,
            code="3.2.01",
            name="Lucros ou prejuízos acumulados",
            account_type="equity",
            postable=True,
            active=True,
        )
    )
    session.flush()
