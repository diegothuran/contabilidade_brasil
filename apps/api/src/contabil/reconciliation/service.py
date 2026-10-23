from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from contabil.audit.service import append_event
from contabil.documents.service import open_content
from contabil.ledger.schemas import JournalCreate, LineIn
from contabil.ledger.service import create_journal
from contabil.platform.constants import EFFECTIVE_JOURNAL_STATUSES, POSTING_PERIOD_STATUSES, SCHEMA_VERSION
from contabil.platform.correlation import correlation_id
from contabil.platform.errors import DomainError
from contabil.platform.ids import new_id
from contabil.platform.money import format_amount, format_signed
from contabil.platform.outbox import enqueue
from contabil.platform.principal import Principal, ensure_role
from contabil.platform.settings import get_settings
from contabil.reconciliation.matching import find_candidates
from contabil.reconciliation.statement_parser import StatementParseError, fingerprint, parse_statement
from contabil.tables import (
    Account,
    AccountingPeriod,
    BankAccount,
    BankStatement,
    BankTransaction,
    JournalEntry,
    JournalLine,
    Operation,
    ReconciliationCase,
    ReconciliationMatch,
    SourceDocument,
)
from contabil.tenancy.service import before_cursor, encode_cursor, page_limit, require_entity

_CASE_STATUSES = frozenset({"open", "suggested", "approved", "rejected", "reversed", "ignored"})
_PENDING_STATUSES = frozenset({"open", "suggested", "reversed"})
_DECIDED_AWAY = frozenset({"open", "suggested", "rejected"})


def bank_account_dict(row: BankAccount) -> dict:
    return {
        "bank_account_id": row.id,
        "legal_entity_id": row.legal_entity_id,
        "account_id": row.account_id,
        "name": row.name,
        "bank_code": row.bank_code,
        "branch": row.branch,
        "account_number_masked": row.account_number_masked,
        "currency": row.currency,
        "active": row.active,
    }


def statement_dict(row: BankStatement) -> dict:
    return {
        "statement_id": row.id,
        "bank_account_id": row.bank_account_id,
        "document_id": row.document_id,
        "format": row.format,
        "status": row.status,
        "start_date": row.start_date.isoformat() if row.start_date else None,
        "end_date": row.end_date.isoformat() if row.end_date else None,
        "closing_balance": format_signed(row.closing_balance) if row.closing_balance is not None else None,
        "transactions_received": row.transactions_received,
        "transactions_new": row.transactions_new,
        "transactions_duplicate": row.transactions_duplicate,
        "error_code": row.error_code,
        "error_message": row.error_message,
    }


def case_dict(session: Session, case: ReconciliationCase) -> dict:
    transaction = session.scalar(
        select(BankTransaction).where(BankTransaction.id == case.transaction_id, BankTransaction.tenant_id == case.tenant_id)
    )
    bank = session.scalar(select(BankAccount).where(BankAccount.id == case.bank_account_id, BankAccount.tenant_id == case.tenant_id))
    if transaction is None or bank is None:
        raise DomainError(404, "Não encontrado", "Caso de conciliação não encontrado.")
    return {
        "schema_version": case.schema_version,
        "case_id": case.id,
        "tenant_id": case.tenant_id,
        "legal_entity_id": bank.legal_entity_id,
        "account_id": case.account_id,
        "bank_account_id": case.bank_account_id,
        "status": case.status,
        "bank_transaction": {
            "transaction_id": transaction.id,
            "date": transaction.transaction_date.isoformat(),
            "amount": format_amount(transaction.amount),
            "direction": transaction.direction,
            "description": transaction.description,
            "external_id": transaction.external_id,
        },
        "candidates": [_candidate(item) for item in case.candidates],
        "selected_candidate_id": case.selected_candidate_id,
        "approved_by": case.approved_by,
        "audit_event_id": case.audit_event_id,
        "journal_id": case.journal_id,
        "reason": case.reason,
    }


