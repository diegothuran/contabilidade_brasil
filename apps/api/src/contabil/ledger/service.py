from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from contabil.audit.service import append_event
from contabil.ledger.csv_export import account_ledger_csv, period_label, trial_balance_csv
from contabil.ledger.presenter import journal_dict, totals
from contabil.ledger.schemas import JournalCreate
from contabil.master_data.service import require_cost_center, require_postable_accounts
from contabil.periods.service import require_period
from contabil.platform.constants import EFFECTIVE_JOURNAL_STATUSES, SCHEMA_VERSION
from contabil.platform.errors import DomainError
from contabil.platform.ids import new_id
from contabil.platform.money import format_amount, format_signed, parse_amount
from contabil.platform.outbox import enqueue
from contabil.platform.principal import Principal, ensure_role
from contabil.tables import Account, AccountingPeriod, JournalEntry, JournalLine
from contabil.tenancy.service import before_cursor, encode_cursor, page_limit, require_entity


def _lines(session: Session, tenant_id: str, journal_id: str) -> list[JournalLine]:
    return list(
        session.scalars(
            select(JournalLine)
            .where(JournalLine.journal_id == journal_id, JournalLine.tenant_id == tenant_id)
            .order_by(JournalLine.line_no)
        ).all()
    )


def _lock(session: Session, tenant_id: str, journal_id: str) -> JournalEntry:
    journal = session.scalar(
        select(JournalEntry).where(JournalEntry.id == journal_id, JournalEntry.tenant_id == tenant_id).with_for_update()
    )
    if journal is None:
        raise DomainError(404, "Não encontrado", "Lançamento não encontrado.")
    return journal


def _ensure_balanced(lines: list[JournalLine]) -> None:
    debit, credit = totals(lines)
    if len(lines) < 2 or debit != credit:
        raise DomainError(409, "Journal desequilibrado", "Débitos e créditos precisam ser iguais para publicar.")


def _ensure_not_creator(journal: JournalEntry, principal: Principal) -> None:
    if journal.created_by == principal.user_id:
        raise DomainError(403, "Segregação de funções", "Quem cria o lançamento não pode aprová-lo nem publicá-lo.")


def _validate_lines(session: Session, tenant_id: str, legal_entity_id: str, lines: list[JournalLine]) -> None:
    require_postable_accounts(session, tenant_id, legal_entity_id, {line.account_id for line in lines})
    for line in lines:
        require_cost_center(session, tenant_id, legal_entity_id, line.cost_center_id)


def _ready(session: Session, journal: JournalEntry, lines: list[JournalLine]) -> None:
    _ensure_balanced(lines)
    _validate_lines(session, journal.tenant_id, journal.legal_entity_id, lines)
    require_period(session, journal.tenant_id, journal.legal_entity_id, journal.period_id, for_posting=True)
    if journal.entry_date is None:
        raise DomainError(400, "Data inválida", "O lançamento precisa de data.")


