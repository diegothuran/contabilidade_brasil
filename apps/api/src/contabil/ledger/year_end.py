"""Encerramento do exercício: o sistema monta o rascunho, um usuário aprova e outro publica (ADR 029).

As contas de resultado com saldo voltam a zero contra a conta de lucros ou prejuízos acumulados
escolhida a cada encerramento. Nada é publicado aqui.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from contabil.ledger.schemas import JournalCreate, LineIn
from contabil.ledger.service import account_sums, create_journal
from contabil.periods.service import require_period
from contabil.platform.constants import CLOSING_SOURCE
from contabil.platform.errors import DomainError
from contabil.platform.money import format_amount, format_signed
from contabil.platform.principal import Principal, ensure_role
from contabil.tables import Account, AccountingPeriod, JournalEntry
from contabil.tenancy.service import require_entity

RESULT_TYPES = ("revenue", "expense")
PENDING_STATUSES = ("draft", "pending_approval", "approved")


def closing_source_id(legal_entity_id: str, fiscal_year: int) -> str:
    return f"{legal_entity_id}-{fiscal_year:04d}"


def _retained_earnings_account(session: Session, tenant_id: str, legal_entity_id: str, account_id: str) -> Account:
    account = session.scalar(select(Account).where(Account.id == account_id, Account.tenant_id == tenant_id))
    if account is None or account.legal_entity_id != legal_entity_id:
        raise DomainError(400, "Conta inválida", "A conta de destino não pertence à empresa.")
    if account.account_type != "equity" or not account.postable or not account.active:
        raise DomainError(400, "Conta inválida", "A conta de destino precisa ser do patrimônio líquido, ativa e postável.")
    return account


def _december(session: Session, tenant_id: str, legal_entity_id: str, fiscal_year: int) -> AccountingPeriod:
    period_id = session.scalar(
        select(AccountingPeriod.id).where(
            AccountingPeriod.tenant_id == tenant_id,
            AccountingPeriod.legal_entity_id == legal_entity_id,
            AccountingPeriod.fiscal_year == fiscal_year,
            AccountingPeriod.month == 12,
        )
    )
    if period_id is None:
        raise DomainError(404, "Não encontrado", f"O exercício {fiscal_year} não tem a competência de dezembro.")
    # Trava a competência: dois pedidos simultâneos não geram dois encerramentos.
    return require_period(session, tenant_id, legal_entity_id, period_id, for_posting=True)


def _ensure_nothing_pending(session: Session, tenant_id: str, legal_entity_id: str, fiscal_year: int) -> None:
    pending = session.scalars(
        select(JournalEntry.id)
        .join(AccountingPeriod, AccountingPeriod.id == JournalEntry.period_id)
        .where(
            JournalEntry.tenant_id == tenant_id,
            JournalEntry.legal_entity_id == legal_entity_id,
            AccountingPeriod.fiscal_year == fiscal_year,
            JournalEntry.status.in_(PENDING_STATUSES),
        )
        .order_by(JournalEntry.id)
    ).all()
    if pending:
        shown = ", ".join(pending[:5]) + (" e outros" if len(pending) > 5 else "")
        raise DomainError(
            409,
            "Lançamentos pendentes",
            f"Há {len(pending)} lançamento(s) do exercício ainda não publicado(s): {shown}. Publique ou rejeite antes de encerrar.",
        )


def _ensure_not_closed(session: Session, tenant_id: str, legal_entity_id: str, fiscal_year: int) -> None:
    existing = session.scalar(
        select(JournalEntry.id).where(
            JournalEntry.tenant_id == tenant_id,
            JournalEntry.legal_entity_id == legal_entity_id,
            JournalEntry.source_type == CLOSING_SOURCE,
            JournalEntry.source_id == closing_source_id(legal_entity_id, fiscal_year),
            JournalEntry.status.not_in(("rejected", "reversed")),
        )
    )
    if existing is not None:
        raise DomainError(
            409,
            "Encerramento já existe",
            f"O exercício {fiscal_year} já tem o encerramento {existing}. Para refazer, reverta esse lançamento.",
        )


def build_closing_draft(
    session: Session, principal: Principal, legal_entity_id: str, fiscal_year: int, retained_earnings_account_id: str
) -> dict:
    ensure_role(principal, "preparer", "admin")
    entity = require_entity(session, principal.tenant_id, legal_entity_id)
    retained = _retained_earnings_account(session, principal.tenant_id, entity.id, retained_earnings_account_id)
    december = _december(session, principal.tenant_id, entity.id, fiscal_year)
    _ensure_not_closed(session, principal.tenant_id, entity.id, fiscal_year)
    _ensure_nothing_pending(session, principal.tenant_id, entity.id, fiscal_year)

    result_accounts = session.execute(
        select(Account.id, Account.code)
        .where(
            Account.tenant_id == principal.tenant_id,
            Account.legal_entity_id == entity.id,
            Account.account_type.in_(RESULT_TYPES),
        )
        .order_by(Account.code)
    ).all()
    year_end = date(fiscal_year, 12, 31)
    sums = account_sums(session, principal.tenant_id, entity.id, AccountingPeriod.end_date <= year_end)
    balances = [(account_id, sums.get(account_id, Decimal("0"))) for account_id, _ in result_accounts]
    balances = [(account_id, amount) for account_id, amount in balances if amount != 0]
    if not balances:
        raise DomainError(409, "Nada a encerrar", f"As contas de resultado não têm saldo em {fiscal_year}.")

    warnings: list[str] = []
    before = account_sums(session, principal.tenant_id, entity.id, AccountingPeriod.end_date < date(fiscal_year, 1, 1))
    if any(before.get(account_id, Decimal("0")) != 0 for account_id, _ in result_accounts):
        warnings.append("O resultado de exercícios anteriores não foi encerrado e entra neste lançamento.")

    description = f"Encerramento do exercício {fiscal_year}"
    lines = [
        LineIn(
            account_id=account_id,
            side="credit" if amount > 0 else "debit",
            amount=format_amount(abs(amount)),
            description=description,
        )
        for account_id, amount in balances
    ]
    net = sum((amount for _, amount in balances), Decimal("0"))
    profit = -net  # saldo credor das contas de resultado é lucro
    if profit != 0:
        lines.append(
            LineIn(
                account_id=retained.id,
                side="credit" if profit > 0 else "debit",
                amount=format_amount(abs(profit)),
                description=f"{description}: {'lucro' if profit > 0 else 'prejuízo'}",
            )
        )
    if len(lines) < 2:
        raise DomainError(409, "Nada a encerrar", "O encerramento precisa de pelo menos duas linhas.")
    journal = create_journal(
        session,
        principal,
        JournalCreate(
            legal_entity_id=entity.id,
            period_id=december.id,
            currency=entity.currency,
            entry_date=year_end,
            description=description,
            source_type=CLOSING_SOURCE,
            source_id=closing_source_id(entity.id, fiscal_year),
            lines=lines,
        ),
        system_source=True,
    )
    return {"journal": journal, "fiscal_year": fiscal_year, "result": format_signed(profit), "warnings": warnings}
