from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from contabil.audit.service import append_event
from contabil.document_requests.service import cancel_reason_error
from contabil.documents.service import DOCUMENT_TYPES, get_document, store_document
from contabil.periods.service import require_period
from contabil.platform.auth import apply_tenant, format_utc
from contabil.platform.constants import POSTING_PERIOD_STATUSES
from contabil.platform.errors import DomainError
from contabil.platform.ids import new_id
from contabil.platform.principal import Principal, ensure_client, ensure_role
from contabil.tables import ClientSubmission, DocumentRequest, DocumentRequestFile, SourceDocument

SUBMISSION_STATUSES = frozenset({"new", "classified", "discarded"})


def create_submission(
    session: Session,
    principal: Principal,
    *,
    file_name: str,
    media_type: str,
    content: bytes,
    note: str | None,
) -> dict:
    ensure_client(principal)
    cleaned = (note or "").strip()
    if len(cleaned) > 500:
        raise DomainError(400, "Nota longa", "A nota tem no máximo 500 caracteres.")
    submission_id = new_id("csub")
    stored, _status = store_document(
        session,
        principal,
        file_name=file_name,
        media_type=media_type,
        content=content,
        document_type="other",
        legal_entity_id=principal.legal_entity_id,
        competence=None,
        source_ref=submission_id,
        source_type="upload",
        allow_client=True,
    )
    apply_tenant(session, principal.tenant_id)
    document = get_document(session, principal, stored["document_id"])
    if document.legal_entity_id != principal.legal_entity_id:
        raise DomainError(409, "Arquivo de outra empresa", "O arquivo já está ligado a outra empresa deste escritório.")
    row = ClientSubmission(
        id=submission_id,
        tenant_id=principal.tenant_id,
        legal_entity_id=principal.legal_entity_id or "",
        document_id=document.id,
        note=cleaned or None,
        submitted_by=principal.user_id,
        status="new",
        classified_request_id=None,
        discard_reason=None,
        created_at=datetime.now(timezone.utc),
    )
    session.add(row)
    session.flush()
    append_event(
        session,
        tenant_id=principal.tenant_id,
        event_type="other",
        actor_ref=principal.user_id,
        target_type="client_submission",
        target_ref=row.id,
        metadata={"action": "client_submission_received", "document_id": document.id},
    )
    return _dict(row, document.file_name)


def list_submissions(session: Session, principal: Principal, *, status: str | None, own_company: bool) -> dict:
    chosen = _statuses(status)
    if own_company:
        ensure_client(principal)
    stmt = select(ClientSubmission, SourceDocument.file_name).join(
        SourceDocument, SourceDocument.id == ClientSubmission.document_id
    ).where(ClientSubmission.tenant_id == principal.tenant_id, ClientSubmission.status.in_(chosen))
    if own_company:
        stmt = stmt.where(ClientSubmission.legal_entity_id == principal.legal_entity_id)
    rows = session.execute(stmt.order_by(ClientSubmission.created_at.desc()).limit(100)).all()
    return {"items": [_dict(row, file_name) for row, file_name in rows]}


def classify_submission(
    session: Session,
    principal: Principal,
    submission_id: str,
    *,
    period_id: str,
    document_type: str,
    title: str,
    due_on: date,
) -> dict:
    ensure_role(principal, "preparer", "approver", "admin")
    if document_type not in DOCUMENT_TYPES:
        raise DomainError(400, "Tipo inválido", "O tipo de documento não é aceito.")
    cleaned = title.strip()
    if not cleaned or len(cleaned) > 200:
        raise DomainError(400, "Título inválido", "O pedido precisa de um título com até 200 caracteres.")
    row = _locked(session, principal, submission_id)
    if row.status != "new":
        raise DomainError(409, "Estado inválido", "Este envio já foi classificado ou descartado.")
    period = require_period(session, principal.tenant_id, row.legal_entity_id, period_id, for_posting=False)
    if period.status not in POSTING_PERIOD_STATUSES:
        raise DomainError(409, "Período fechado", "Só um período aberto ou reaberto aceita o envio.")
    now = datetime.now(timezone.utc)
    request = DocumentRequest(
        id=new_id("dreq"),
        tenant_id=principal.tenant_id,
        legal_entity_id=row.legal_entity_id,
        period_id=period.id,
        document_type=document_type,
        title=cleaned,
        due_on=due_on,
        status="received",
        document_id=row.document_id,
        requested_by=principal.user_id,
        received_by=row.submitted_by,
        confirmed_by=None,
        cancelled_by=None,
        cancel_reason=None,
        created_at=now,
        updated_at=now,
    )
    session.add(request)
    session.add(
        DocumentRequestFile(
            id=new_id("dfile"),
            tenant_id=principal.tenant_id,
            request_id=request.id,
            document_id=row.document_id,
            uploaded_by=row.submitted_by,
            uploaded_at=now,
            state="active",
            returned_reason=None,
        )
    )
    row.status = "classified"
    row.classified_request_id = request.id
    session.flush()
    append_event(
        session,
        tenant_id=principal.tenant_id,
        event_type="other",
        actor_ref=principal.user_id,
        target_type="client_submission",
        target_ref=row.id,
        metadata={"action": "client_submission_classified", "document_request_id": request.id},
    )
    return {"submission_id": row.id, "document_request_id": request.id, "status": row.status}


def discard_submission(session: Session, principal: Principal, submission_id: str, reason: str) -> dict:
    ensure_role(principal, "preparer", "approver", "admin")
    problem = cancel_reason_error(reason)
    if problem:
        raise DomainError(400, "Motivo curto", problem)
    row = _locked(session, principal, submission_id)
    if row.status != "new":
        raise DomainError(409, "Estado inválido", "Este envio já foi classificado ou descartado.")
    row.status = "discarded"
    row.discard_reason = reason.strip()
    session.flush()
    append_event(
        session,
        tenant_id=principal.tenant_id,
        event_type="other",
        actor_ref=principal.user_id,
        target_type="client_submission",
        target_ref=row.id,
        reason=row.discard_reason,
        metadata={"action": "client_submission_discarded"},
    )
    return {"submission_id": row.id, "status": row.status}


def _statuses(raw: str | None) -> list[str]:
    if raw is None or not raw.strip():
        return ["new"]
    chosen = [item.strip() for item in raw.split(",") if item.strip()]
    if not chosen or any(item not in SUBMISSION_STATUSES for item in chosen):
        raise DomainError(400, "Estado inválido", "Filtre por new, classified ou discarded.")
    return list(dict.fromkeys(chosen))


def _locked(session: Session, principal: Principal, submission_id: str) -> ClientSubmission:
    row = session.scalar(
        select(ClientSubmission)
        .where(ClientSubmission.id == submission_id, ClientSubmission.tenant_id == principal.tenant_id)
        .with_for_update()
    )
    if row is None:
        raise DomainError(404, "Não encontrado", "Envio do cliente não encontrado.")
    return row


def _dict(row: ClientSubmission, file_name: str) -> dict:
    return {
        "submission_id": row.id,
        "legal_entity_id": row.legal_entity_id,
        "document_id": row.document_id,
        "file_name": file_name,
        "note": row.note,
        "status": row.status,
        "classified_request_id": row.classified_request_id,
        "discard_reason": row.discard_reason,
        "created_at": format_utc(row.created_at),
    }
