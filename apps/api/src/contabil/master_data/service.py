from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from contabil.platform.errors import DomainError
from contabil.platform.ids import new_id
from contabil.tables import Account, ChartOfAccounts, CostCenter


def list_accounts(session: Session, tenant_id: str, legal_entity_id: str) -> list[Account]:
    return list(
        session.scalars(
            select(Account)
            .where(Account.tenant_id == tenant_id, Account.legal_entity_id == legal_entity_id)
            .order_by(Account.code)
        ).all()
    )


def account_dict(account: Account) -> dict:
    return {
        "account_id": account.id,
        "legal_entity_id": account.legal_entity_id,
        "code": account.code,
        "name": account.name,
        "account_type": account.account_type,
        "postable": account.postable,
        "active": account.active,
        "parent_id": account.parent_id,
    }


def create_account(
    session: Session,
    *,
    tenant_id: str,
    legal_entity_id: str,
    code: str,
    name: str,
    account_type: str,
    postable: bool,
    parent_id: str | None,
) -> Account:
    chart = session.scalar(
        select(ChartOfAccounts).where(ChartOfAccounts.tenant_id == tenant_id, ChartOfAccounts.legal_entity_id == legal_entity_id)
    )
    if chart is None:
        raise DomainError(404, "Não encontrado", "A empresa não tem plano de contas.")
    if parent_id is not None:
        parent = session.scalar(select(Account).where(Account.id == parent_id, Account.tenant_id == tenant_id, Account.legal_entity_id == legal_entity_id))
        if parent is None:
            raise DomainError(400, "Conta pai inválida", "A conta pai não pertence à empresa.")
    account = Account(
        id=new_id("acc"),
        tenant_id=tenant_id,
        legal_entity_id=legal_entity_id,
        chart_id=chart.id,
        parent_id=parent_id,
        code=code,
        name=name,
        account_type=account_type,
        postable=postable,
        active=True,
    )
    session.add(account)
    session.flush()
    return account


def require_postable_accounts(session: Session, tenant_id: str, legal_entity_id: str, account_ids: set[str]) -> None:
    if not account_ids:
        raise DomainError(400, "Conta inválida", "O lançamento precisa de contas.")
    rows = session.scalars(select(Account).where(Account.tenant_id == tenant_id, Account.id.in_(account_ids))).all()
    found = {row.id: row for row in rows}
    for account_id in account_ids:
        account = found.get(account_id)
        if account is None or account.legal_entity_id != legal_entity_id:
            raise DomainError(400, "Conta inválida", "A conta não pertence à empresa.")
        if not account.active or not account.postable:
            raise DomainError(400, "Conta inválida", "A conta precisa estar ativa e ser postável.")


def require_cost_center(session: Session, tenant_id: str, legal_entity_id: str, cost_center_id: str | None) -> None:
    if cost_center_id is None:
        return
    center = session.scalar(
        select(CostCenter).where(
            CostCenter.id == cost_center_id,
            CostCenter.tenant_id == tenant_id,
            CostCenter.legal_entity_id == legal_entity_id,
            CostCenter.active.is_(True),
        )
    )
    if center is None:
        raise DomainError(400, "Centro de custo inválido", "O centro de custo não pertence à empresa.")