def create_journal(session: Session, principal: Principal, body: JournalCreate) -> dict:
    ensure_role(principal, "preparer", "admin")
    if body.source_type == "reversal":
        raise DomainError(400, "Origem inválida", "Reversão é criada pela operação de reverter.")
    entity = require_entity(session, principal.tenant_id, body.legal_entity_id)
    if body.currency != entity.currency:
        raise DomainError(400, "Moeda inválida", "A moeda do lançamento deve ser a moeda da empresa.")
    period = require_period(session, principal.tenant_id, entity.id, body.period_id, for_posting=True)
    if not period.start_date <= body.entry_date <= period.end_date:
        raise DomainError(400, "Data fora da competência", "A data do lançamento precisa cair dentro do período.")
    parsed = [parse_amount(line.amount) for line in body.lines]
    journal_id = new_id("jnl")
    source_id = body.source_id or journal_id
    journal = JournalEntry(
        id=journal_id,
        schema_version=SCHEMA_VERSION,
        tenant_id=principal.tenant_id,
        legal_entity_id=entity.id,
        period_id=period.id,
        status="draft",
        currency=body.currency,
        entry_date=body.entry_date,
        description=body.description,
        source_type=body.source_type,
        source_id=source_id,
        source_hash=body.source_hash,
        created_by=principal.user_id,
    )
    lines: list[JournalLine] = []
    for index, (incoming, amount) in enumerate(zip(body.lines, parsed, strict=True), start=1):
        require_cost_center(session, principal.tenant_id, entity.id, incoming.cost_center_id)
        lines.append(
            JournalLine(
                id=new_id("ln"),
                tenant_id=principal.tenant_id,
                journal_id=journal_id,
                line_no=index,
                account_id=incoming.account_id,
                side=incoming.side,
                amount=amount,
                description=incoming.description,
                cost_center_id=incoming.cost_center_id,
                dimension_values=incoming.dimension_values,
            )
        )
    require_postable_accounts(session, principal.tenant_id, entity.id, {line.account_id for line in lines})
    debit, credit = totals(lines)
    if debit != credit:
        raise DomainError(400, "Journal desequilibrado", "O rascunho precisa nascer equilibrado. A publicação também recusa desequilíbrio.")
    session.add(journal)
    session.flush()
    session.add_all(lines)
    event = append_event(
        session,
        tenant_id=principal.tenant_id,
        event_type="journal_created",
        actor_ref=principal.user_id,
        target_type="journal",
        target_ref=journal.id,
        metadata={"action": "journal_created"},
    )
    journal.audit_event_id = event.id
    session.flush()
    return journal_dict(journal, lines)


def get_journal(session: Session, principal: Principal, journal_id: str) -> dict:
    journal = session.scalar(select(JournalEntry).where(JournalEntry.id == journal_id, JournalEntry.tenant_id == principal.tenant_id))
    if journal is None:
        raise DomainError(404, "Não encontrado", "Lançamento não encontrado.")
    return journal_dict(journal, _lines(session, principal.tenant_id, journal.id))


def list_journals(
    session: Session,
    principal: Principal,
    *,
    legal_entity_id: str,
    period_id: str | None,
    status: str | None,
    reverses_journal_id: str | None,
    cursor: str | None,
    limit: int,
) -> dict:
    require_entity(session, principal.tenant_id, legal_entity_id)
    limit = page_limit(limit)
    stmt = select(JournalEntry).where(JournalEntry.tenant_id == principal.tenant_id, JournalEntry.legal_entity_id == legal_entity_id)
    if period_id:
        stmt = stmt.where(JournalEntry.period_id == period_id)
    if status:
        stmt = stmt.where(JournalEntry.status == status)
    if reverses_journal_id:
        stmt = stmt.where(JournalEntry.reverses_journal_id == reverses_journal_id)
    comparison = before_cursor(JournalEntry.created_at, JournalEntry.id, cursor)
    if comparison is not None:
        stmt = stmt.where(comparison)
    rows = session.scalars(stmt.order_by(JournalEntry.created_at.desc(), JournalEntry.id.desc()).limit(limit + 1)).all()
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        rows = rows[:limit]
        next_cursor = encode_cursor(last.created_at, last.id)
    items = [journal_dict(row, _lines(session, principal.tenant_id, row.id)) for row in rows]
    return {"items": items, "next_cursor": next_cursor}


def _transition_note(session: Session, principal: Principal, journal: JournalEntry, action: str) -> None:
    append_event(
        session,
        tenant_id=principal.tenant_id,
        event_type="other",
        actor_ref=principal.user_id,
        target_type="journal",
        target_ref=journal.id,
        metadata={"action": action},
    )


def submit_journal(session: Session, principal: Principal, journal_id: str) -> dict:
    ensure_role(principal, "preparer", "admin")
    journal = _lock(session, principal.tenant_id, journal_id)
    if journal.status != "draft":
        raise DomainError(409, "Estado inválido", "Somente rascunho pode ser enviado para aprovação.")
    lines = _lines(session, principal.tenant_id, journal.id)
    _ready(session, journal, lines)
    journal.status = "pending_approval"
    _transition_note(session, principal, journal, "journal_submitted")
    return journal_dict(journal, lines)