def create_bank_account(session: Session, principal: Principal, body) -> dict:
    ensure_role(principal, "preparer", "approver", "admin")
    entity = require_entity(session, principal.tenant_id, body.legal_entity_id)
    account = session.scalar(select(Account).where(Account.id == body.account_id, Account.tenant_id == principal.tenant_id))
    if account is None or account.legal_entity_id != entity.id:
        raise DomainError(400, "Conta inválida", "A conta do razão não pertence a esta empresa.")
    if account.account_type != "asset" or not account.postable or not account.active:
        raise DomainError(400, "Conta inválida", "A conta banco precisa ser um ativo postável e ativo.")
    existing = session.scalar(
        select(BankAccount).where(
            BankAccount.tenant_id == principal.tenant_id,
            BankAccount.legal_entity_id == entity.id,
            BankAccount.account_id == account.id,
        )
    )
    if existing is not None:
        raise DomainError(409, "Conta já cadastrada", "Esta conta do razão já está ligada a uma conta banco.")
    row = BankAccount(
        id=new_id("bank"),
        tenant_id=principal.tenant_id,
        legal_entity_id=entity.id,
        account_id=account.id,
        name=body.name.strip(),
        bank_code=body.bank_code.strip(),
        branch=body.branch.strip(),
        account_number_masked=body.account_number_masked,
        currency=entity.currency,
        active=True,
    )
    session.add(row)
    session.flush()
    return bank_account_dict(row)


def list_bank_accounts(session: Session, principal: Principal, legal_entity_id: str) -> dict:
    require_entity(session, principal.tenant_id, legal_entity_id)
    rows = session.scalars(
        select(BankAccount)
        .where(BankAccount.tenant_id == principal.tenant_id, BankAccount.legal_entity_id == legal_entity_id)
        .order_by(BankAccount.name, BankAccount.id)
    ).all()
    return {"items": [bank_account_dict(row) for row in rows]}


def create_statement(session: Session, principal: Principal, bank_account_id: str, document_id: str) -> dict:
    ensure_role(principal, "preparer", "approver", "admin")
    bank = _bank_or_404(session, principal.tenant_id, bank_account_id)
    document = session.scalar(
        select(SourceDocument).where(SourceDocument.id == document_id, SourceDocument.tenant_id == principal.tenant_id)
    )
    if document is None or document.legal_entity_id != bank.legal_entity_id:
        raise DomainError(400, "Documento inválido", "O arquivo não pertence a esta empresa.")
    if document.document_type != "bank_statement":
        raise DomainError(400, "Documento inválido", "O arquivo precisa ser um extrato bancário.")
    statement = BankStatement(
        id=new_id("stmt"),
        tenant_id=principal.tenant_id,
        bank_account_id=bank.id,
        document_id=document.id,
        format="csv" if document.file_name.lower().endswith(".csv") else "ofx",
        status="received",
        transactions_received=0,
        transactions_new=0,
        transactions_duplicate=0,
        created_by=principal.user_id,
    )
    session.add(statement)
    operation = Operation(
        id=new_id("op"),
        tenant_id=principal.tenant_id,
        kind="bank_statement_import",
        status="accepted",
        correlation_id=correlation_id.get() or "",
        target_ref=statement.id,
    )
    session.add(operation)
    session.flush()
    enqueue(
        session,
        tenant_id=principal.tenant_id,
        event_type="BankStatementReceived",
        payload={"statement_id": statement.id, "operation_id": operation.id, "bank_account_id": bank.id},
    )
    return {
        "operation_id": operation.id,
        "status": operation.status,
        "correlation_id": operation.correlation_id,
        "statement_id": statement.id,
    }


def list_statements(session: Session, principal: Principal, bank_account_id: str) -> dict:
    bank = _bank_or_404(session, principal.tenant_id, bank_account_id)
    rows = session.scalars(
        select(BankStatement)
        .where(BankStatement.tenant_id == principal.tenant_id, BankStatement.bank_account_id == bank.id)
        .order_by(BankStatement.created_at.desc(), BankStatement.id.desc())
    ).all()
    return {"items": [statement_dict(row) for row in rows]}


def get_statement(session: Session, principal: Principal, statement_id: str) -> dict:
    return statement_dict(_statement_or_404(session, principal.tenant_id, statement_id))


