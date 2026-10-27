from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from contabil.audit.hash import content_hash
from contabil.audit.service import append_event
from contabil.closing.checklist import (
    BY_ID,
    CHECKLIST_VERSION,
    CLOSE_SCHEMA_VERSION,
    PENDING_RECONCILIATION,
    ItemDecision,
    blocking_pending,
    decision_error,
    evaluate,
)
from contabil.ledger.service import trial_balance
from contabil.periods.service import lock_period, period_dict
from contabil.platform.auth import apply_tenant, format_utc
from contabil.platform.constants import POSTING_PERIOD_STATUSES
from contabil.platform.errors import DomainError
from contabil.platform.ids import new_id
from contabil.platform.money import format_amount
from contabil.platform.outbox import enqueue
from contabil.platform.principal import Principal, ensure_role
from contabil.tables import (
    AccountingPeriod,
    AuditEvent,
    BankAccount,
    BankTransaction,
    CloseRun,
    CloseRunDecision,
    CloseSnapshot,
    ImportBatch,
    JournalEntry,
    JournalLine,
    ReconciliationCase,
    SourceDocument,
)
from contabil.tenancy.service import require_entity


def open_close_run(session: Session, principal: Principal, period_id: str) -> tuple[bool, dict]:
    ensure_role(principal, "preparer", "approver", "admin")
    period = lock_period(session, principal.tenant_id, period_id)
    if period.status == "closed":
        raise DomainError(409, "Período fechado", "Reabra a competência antes de uma nova execução.")
    if period.status not in POSTING_PERIOD_STATUSES:
        raise DomainError(409, "Estado inválido", "Somente período aberto ou reaberto recebe uma execução de fechamento.")
    existing = _open_run(session, principal.tenant_id, period.id)
    if existing is not None:
        return False, _to_dict(session, principal, existing, period)
    current = session.scalar(
        select(func.max(CloseRun.run_number)).where(
            CloseRun.tenant_id == principal.tenant_id,
            CloseRun.period_id == period.id,
        )
    )
    run = CloseRun(
        id=new_id("cls"),
        tenant_id=principal.tenant_id,
        legal_entity_id=period.legal_entity_id,
        period_id=period.id,
        run_number=int(current or 0) + 1,
        status="open",
        checklist_version=CHECKLIST_VERSION,
        created_by=principal.user_id,
        created_at=_now(),
    )
    session.add(run)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        apply_tenant(session, principal.tenant_id)
        existing = _open_run(session, principal.tenant_id, period_id)
        if existing is None:
            raise
        period = lock_period(session, principal.tenant_id, period_id)
        return False, _to_dict(session, principal, existing, period)
    append_event(
        session,
        tenant_id=principal.tenant_id,
        event_type="other",
        actor_ref=principal.user_id,
        target_type="close_run",
        target_ref=run.id,
        metadata={"action": "close_run_opened", "period_id": period.id, "checklist_version": CHECKLIST_VERSION},
    )
    return True, _to_dict(session, principal, run, period)


def get_close_run(session: Session, principal: Principal, close_run_id: str) -> dict:
    run = _load_run(session, principal.tenant_id, close_run_id)
    period = lock_period(session, principal.tenant_id, run.period_id)
    return _to_dict(session, principal, run, period)


def decide_item(
    session: Session,
    principal: Principal,
    close_run_id: str,
    item_id: str,
    *,
    status: str,
    reason: str | None,
) -> dict:
    ensure_role(principal, "approver", "admin")
    run = _lock_run(session, principal.tenant_id, close_run_id)
    if run.status != "open":
        raise DomainError(409, "Estado inválido", "Só uma execução aberta aceita decisão.")
    spec = BY_ID.get(item_id)
    if spec is None:
        raise DomainError(404, "Não encontrado", "Item de checklist não encontrado.")
    message = decision_error(spec, status, reason)
    if message:
        raise DomainError(400, "Decisão inválida", message)
    cleaned = reason.strip() if reason else None
    existing = session.scalar(
        select(CloseRunDecision).where(
            CloseRunDecision.tenant_id == principal.tenant_id,
            CloseRunDecision.close_run_id == run.id,
            CloseRunDecision.item_id == item_id,
        )
    )
    if existing is None:
        session.add(
            CloseRunDecision(
                id=new_id("cid"),
                tenant_id=principal.tenant_id,
                close_run_id=run.id,
                item_id=item_id,
                status=status,
                reason=cleaned,
                decided_by=principal.user_id,
                decided_at=_now(),
            )
        )
    else:
        existing.status = status
        existing.reason = cleaned
        existing.decided_by = principal.user_id
        existing.decided_at = _now()
    append_event(
        session,
        tenant_id=principal.tenant_id,
        event_type="other",
        actor_ref=principal.user_id,
        target_type="close_run",
        target_ref=run.id,
        reason=cleaned,
        metadata={"action": "close_item_decided", "item_id": item_id, "status": status},
    )
    period = lock_period(session, principal.tenant_id, run.period_id)
    return _to_dict(session, principal, run, period)