def approve_journal(session: Session, principal: Principal, journal_id: str) -> dict:
    ensure_role(principal, "approver", "admin")
    journal = _lock(session, principal.tenant_id, journal_id)
    if journal.status != "pending_approval":
        raise DomainError(409, "Estado inválido", "Somente lançamento pendente pode ser aprovado.")
    _ensure_not_creator(journal, principal)
    lines = _lines(session, principal.tenant_id, journal.id)
    _ready(session, journal, lines)
    journal.status = "approved"
    _transition_note(session, principal, journal, "journal_approved")
    return journal_dict(journal, lines)


def reject_journal(session: Session, principal: Principal, journal_id: str, reason: str) -> dict:
    ensure_role(principal, "approver", "admin")
    journal = _lock(session, principal.tenant_id, journal_id)
    if journal.status != "pending_approval":
        raise DomainError(409, "Estado inválido", "Somente lançamento pendente pode ser rejeitado.")
    _ensure_not_creator(journal, principal)
    journal.status = "rejected"
    append_event(
        session,
        tenant_id=principal.tenant_id,
        event_type="other",
        actor_ref=principal.user_id,
        target_type="journal",
        target_ref=journal.id,
        reason=reason,
        metadata={"action": "journal_rejected"},
    )
    return journal_dict(journal, _lines(session, principal.tenant_id, journal.id))


def publish_journal(session: Session, principal: Principal, journal_id: str) -> dict:
    ensure_role(principal, "approver", "admin")
    journal = _lock(session, principal.tenant_id, journal_id)
    if journal.status != "approved":
        raise DomainError(409, "Estado inválido", "Somente lançamento aprovado pode ser publicado.")
    _ensure_not_creator(journal, principal)
    lines = _lines(session, principal.tenant_id, journal.id)
    _ready(session, journal, lines)
    original: JournalEntry | None = None
    if journal.source_type == "reversal":
        if not journal.reverses_journal_id:
            raise DomainError(409, "Estado inválido", "A reversão não aponta para o lançamento original.")
        original = _lock(session, principal.tenant_id, journal.reverses_journal_id)
        if original.status != "published":
            raise DomainError(409, "Estado inválido", "O lançamento original não está publicado.")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    event = append_event(
        session,
        tenant_id=principal.tenant_id,
        event_type="journal_published",
        actor_ref=principal.user_id,
        target_type="journal",
        target_ref=journal.id,
        metadata={"action": "journal_published"},
    )
    journal.status = "published"
    journal.published_at = now
    journal.published_by = principal.user_id
    journal.audit_event_id = event.id
    enqueue(
        session,
        tenant_id=principal.tenant_id,
        event_type="JournalPublished",
        payload={"journal_id": journal.id, "legal_entity_id": journal.legal_entity_id, "period_id": journal.period_id},
    )
    if original is not None:
        original.status = "reversed"
        original.reversal_journal_id = journal.id
        append_event(
            session,
            tenant_id=principal.tenant_id,
            event_type="journal_reversed",
            actor_ref=principal.user_id,
            target_type="journal",
            target_ref=original.id,
            metadata={"action": "journal_reversed", "reversal_journal_id": journal.id},
        )
        enqueue(
            session,
            tenant_id=principal.tenant_id,
            event_type="JournalReversed",
            payload={
                "journal_id": original.id,
                "reversal_journal_id": journal.id,
                "legal_entity_id": original.legal_entity_id,
                "period_id": original.period_id,
            },
        )
    session.flush()
    return journal_dict(journal, lines)