def import_statement(session: Session, tenant_id: str, payload: dict) -> None:
    statement_id = payload.get("statement_id")
    if not statement_id:
        return
    statement = session.scalar(
        select(BankStatement)
        .where(BankStatement.id == statement_id, BankStatement.tenant_id == tenant_id)
        .with_for_update()
    )
    if statement is None or statement.status in {"parsed", "failed"}:
        return
    document = session.scalar(
        select(SourceDocument).where(SourceDocument.id == statement.document_id, SourceDocument.tenant_id == tenant_id)
    )
    bank = session.scalar(
        select(BankAccount).where(BankAccount.id == statement.bank_account_id, BankAccount.tenant_id == tenant_id)
    )
    if document is None or bank is None:
        _fail_statement(statement, "UNSUPPORTED_FORMAT", "Documento do extrato não encontrado.")
        return
    try:
        content = b"".join(open_content(document))
        parsed = parse_statement(content)
    except StatementParseError as exc:
        _fail_statement(statement, exc.code, exc.message)
        return
    received = 0
    new_count = 0
    duplicate_count = 0
    for item in parsed.transactions:
        received += 1
        digest = fingerprint(
            bank.id,
            posted_on=item.date,
            amount=item.amount,
            direction=item.direction,
            description=item.description,
            external_id=item.external_id,
        )
        existing = session.scalar(
            select(BankTransaction).where(
                BankTransaction.tenant_id == tenant_id,
                BankTransaction.bank_account_id == bank.id,
                BankTransaction.fingerprint == digest,
            )
        )
        if existing is not None:
            duplicate_count += 1
            _ensure_case(session, tenant_id, bank, existing)
            continue
        transaction = BankTransaction(
            id=new_id("btx"),
            tenant_id=tenant_id,
            bank_account_id=bank.id,
            statement_id=statement.id,
            transaction_date=item.date,
            amount=item.amount,
            direction=item.direction,
            description=item.description,
            external_id=item.external_id,
            fingerprint=digest,
        )
        try:
            with session.begin_nested():
                session.add(transaction)
                session.flush()
        except IntegrityError:
            duplicate_count += 1
            raced = session.scalar(
                select(BankTransaction).where(
                    BankTransaction.tenant_id == tenant_id,
                    BankTransaction.bank_account_id == bank.id,
                    BankTransaction.fingerprint == digest,
                )
            )
            if raced is not None:
                _ensure_case(session, tenant_id, bank, raced)
            continue
        new_count += 1
        _ensure_case(session, tenant_id, bank, transaction)
    dates = [item.date for item in parsed.transactions]
    statement.format = parsed.format
    statement.status = "parsed"
    statement.start_date = parsed.start_date or (min(dates) if dates else None)
    statement.end_date = parsed.end_date or (max(dates) if dates else None)
    statement.closing_balance = parsed.closing_balance
    statement.transactions_received = received
    statement.transactions_new = new_count
    statement.transactions_duplicate = duplicate_count
    statement.error_code = None
    statement.error_message = None
    session.flush()


def list_cases(
    session: Session,
    principal: Principal,
    *,
    bank_account_id: str,
    status: str | None,
    cursor: str | None,
    limit: int,
) -> dict:
    bank = _bank_or_404(session, principal.tenant_id, bank_account_id)
    if status is not None and status not in _CASE_STATUSES:
        raise DomainError(400, "Estado inválido", "O filtro de estado não é válido.")
    limit = page_limit(limit)
    stmt = select(ReconciliationCase).where(
        ReconciliationCase.tenant_id == principal.tenant_id,
        ReconciliationCase.bank_account_id == bank.id,
    )
    if status is not None:
        stmt = stmt.where(ReconciliationCase.status == status)
    comparison = before_cursor(ReconciliationCase.created_at, ReconciliationCase.id, cursor)
    if comparison is not None:
        stmt = stmt.where(comparison)
    rows = session.scalars(stmt.order_by(ReconciliationCase.created_at.desc(), ReconciliationCase.id.desc()).limit(limit + 1)).all()
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        rows = rows[:limit]
        next_cursor = encode_cursor(last.created_at, last.id)
    return {"items": [case_dict(session, row) for row in rows], "next_cursor": next_cursor}