def close_run(session: Session, principal: Principal, close_run_id: str) -> dict:
    ensure_role(principal, "approver", "admin")
    run = _lock_run(session, principal.tenant_id, close_run_id)
    period = lock_period(session, principal.tenant_id, run.period_id)
    _finish(session, principal, run, period)
    return _to_dict(session, principal, run, period)


def close_open_run_for_period(session: Session, principal: Principal, period_id: str) -> AccountingPeriod:
    period = lock_period(session, principal.tenant_id, period_id)
    run = _open_run(session, principal.tenant_id, period.id, lock=True)
    if run is None:
        raise DomainError(409, "Fechamento sem execução", "Abra o checklist antes de fechar a competência.")
    _finish(session, principal, run, period)
    return period


def reopen_closed_run(session: Session, tenant_id: str, period_id: str, reason: str) -> None:
    run = session.scalar(
        select(CloseRun)
        .where(CloseRun.tenant_id == tenant_id, CloseRun.period_id == period_id, CloseRun.status == "closed")
        .with_for_update()
    )
    if run is None:
        return
    run.status = "reopened"
    run.reopened_reason = reason


def evidence_package(session: Session, principal: Principal, close_run_id: str) -> dict:
    run = _load_run(session, principal.tenant_id, close_run_id)
    if not run.snapshot_sha256:
        raise DomainError(409, "Pacote indisponível", "A execução ainda não foi fechada.")
    snapshot = session.scalar(
        select(CloseSnapshot).where(
            CloseSnapshot.tenant_id == principal.tenant_id,
            CloseSnapshot.close_run_id == run.id,
        )
    )
    if snapshot is None or content_hash(snapshot.payload) != snapshot.sha256 or snapshot.sha256 != run.snapshot_sha256:
        raise DomainError(500, "Snapshot inconsistente", "O snapshot gravado não confere com o hash.")
    entity = require_entity(session, principal.tenant_id, run.legal_entity_id)
    period = lock_period(session, principal.tenant_id, run.period_id)
    append_event(
        session,
        tenant_id=principal.tenant_id,
        event_type="document_exported",
        actor_ref=principal.user_id,
        target_type="close_run",
        target_ref=run.id,
        metadata={"action": "evidence_package_downloaded", "snapshot_sha256": snapshot.sha256},
    )
    return {
        "manifest": {
            "kind": "evidence_package",
            "schema_version": CLOSE_SCHEMA_VERSION,
            "checklist_version": run.checklist_version,
            "generated_at": format_utc(datetime.now(timezone.utc)),
            "snapshot_sha256": snapshot.sha256,
            "disclaimer": (
                "Este pacote reúne o estado da competência no fechamento. "
                "Não é livro autenticado no SPED e não tem assinatura ICP-Brasil."
            ),
        },
        "snapshot_sha256": snapshot.sha256,
        "legal_entity": {"legal_entity_id": entity.id, "name": entity.name, "cnpj": entity.cnpj},
        "period": period_dict(period),
        "closed_by": run.closed_by,
        "closed_at": format_utc(run.closed_at) if run.closed_at else None,
        "snapshot": snapshot.payload,
    }


def latest_runs(session: Session, tenant_id: str, period_ids: list[str]) -> dict[str, CloseRun]:
    if not period_ids:
        return {}
    rows = session.scalars(
        select(CloseRun)
        .where(CloseRun.tenant_id == tenant_id, CloseRun.period_id.in_(period_ids))
        .order_by(CloseRun.run_number)
    ).all()
    found: dict[str, CloseRun] = {}
    for row in rows:
        found[row.period_id] = row
    return found