def reverse_journal(session: Session, principal: Principal, journal_id: str) -> dict:
    ensure_role(principal, "preparer", "approver", "admin")
    original = _lock(session, principal.tenant_id, journal_id)
    if original.status != "published":
        raise DomainError(409, "Estado inválido", "Só um lançamento publicado pode ser revertido.")
    require_period(session, principal.tenant_id, original.legal_entity_id, original.period_id, for_posting=True)
    existing = session.scalar(
        select(JournalEntry.id).where(
            JournalEntry.tenant_id == principal.tenant_id,
            JournalEntry.reverses_journal_id == original.id,
            JournalEntry.status != "rejected",
        )
    )
    if existing is not None:
        raise DomainError(409, "Reversão já existe", "Já existe uma reversão não rejeitada para este lançamento.")
    source_lines = _lines(session, principal.tenant_id, original.id)
    reversal_id = new_id("jnl")
    reversal = JournalEntry(
        id=reversal_id,
        schema_version=SCHEMA_VERSION,
        tenant_id=principal.tenant_id,
        legal_entity_id=original.legal_entity_id,
        period_id=original.period_id,
        status="draft",
        currency=original.currency,
        entry_date=original.entry_date,
        description=f"Reversão: {original.description}"[:2000],
        source_type="reversal",
        source_id=original.id,
        source_hash=None,
        reverses_journal_id=original.id,
        created_by=principal.user_id,
    )
    lines: list[JournalLine] = []
    for index, line in enumerate(source_lines, start=1):
        lines.append(
            JournalLine(
                id=new_id("ln"),
                tenant_id=principal.tenant_id,
                journal_id=reversal_id,
                line_no=index,
                account_id=line.account_id,
                side="credit" if line.side == "debit" else "debit",
                amount=line.amount,
                description=line.description,
                cost_center_id=line.cost_center_id,
                dimension_values=dict(line.dimension_values or {}),
            )
        )
    session.add(reversal)
    session.flush()
    session.add_all(lines)
    event = append_event(
        session,
        tenant_id=principal.tenant_id,
        event_type="journal_created",
        actor_ref=principal.user_id,
        target_type="journal",
        target_ref=reversal.id,
        metadata={"action": "reversal_drafted", "reverses_journal_id": original.id},
    )
    reversal.audit_event_id = event.id
    session.flush()
    return journal_dict(reversal, lines)


def _opening_balances(
    session: Session, tenant_id: str, legal_entity_id: str, period: AccountingPeriod, account_id: str | None = None
) -> dict[str, Decimal]:
    """Débito menos crédito dos lançamentos efetivos das competências anteriores, por conta.

    Acumula desde o primeiro lançamento, sem zerar contas de resultado na virada do exercício
    (decisão provisória; pergunta 49 do caderno do contador).
    """
    debit_sum = func.coalesce(func.sum(JournalLine.amount).filter(JournalLine.side == "debit"), 0)
    credit_sum = func.coalesce(func.sum(JournalLine.amount).filter(JournalLine.side == "credit"), 0)
    query = (
        select(JournalLine.account_id, debit_sum, credit_sum)
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_id)
        .join(AccountingPeriod, AccountingPeriod.id == JournalEntry.period_id)
        .where(
            JournalLine.tenant_id == tenant_id,
            JournalEntry.tenant_id == tenant_id,
            JournalEntry.legal_entity_id == legal_entity_id,
            JournalEntry.status.in_(EFFECTIVE_JOURNAL_STATUSES),
            AccountingPeriod.end_date < period.start_date,
        )
        .group_by(JournalLine.account_id)
    )
    if account_id is not None:
        query = query.where(JournalLine.account_id == account_id)
    return {row[0]: Decimal(row[1] or 0) - Decimal(row[2] or 0) for row in session.execute(query).all()}