def get_case(session: Session, principal: Principal, case_id: str) -> dict:
    return case_dict(session, _case_or_404(session, principal.tenant_id, case_id))


def approve_case(session: Session, principal: Principal, case_id: str, candidate_id: str) -> dict:
    ensure_role(principal, "approver", "admin")
    case = _lock_case(session, principal.tenant_id, case_id)
    if case.status not in {"open", "suggested"}:
        raise DomainError(409, "Estado inválido", "Somente um caso aberto ou sugerido pode ser aprovado.")
    transaction = _transaction_of(session, case)
    bank = _bank_or_404(session, principal.tenant_id, case.bank_account_id)
    known = {item.get("candidate_id") for item in case.candidates}
    line, journal = _validated_line(session, principal.tenant_id, bank, transaction, candidate_id)
    if candidate_id not in known:
        candidates = list(case.candidates)
        candidates.append(
            {
                "candidate_id": line.id,
                "candidate_type": "journal",
                "score": 1.0,
                "explanation": ["Escolhido manualmente"],
                "matched_fields": ["amount", "account"],
            }
        )
        case.candidates = candidates[:20]
    _link_line(session, case, line, principal.user_id, transaction.amount)
    event = append_event(
        session,
        tenant_id=principal.tenant_id,
        event_type="reconciliation_approved",
        actor_ref=principal.user_id,
        target_type="reconciliation_case",
        target_ref=case.id,
        metadata={"action": "reconciliation_approved"},
    )
    case.selected_candidate_id = line.id
    case.approved_by = principal.user_id
    case.audit_event_id = event.id
    case.journal_id = journal.id
    case.status = "approved"
    case.reason = None
    case.updated_at = _now()
    enqueue(
        session,
        tenant_id=principal.tenant_id,
        event_type="ReconciliationApproved",
        payload={"case_id": case.id, "journal_id": journal.id},
    )
    session.flush()
    return case_dict(session, case)


def reject_case(session: Session, principal: Principal, case_id: str, reason: str) -> dict:
    return _decide_without_match(session, principal, case_id, "rejected", "reconciliation_rejected", reason)


def ignore_case(session: Session, principal: Principal, case_id: str, reason: str) -> dict:
    return _decide_without_match(session, principal, case_id, "ignored", "reconciliation_ignored", reason)


def reverse_case(session: Session, principal: Principal, case_id: str, reason: str) -> dict:
    ensure_role(principal, "approver", "admin")
    case = _lock_case(session, principal.tenant_id, case_id)
    if case.status != "approved":
        raise DomainError(409, "Estado inválido", "Somente uma conciliação aprovada pode ser revertida.")
    matches = session.scalars(
        select(ReconciliationMatch).where(
            ReconciliationMatch.tenant_id == principal.tenant_id,
            ReconciliationMatch.case_id == case.id,
            ReconciliationMatch.active.is_(True),
        )
    ).all()
    for match in matches:
        match.active = False
    event = append_event(
        session,
        tenant_id=principal.tenant_id,
        event_type="other",
        actor_ref=principal.user_id,
        target_type="reconciliation_case",
        target_ref=case.id,
        reason=reason,
        metadata={"action": "reconciliation_reversed"},
    )
    case.status = "reversed"
    case.reason = reason
    case.audit_event_id = event.id
    case.updated_at = _now()
    session.flush()
    return case_dict(session, case)


def resuggest_case(session: Session, principal: Principal, case_id: str) -> dict:
    ensure_role(principal, "preparer", "approver", "admin")
    case = _lock_case(session, principal.tenant_id, case_id)
    if case.status not in {"open", "rejected", "reversed"}:
        raise DomainError(409, "Estado inválido", "Só um caso aberto, rejeitado ou revertido pode receber nova sugestão.")
    if _active_match(session, case.id) is not None:
        raise DomainError(409, "Estado inválido", "Desfaça o vínculo antes de sugerir de novo.")
    transaction = _transaction_of(session, case)
    bank = _bank_or_404(session, principal.tenant_id, case.bank_account_id)
    _apply_suggestions(session, case, transaction, bank)
    case.selected_candidate_id = None
    case.approved_by = None
    case.updated_at = _now()
    session.flush()
    return case_dict(session, case)