def _finish(session: Session, principal: Principal, run: CloseRun, period: AccountingPeriod) -> None:
    if run.status != "open":
        raise DomainError(409, "Estado inválido", "Só uma execução aberta pode ser fechada.")
    if period.status not in POSTING_PERIOD_STATUSES:
        raise DomainError(409, "Estado inválido", "Somente período aberto ou reaberto pode ser fechado.")
    gathered = _gather(session, principal, period)
    checklist = evaluate(gathered["counts"], _decision_map(session, run))
    pending = blocking_pending(checklist)
    if pending:
        raise DomainError(
            409,
            "Fechamento bloqueado",
            "Há itens bloqueantes pendentes.",
            errors=[{"item_id": item["item_id"], "title": item["title"], "detail": item["detail"]} for item in pending],
        )
    closed_at = datetime.now(timezone.utc).replace(microsecond=0)
    head = session.scalar(
        select(AuditEvent.event_hash)
        .where(AuditEvent.tenant_id == principal.tenant_id)
        .order_by(AuditEvent.occurred_at.desc())
        .limit(1)
    )
    payload = {
        "schema_version": CLOSE_SCHEMA_VERSION,
        "checklist_version": run.checklist_version,
        "close_run_id": run.id,
        "run_number": run.run_number,
        "tenant_id": principal.tenant_id,
        "legal_entity_id": period.legal_entity_id,
        "period_id": period.id,
        "fiscal_year": period.fiscal_year,
        "month": period.month,
        "start_date": period.start_date.isoformat(),
        "end_date": period.end_date.isoformat(),
        "closed_by": principal.user_id,
        "closed_at": format_utc(closed_at),
        "trial_balance": gathered["trial_balance"],
        "journals": gathered["journals"],
        "reconciliation": gathered["reconciliation"],
        "import_batches": gathered["import_batches"],
        "documents": gathered["documents"],
        "checklist": checklist,
        "audit_head_hash": head,
    }
    digest = content_hash(payload)
    session.add(
        CloseSnapshot(
            id=new_id("snp"),
            tenant_id=principal.tenant_id,
            close_run_id=run.id,
            payload=payload,
            sha256=digest,
            created_at=closed_at,
        )
    )
    run.status = "closed"
    run.closed_by = principal.user_id
    run.closed_at = closed_at
    run.snapshot_sha256 = digest
    period.status = "closed"
    event = append_event(
        session,
        tenant_id=principal.tenant_id,
        event_type="other",
        actor_ref=principal.user_id,
        target_type="accounting_period",
        target_ref=period.id,
        reason="Fechamento da competência",
        metadata={"action": "period_closed", "close_run_id": run.id, "snapshot_sha256": digest},
    )
    run.audit_event_id = event.id
    enqueue(
        session,
        tenant_id=principal.tenant_id,
        event_type="PeriodClosed",
        payload={"period_id": period.id, "legal_entity_id": period.legal_entity_id, "close_run_id": run.id},
    )
    session.flush()


def _gather(session: Session, principal: Principal, period: AccountingPeriod) -> dict:
    balance = trial_balance(session, principal, period.legal_entity_id, period.id)
    journals = list(
        session.scalars(
            select(JournalEntry)
            .where(JournalEntry.tenant_id == principal.tenant_id, JournalEntry.period_id == period.id)
            .order_by(JournalEntry.entry_date, JournalEntry.id)
        ).all()
    )
    lines: list[JournalLine] = []
    if journals:
        lines = list(
            session.scalars(
                select(JournalLine)
                .where(JournalLine.journal_id.in_([journal.id for journal in journals]))
                .order_by(JournalLine.journal_id, JournalLine.line_no)
            ).all()
        )
    grouped: dict[str, list[dict]] = {}
    for line in lines:
        grouped.setdefault(line.journal_id, []).append(
            {
                "line_no": line.line_no,
                "account_id": line.account_id,
                "side": line.side,
                "amount": format_amount(line.amount),
                "description": line.description,
            }
        )
    journal_payload = [
        {
            "journal_id": journal.id,
            "status": journal.status,
            "entry_date": journal.entry_date.isoformat(),
            "description": journal.description,
            "source_type": journal.source_type,
            "source_id": journal.source_id,
            "reverses_journal_id": journal.reverses_journal_id,
            "published_by": journal.published_by,
            "lines": grouped.get(journal.id, []),
        }
        for journal in journals
    ]
    statuses = Counter(journal.status for journal in journals)
    reconciliation = _reconciliation(session, principal.tenant_id, period)
    batches = list(
        session.scalars(
            select(ImportBatch).where(
                ImportBatch.tenant_id == principal.tenant_id,
                ImportBatch.legal_entity_id == period.legal_entity_id,
                ImportBatch.period_id == period.id,
            )
        ).all()
    )
    competence = f"{period.fiscal_year:04d}-{period.month:02d}"
    documents = list(
        session.scalars(
            select(SourceDocument).where(
                SourceDocument.tenant_id == principal.tenant_id,
                SourceDocument.legal_entity_id == period.legal_entity_id,
                SourceDocument.competence == competence,
            )
        ).all()
    )
    return {
        "counts": {
            "journals_pending_approval": statuses.get("pending_approval", 0),
            "journals_approved": statuses.get("approved", 0),
            "journals_draft": statuses.get("draft", 0),
            "import_batches_open": sum(1 for batch in batches if batch.status not in {"published", "rolled_back"}),
            "reconciliation_pending": reconciliation["pending_count"],
            "documents": len(documents),
            "trial_debit": balance["debit_total"],
            "trial_credit": balance["credit_total"],
        },
        "trial_balance": balance,
        "journals": journal_payload,
        "reconciliation": reconciliation,
        "import_batches": [
            {
                "batch_id": batch.id,
                "status": batch.status,
                "source_system": batch.source_system,
                "rows_received": batch.rows_received,
                "rows_invalid": batch.rows_invalid,
            }
            for batch in batches
        ],
        "documents": [
            {
                "document_id": document.id,
                "document_type": document.document_type,
                "file_name": document.file_name,
                "sha256": document.sha256,
                "competence": document.competence,
            }
            for document in documents
        ],
    }