def trial_balance(session: Session, principal: Principal, legal_entity_id: str, period_id: str) -> dict:
    entity = require_entity(session, principal.tenant_id, legal_entity_id)
    period = require_period(session, principal.tenant_id, entity.id, period_id, for_posting=False)
    matched = JournalEntry.id.is_not(None)
    debit_sum = func.coalesce(func.sum(JournalLine.amount).filter((JournalLine.side == "debit") & matched), 0)
    credit_sum = func.coalesce(func.sum(JournalLine.amount).filter((JournalLine.side == "credit") & matched), 0)
    rows = session.execute(
        select(Account.id, Account.code, Account.name, debit_sum, credit_sum)
        .select_from(Account)
        .outerjoin(
            JournalLine,
            (JournalLine.account_id == Account.id) & (JournalLine.tenant_id == Account.tenant_id),
        )
        .outerjoin(
            JournalEntry,
            (JournalEntry.id == JournalLine.journal_id)
            & (JournalEntry.period_id == period.id)
            & (JournalEntry.status.in_(EFFECTIVE_JOURNAL_STATUSES)),
        )
        .where(
            Account.tenant_id == principal.tenant_id,
            Account.legal_entity_id == entity.id,
            Account.postable.is_(True),
        )
        .group_by(Account.id, Account.code, Account.name)
        .order_by(Account.code)
    ).all()
    opening = _opening_balances(session, principal.tenant_id, entity.id, period)
    debit_total = Decimal("0")
    credit_total = Decimal("0")
    items = []
    for account_id, code, name, debit, credit in rows:
        debit_amount = Decimal(debit or 0)
        credit_amount = Decimal(credit or 0)
        debit_total += debit_amount
        credit_total += credit_amount
        opening_amount = opening.get(account_id, Decimal("0"))
        items.append(
            {
                "account_id": account_id,
                "code": code,
                "name": name,
                "opening_balance": format_signed(opening_amount),
                "debit": format_amount(debit_amount),
                "credit": format_amount(credit_amount),
                "balance": format_signed(debit_amount - credit_amount),
                "closing_balance": format_signed(opening_amount + debit_amount - credit_amount),
            }
        )
    return {
        "legal_entity_id": entity.id,
        "period_id": period.id,
        "currency": entity.currency,
        "rows": items,
        "debit_total": format_amount(debit_total),
        "credit_total": format_amount(credit_total),
    }


def post_imported_journal(
    session: Session,
    *,
    tenant_id: str,
    legal_entity_id: str,
    period_id: str,
    created_by: str,
    published_by: str,
    entry_date: date,
    description: str,
    source_id: str,
    source_hash: str | None,
    lines: list[dict],
) -> str:
    if created_by == published_by:
        raise DomainError(403, "Segregação de funções", "Quem cria o lote não pode publicá-lo.")
    entity = require_entity(session, tenant_id, legal_entity_id)
    period = require_period(session, tenant_id, entity.id, period_id, for_posting=True)
    if not period.start_date <= entry_date <= period.end_date:
        raise DomainError(400, "Data fora da competência", "A data do lançamento precisa cair dentro do período.")
    journal_id = new_id("jnl")
    stored: list[JournalLine] = []
    for index, incoming in enumerate(lines, start=1):
        require_cost_center(session, tenant_id, entity.id, incoming.get("cost_center_id"))
        stored.append(
            JournalLine(
                id=new_id("ln"),
                tenant_id=tenant_id,
                journal_id=journal_id,
                line_no=index,
                account_id=incoming["account_id"],
                side=incoming["side"],
                amount=incoming["amount"],
                description=incoming["description"],
                cost_center_id=incoming.get("cost_center_id"),
                dimension_values={},
            )
        )
    require_postable_accounts(session, tenant_id, entity.id, {line.account_id for line in stored})
    _ensure_balanced(stored)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    journal = JournalEntry(
        id=journal_id,
        schema_version=SCHEMA_VERSION,
        tenant_id=tenant_id,
        legal_entity_id=entity.id,
        period_id=period.id,
        status="draft",
        currency=entity.currency,
        entry_date=entry_date,
        description=description[:2000],
        source_type="import",
        source_id=source_id,
        source_hash=source_hash,
        created_by=created_by,
    )
    session.add(journal)
    session.flush()
    session.add_all(stored)
    session.flush()
    event = append_event(
        session,
        tenant_id=tenant_id,
        event_type="journal_published",
        actor_ref=published_by,
        target_type="journal",
        target_ref=journal.id,
        metadata={"action": "journal_published", "batch_id": source_id.removeprefix("opening:")},
    )
    journal.status = "published"
    journal.published_at = now
    journal.published_by = published_by
    journal.audit_event_id = event.id
    enqueue(
        session,
        tenant_id=tenant_id,
        event_type="JournalPublished",
        payload={"journal_id": journal.id, "legal_entity_id": journal.legal_entity_id, "period_id": journal.period_id},
    )
    session.flush()
    return journal.id