def create_journal_from_case(session: Session, principal: Principal, case_id: str, body) -> dict:
    ensure_role(principal, "preparer", "admin")
    case = _lock_case(session, principal.tenant_id, case_id)
    if case.status in {"approved", "ignored"}:
        raise DomainError(409, "Estado inválido", "Este caso não aceita um lançamento novo.")
    if _active_match(session, case.id) is not None:
        raise DomainError(409, "Estado inválido", "Este caso já está conciliado.")
    if case.journal_id:
        existing = session.scalar(
            select(JournalEntry).where(JournalEntry.id == case.journal_id, JournalEntry.tenant_id == principal.tenant_id)
        )
        if existing is not None and existing.status != "reversed":
            raise DomainError(409, "Lançamento já existe", "Este caso já tem um lançamento. Publique-o ou reverta esse lançamento antes de criar outro.")
    transaction = _transaction_of(session, case)
    bank = _bank_or_404(session, principal.tenant_id, case.bank_account_id)
    period = session.scalar(
        select(AccountingPeriod).where(
            AccountingPeriod.tenant_id == principal.tenant_id,
            AccountingPeriod.legal_entity_id == bank.legal_entity_id,
            AccountingPeriod.start_date <= transaction.transaction_date,
            AccountingPeriod.end_date >= transaction.transaction_date,
            AccountingPeriod.status.in_(POSTING_PERIOD_STATUSES),
        )
    )
    if period is None:
        raise DomainError(409, "Período fechado", "Não há período aberto para a data da transação.")
    description = (body.description or transaction.description or "Conciliação bancária").strip()[:2000]
    amount = format_amount(transaction.amount)
    bank_side = "debit" if transaction.direction == "inflow" else "credit"
    counterpart_side = "credit" if bank_side == "debit" else "debit"
    created = create_journal(
        session,
        principal,
        JournalCreate(
            legal_entity_id=bank.legal_entity_id,
            period_id=period.id,
            currency=bank.currency,
            entry_date=transaction.transaction_date,
            description=description,
            source_type="bank",
            source_id=case.id,
            lines=[
                LineIn(account_id=bank.account_id, side=bank_side, amount=amount, description=description[:1000], cost_center_id=body.cost_center_id),
                LineIn(
                    account_id=body.counterpart_account_id,
                    side=counterpart_side,
                    amount=amount,
                    description=description[:1000],
                    cost_center_id=body.cost_center_id,
                ),
            ],
        ),
    )
    case.journal_id = created["journal_id"]
    case.updated_at = _now()
    session.flush()
    return created