def _reconciliation(session: Session, tenant_id: str, period: AccountingPeriod) -> dict:
    rows = session.execute(
        select(BankAccount.id, BankAccount.name, func.count())
        .join(BankTransaction, BankTransaction.bank_account_id == BankAccount.id)
        .join(ReconciliationCase, ReconciliationCase.transaction_id == BankTransaction.id)
        .where(
            BankAccount.tenant_id == tenant_id,
            BankAccount.legal_entity_id == period.legal_entity_id,
            BankTransaction.transaction_date >= period.start_date,
            BankTransaction.transaction_date <= period.end_date,
            ReconciliationCase.status.in_(PENDING_RECONCILIATION),
        )
        .group_by(BankAccount.id, BankAccount.name)
        .order_by(BankAccount.name)
    ).all()
    accounts = [
        {"bank_account_id": bank_id, "name": name, "pending_count": int(count)}
        for bank_id, name, count in rows
    ]
    return {"pending_count": sum(item["pending_count"] for item in accounts), "accounts": accounts}


def _to_dict(session: Session, principal: Principal, run: CloseRun, period: AccountingPeriod) -> dict:
    if run.status != "open" and run.snapshot_sha256:
        snapshot = session.scalar(
            select(CloseSnapshot).where(
                CloseSnapshot.tenant_id == run.tenant_id,
                CloseSnapshot.close_run_id == run.id,
            )
        )
        checklist = snapshot.payload.get("checklist", []) if snapshot is not None else []
    else:
        gathered = _gather(session, principal, period)
        checklist = evaluate(gathered["counts"], _decision_map(session, run))
    sha = run.snapshot_sha256
    return {
        "schema_version": CLOSE_SCHEMA_VERSION,
        "close_run_id": run.id,
        "tenant_id": run.tenant_id,
        "legal_entity_id": run.legal_entity_id,
        "period_id": run.period_id,
        "status": run.status,
        "run_number": run.run_number,
        "checklist_version": run.checklist_version,
        "checklist": checklist,
        "snapshot_ref": sha,
        "snapshot_sha256": sha,
        "evidence_package_ref": f"/v1/close-runs/{run.id}/evidence-package" if sha else None,
        "reopened_reason": run.reopened_reason,
        "approved_by": run.closed_by,
        "closed_by": run.closed_by,
        "closed_at": format_utc(run.closed_at) if run.closed_at else None,
        "audit_event_id": run.audit_event_id,
    }


def _decision_map(session: Session, run: CloseRun) -> dict[str, ItemDecision]:
    rows = session.scalars(
        select(CloseRunDecision).where(
            CloseRunDecision.tenant_id == run.tenant_id,
            CloseRunDecision.close_run_id == run.id,
        )
    ).all()
    return {
        row.item_id: ItemDecision(status=row.status, reason=row.reason, decided_by=row.decided_by)
        for row in rows
    }


def _open_run(session: Session, tenant_id: str, period_id: str, *, lock: bool = False) -> CloseRun | None:
    query = select(CloseRun).where(
        CloseRun.tenant_id == tenant_id,
        CloseRun.period_id == period_id,
        CloseRun.status == "open",
    )
    if lock:
        query = query.with_for_update()
    return session.scalar(query)


def _load_run(session: Session, tenant_id: str, close_run_id: str) -> CloseRun:
    run = session.scalar(select(CloseRun).where(CloseRun.id == close_run_id, CloseRun.tenant_id == tenant_id))
    if run is None:
        raise DomainError(404, "Não encontrado", "Execução de fechamento não encontrada.")
    return run


def _lock_run(session: Session, tenant_id: str, close_run_id: str) -> CloseRun:
    run = session.scalar(
        select(CloseRun).where(CloseRun.id == close_run_id, CloseRun.tenant_id == tenant_id).with_for_update()
    )
    if run is None:
        raise DomainError(404, "Não encontrado", "Execução de fechamento não encontrada.")
    return run


def _now() -> datetime:
    return datetime.now(timezone.utc)