def account_lines(session: Session, principal: Principal, account_id: str, period_id: str) -> dict:
    account = session.scalar(select(Account).where(Account.id == account_id, Account.tenant_id == principal.tenant_id))
    if account is None:
        raise DomainError(404, "Não encontrado", "Conta não encontrada.")
    period = require_period(session, principal.tenant_id, account.legal_entity_id, period_id, for_posting=False)
    opening = _opening_balances(session, principal.tenant_id, account.legal_entity_id, period, account.id)
    rows = session.execute(
        select(
            JournalEntry.id,
            JournalLine.id,
            JournalEntry.entry_date,
            JournalLine.side,
            JournalLine.amount,
            JournalLine.description,
            JournalEntry.status,
            JournalEntry.source_type,
            JournalEntry.source_id,
        )
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_id)
        .where(
            JournalLine.tenant_id == principal.tenant_id,
            JournalLine.account_id == account.id,
            JournalEntry.period_id == period_id,
            JournalEntry.status.in_(EFFECTIVE_JOURNAL_STATUSES),
        )
        .order_by(JournalEntry.entry_date, JournalEntry.id, JournalLine.line_no)
    ).all()
    return {
        "account_id": account.id,
        "code": account.code,
        "name": account.name,
        "period_id": period_id,
        "opening_balance": format_signed(opening.get(account.id, Decimal("0"))),
        "lines": [
            {
                "journal_id": journal_id,
                "line_id": line_id,
                "entry_date": entry_date.isoformat(),
                "side": side,
                "amount": format_amount(amount),
                "description": description,
                "journal_status": status,
                "source_type": source_type,
                "source_id": source_id,
            }
            for journal_id, line_id, entry_date, side, amount, description, status, source_type, source_id in rows
        ],
    }


def trial_balance_csv_export(session: Session, principal: Principal, legal_entity_id: str, period_id: str) -> tuple[str, str]:
    balance = trial_balance(session, principal, legal_entity_id, period_id)
    entity = require_entity(session, principal.tenant_id, legal_entity_id)
    period = require_period(session, principal.tenant_id, entity.id, period_id, for_posting=False)
    content = trial_balance_csv(
        entity_name=entity.name,
        cnpj=entity.cnpj,
        period=period_label(period.fiscal_year, period.month),
        generated_at=datetime.now(timezone.utc),
        balance=balance,
    )
    return f"balancete-{entity.cnpj}-{period.fiscal_year:04d}-{period.month:02d}.csv", content


def account_lines_csv_export(session: Session, principal: Principal, account_id: str, period_id: str) -> tuple[str, str]:
    ledger = account_lines(session, principal, account_id, period_id)
    account = session.scalar(select(Account).where(Account.id == account_id, Account.tenant_id == principal.tenant_id))
    entity = require_entity(session, principal.tenant_id, account.legal_entity_id)
    period = require_period(session, principal.tenant_id, entity.id, period_id, for_posting=False)
    content = account_ledger_csv(
        entity_name=entity.name,
        cnpj=entity.cnpj,
        period=period_label(period.fiscal_year, period.month),
        generated_at=datetime.now(timezone.utc),
        ledger=ledger,
    )
    code = "".join(char if char.isalnum() or char in ".-" else "_" for char in account.code)
    return f"razao-{code}-{period.fiscal_year:04d}-{period.month:02d}.csv", content