def resolve_case_from_journal(session: Session, tenant_id: str, payload: dict) -> None:
    journal_id = payload.get("journal_id")
    if not journal_id:
        return
    journal = session.scalar(select(JournalEntry).where(JournalEntry.id == journal_id, JournalEntry.tenant_id == tenant_id))
    if journal is None or journal.source_type != "bank" or journal.status != "published" or not journal.published_by:
        return
    case = session.scalar(
        select(ReconciliationCase).where(ReconciliationCase.id == journal.source_id, ReconciliationCase.tenant_id == tenant_id)
    )
    if case is None or _active_match(session, case.id) is not None:
        return
    bank = session.scalar(select(BankAccount).where(BankAccount.id == case.bank_account_id, BankAccount.tenant_id == tenant_id))
    transaction = session.scalar(
        select(BankTransaction).where(BankTransaction.id == case.transaction_id, BankTransaction.tenant_id == tenant_id)
    )
    if bank is None or transaction is None:
        return
    side = "debit" if transaction.direction == "inflow" else "credit"
    line = session.scalar(
        select(JournalLine).where(
            JournalLine.tenant_id == tenant_id,
            JournalLine.journal_id == journal.id,
            JournalLine.account_id == bank.account_id,
            JournalLine.side == side,
        )
    )
    if line is None:
        return
    if _line_taken(session, tenant_id, line.id):
        return
    try:
        with session.begin_nested():
            session.add(
                ReconciliationMatch(
                    id=new_id("match"),
                    tenant_id=tenant_id,
                    case_id=case.id,
                    journal_line_id=line.id,
                    amount=transaction.amount,
                    active=True,
                )
            )
            session.flush()
    except IntegrityError:
        return
    event = append_event(
        session,
        tenant_id=tenant_id,
        event_type="reconciliation_approved",
        actor_ref=journal.published_by,
        target_type="reconciliation_case",
        target_ref=case.id,
        metadata={"action": "reconciliation_approved"},
    )
    case.candidates = [
        {
            "candidate_id": line.id,
            "candidate_type": "journal",
            "score": 1.0,
            "explanation": ["Lançamento criado a partir desta transação e publicado"],
            "matched_fields": ["amount", "account"],
        }
    ]
    case.selected_candidate_id = line.id
    case.approved_by = journal.published_by
    case.audit_event_id = event.id
    case.journal_id = journal.id
    case.status = "approved"
    case.reason = None
    case.updated_at = _now()
    enqueue(
        session,
        tenant_id=tenant_id,
        event_type="ReconciliationApproved",
        payload={"case_id": case.id, "journal_id": journal.id},
    )
    session.flush()


def bank_account_summary(session: Session, principal: Principal, bank_account_id: str, period_id: str) -> dict:
    bank = _bank_or_404(session, principal.tenant_id, bank_account_id)
    period = session.scalar(
        select(AccountingPeriod).where(AccountingPeriod.id == period_id, AccountingPeriod.tenant_id == principal.tenant_id)
    )
    if period is None or period.legal_entity_id != bank.legal_entity_id:
        raise DomainError(404, "Não encontrado", "Período não encontrado.")
    effective = session.execute(
        select(JournalLine.side, JournalLine.amount)
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_id)
        .where(
            JournalEntry.tenant_id == principal.tenant_id,
            JournalEntry.legal_entity_id == bank.legal_entity_id,
            JournalEntry.period_id == period.id,
            JournalEntry.status.in_(EFFECTIVE_JOURNAL_STATUSES),
            JournalLine.account_id == bank.account_id,
        )
    ).all()
    debit = Decimal("0")
    credit = Decimal("0")
    for side, amount in effective:
        if side == "debit":
            debit += amount
        else:
            credit += amount
    taken = (
        select(ReconciliationMatch.id)
        .where(
            ReconciliationMatch.journal_line_id == JournalLine.id,
            ReconciliationMatch.tenant_id == principal.tenant_id,
            ReconciliationMatch.active.is_(True),
        )
        .exists()
    )
    unmatched = session.scalars(
        select(JournalLine.amount)
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_id)
        .where(
            JournalEntry.tenant_id == principal.tenant_id,
            JournalEntry.period_id == period.id,
            JournalEntry.status.in_(EFFECTIVE_JOURNAL_STATUSES),
            JournalLine.account_id == bank.account_id,
            ~taken,
        )
    ).all()
    pending = session.execute(
        select(BankTransaction.direction, BankTransaction.amount)
        .join(ReconciliationCase, ReconciliationCase.transaction_id == BankTransaction.id)
        .where(
            BankTransaction.tenant_id == principal.tenant_id,
            BankTransaction.bank_account_id == bank.id,
            BankTransaction.transaction_date >= period.start_date,
            BankTransaction.transaction_date <= period.end_date,
            ReconciliationCase.status.in_(_PENDING_STATUSES),
        )
    ).all()
    inflow_count = 0
    outflow_count = 0
    inflow_total = Decimal("0")
    outflow_total = Decimal("0")
    for direction, amount in pending:
        if direction == "inflow":
            inflow_count += 1
            inflow_total += amount
        else:
            outflow_count += 1
            outflow_total += amount
    latest = session.scalar(
        select(BankStatement)
        .where(
            BankStatement.tenant_id == principal.tenant_id,
            BankStatement.bank_account_id == bank.id,
            BankStatement.status == "parsed",
        )
        .order_by(BankStatement.created_at.desc())
    )
    statement_balance = None
    if latest is not None and latest.closing_balance is not None:
        statement_balance = format_signed(latest.closing_balance)
    return {
        "bank_account_id": bank.id,
        "period_id": period.id,
        "ledger_balance": format_signed(debit - credit),
        "statement_balance": statement_balance,
        "pending_inflow_count": inflow_count,
        "pending_inflow_total": format_amount(inflow_total),
        "pending_outflow_count": outflow_count,
        "pending_outflow_total": format_amount(outflow_total),
        "unmatched_ledger_count": len(unmatched),
        "unmatched_ledger_total": format_amount(sum(unmatched, Decimal("0"))),
    }


def _decide_without_match(session: Session, principal: Principal, case_id: str, status: str, action: str, reason: str) -> dict:
    ensure_role(principal, "preparer", "approver", "admin")
    case = _lock_case(session, principal.tenant_id, case_id)
    if case.status not in _DECIDED_AWAY:
        raise DomainError(409, "Estado inválido", "Este caso não aceita essa decisão.")
    if _active_match(session, case.id) is not None:
        raise DomainError(409, "Estado inválido", "Desfaça o vínculo antes de rejeitar ou ignorar.")
    event = append_event(
        session,
        tenant_id=principal.tenant_id,
        event_type="other",
        actor_ref=principal.user_id,
        target_type="reconciliation_case",
        target_ref=case.id,
        reason=reason,
        metadata={"action": action},
    )
    case.status = status
    case.reason = reason
    case.audit_event_id = event.id
    case.updated_at = _now()
    session.flush()
    return case_dict(session, case)


def _ensure_case(session: Session, tenant_id: str, bank: BankAccount, transaction: BankTransaction) -> ReconciliationCase:
    existing = session.scalar(
        select(ReconciliationCase).where(
            ReconciliationCase.transaction_id == transaction.id,
            ReconciliationCase.tenant_id == tenant_id,
        )
    )
    if existing is not None:
        return existing
    case = ReconciliationCase(
        id=new_id("case"),
        schema_version=SCHEMA_VERSION,
        tenant_id=tenant_id,
        bank_account_id=bank.id,
        account_id=bank.account_id,
        transaction_id=transaction.id,
        status="open",
        candidates=[],
        created_at=_now(),
        updated_at=_now(),
    )
    session.add(case)
    session.flush()
    _apply_suggestions(session, case, transaction, bank)
    return case


def _apply_suggestions(session: Session, case: ReconciliationCase, transaction: BankTransaction, bank: BankAccount) -> None:
    candidates = find_candidates(
        session,
        tenant_id=case.tenant_id,
        bank=bank,
        transaction=transaction,
        tolerance_days=get_settings().reconciliation_date_tolerance_days,
    )
    case.candidates = candidates
    case.status = "suggested" if candidates else "open"
    case.updated_at = _now()


def _validated_line(
    session: Session,
    tenant_id: str,
    bank: BankAccount,
    transaction: BankTransaction,
    candidate_id: str,
) -> tuple[JournalLine, JournalEntry]:
    line = session.scalar(select(JournalLine).where(JournalLine.id == candidate_id, JournalLine.tenant_id == tenant_id))
    if line is None:
        raise DomainError(404, "Não encontrado", "Linha do razão não encontrada.")
    if line.account_id != bank.account_id:
        raise DomainError(400, "Conta inválida", "A linha não pertence à conta banco.")
    expected = "debit" if transaction.direction == "inflow" else "credit"
    if line.side != expected:
        raise DomainError(400, "Lado inválido", "A linha não está no mesmo lado da transação bancária.")
    if line.amount != transaction.amount:
        raise DomainError(409, "Valor diferente", "Nesta fase o vínculo é 1:1 e o valor da linha precisa ser igual ao da transação.")
    journal = session.scalar(select(JournalEntry).where(JournalEntry.id == line.journal_id, JournalEntry.tenant_id == tenant_id))
    if journal is None or journal.status not in EFFECTIVE_JOURNAL_STATUSES:
        raise DomainError(409, "Estado inválido", "A linha precisa estar em um lançamento publicado.")
    if _line_taken(session, tenant_id, line.id):
        raise DomainError(409, "Linha já conciliada", "Esta linha do razão já tem conciliação ativa.")
    return line, journal


def _link_line(session: Session, case: ReconciliationCase, line: JournalLine, _actor: str, amount: Decimal) -> None:
    try:
        with session.begin_nested():
            session.add(
                ReconciliationMatch(
                    id=new_id("match"),
                    tenant_id=case.tenant_id,
                    case_id=case.id,
                    journal_line_id=line.id,
                    amount=amount,
                    active=True,
                )
            )
            session.flush()
    except IntegrityError as exc:
        raise DomainError(409, "Linha já conciliada", "Esta linha do razão já tem conciliação ativa.") from exc


def _line_taken(session: Session, tenant_id: str, journal_line_id: str) -> bool:
    return (
        session.scalar(
            select(ReconciliationMatch.id).where(
                ReconciliationMatch.tenant_id == tenant_id,
                ReconciliationMatch.journal_line_id == journal_line_id,
                ReconciliationMatch.active.is_(True),
            )
        )
        is not None
    )


def _active_match(session: Session, case_id: str) -> ReconciliationMatch | None:
    return session.scalar(
        select(ReconciliationMatch).where(ReconciliationMatch.case_id == case_id, ReconciliationMatch.active.is_(True))
    )


def _transaction_of(session: Session, case: ReconciliationCase) -> BankTransaction:
    transaction = session.scalar(
        select(BankTransaction).where(BankTransaction.id == case.transaction_id, BankTransaction.tenant_id == case.tenant_id)
    )
    if transaction is None:
        raise DomainError(404, "Não encontrado", "Transação bancária não encontrada.")
    return transaction


def _fail_statement(statement: BankStatement, code: str, message: str) -> None:
    statement.status = "failed"
    statement.error_code = code[:100]
    statement.error_message = message[:1000]


def _bank_or_404(session: Session, tenant_id: str, bank_account_id: str) -> BankAccount:
    bank = session.scalar(select(BankAccount).where(BankAccount.id == bank_account_id, BankAccount.tenant_id == tenant_id))
    if bank is None:
        raise DomainError(404, "Não encontrado", "Conta banco não encontrada.")
    return bank


def _statement_or_404(session: Session, tenant_id: str, statement_id: str) -> BankStatement:
    statement = session.scalar(select(BankStatement).where(BankStatement.id == statement_id, BankStatement.tenant_id == tenant_id))
    if statement is None:
        raise DomainError(404, "Não encontrado", "Extrato não encontrado.")
    return statement


def _case_or_404(session: Session, tenant_id: str, case_id: str) -> ReconciliationCase:
    case = session.scalar(select(ReconciliationCase).where(ReconciliationCase.id == case_id, ReconciliationCase.tenant_id == tenant_id))
    if case is None:
        raise DomainError(404, "Não encontrado", "Caso de conciliação não encontrado.")
    return case


def _lock_case(session: Session, tenant_id: str, case_id: str) -> ReconciliationCase:
    case = session.scalar(
        select(ReconciliationCase)
        .where(ReconciliationCase.id == case_id, ReconciliationCase.tenant_id == tenant_id)
        .with_for_update()
    )
    if case is None:
        raise DomainError(404, "Não encontrado", "Caso de conciliação não encontrado.")
    return case


def _candidate(raw: dict) -> dict:
    item = {
        "candidate_id": raw["candidate_id"],
        "candidate_type": raw["candidate_type"],
        "score": float(raw["score"]),
        "explanation": list(raw["explanation"]),
    }
    if raw.get("matched_fields") is not None:
        item["matched_fields"] = list(raw["matched_fields"])
    return item


def _now() -> datetime:
    return datetime.now(timezone.utc)
