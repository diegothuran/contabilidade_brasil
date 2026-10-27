from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from contabil.audit.service import append_event
from contabil.documents.service import DOCUMENT_TYPES, get_document, store_document
from contabil.periods.service import require_period
from contabil.platform.auth import apply_tenant, format_utc
from contabil.platform.constants import POSTING_PERIOD_STATUSES, SCHEMA_VERSION
from contabil.platform.errors import DomainError
from contabil.platform.ids import new_id
from contabil.platform.principal import Principal, ensure_role
from contabil.tables import DocumentRequest
from contabil.tenancy.service import before_cursor, encode_cursor, page_limit, require_entity

TRANSITIONS = {
    ("open", "receive"): "received",
    ("open", "cancel"): "cancelled",
    ("received", "confirm"): "confirmed",
    ("received", "cancel"): "cancelled",
}


def next_status(status: str, action: str) -> str:
    found = TRANSITIONS.get((status, action))
    if found is None:
        raise DomainError(409, "Estado inválido", "Este pedido não aceita essa ação.")
    return found


def cancel_reason_error(reason: str | None) -> str | None:
    if reason is None or len(reason.strip()) < 10:
        return "Informe um motivo com pelo menos 10 caracteres."
    return None


def request_dict(row: DocumentRequest) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "document_request_id": row.id,
        "tenant_id": row.tenant_id,
        "legal_entity_id": row.legal_entity_id,
        "period_id": row.period_id,
        "document_type": row.document_type,
        "title": row.title,
        "due_on": row.due_on.isoformat(),
        "status": row.status,
        "document_id": row.document_id,
        "requested_by": row.requested_by,
        "received_by": row.received_by,
        "confirmed_by": row.confirmed_by,
        "cancelled_by": row.cancelled_by,
        "cancel_reason": row.cancel_reason,
        "created_at": format_utc(row.created_at),
    }


def create_request(
    session: Session,
    principal: Principal,
    *,
    legal_entity_id: str,
    period_id: str,
    document_type: str,
    title: str,
    due_on: date,
) -> dict:
    ensure_role(principal, "preparer", "admin")
    cleaned = title.strip()
    if not cleaned or len(cleaned) > 200:
        raise DomainError(400, "Título inválido", "O pedido precisa de um título com até 200 caracteres.")
    if document_type not in DOCUMENT_TYPES:
        raise DomainError(400, "Tipo inválido", "O tipo de documento não é aceito.")
    require_entity(session, principal.tenant_id, legal_entity_id)
    period = _open_period(session, principal, legal_entity_id, period_id)
    now = datetime.now(timezone.utc)
    row = DocumentRequest(
        id=new_id("dreq"),
        tenant_id=principal.tenant_id,
        legal_entity_id=legal_entity_id,
        period_id=period.id,
        document_type=document_type,
        title=cleaned,
        due_on=due_on,
        status="open",
        document_id=None,
        requested_by=principal.user_id,
        received_by=None,
        confirmed_by=None,
        cancelled_by=None,
        cancel_reason=None,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    append_event(
        session,
        tenant_id=principal.tenant_id,
        event_type="other",
        actor_ref=principal.user_id,
        target_type="document_request",
        target_ref=row.id,
        metadata={"action": "document_request_opened", "period_id": period.id, "document_type": document_type},
    )
    return request_dict(row)


def list_requests(
    session: Session,
    principal: Principal,
    *,
    legal_entity_id: str,
    period_id: str,
    cursor: str | None,
    limit: int,
) -> dict:
    require_entity(session, principal.tenant_id, legal_entity_id)
    require_period(session, principal.tenant_id, legal_entity_id, period_id, for_posting=False)
    limit = page_limit(limit)
    stmt = select(DocumentRequest).where(
        DocumentRequest.tenant_id == principal.tenant_id,
        DocumentRequest.legal_entity_id == legal_entity_id,
        DocumentRequest.period_id == period_id,
    )
    comparison = before_cursor(DocumentRequest.created_at, DocumentRequest.id, cursor)
    if comparison is not None:
        stmt = stmt.where(comparison)
    rows = session.scalars(stmt.order_by(DocumentRequest.created_at.desc(), DocumentRequest.id.desc()).limit(limit + 1)).all()
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        rows = rows[:limit]
        next_cursor = encode_cursor(last.created_at, last.id)
    return {"items": [request_dict(row) for row in rows], "next_cursor": next_cursor}


def receive_content(
    session: Session,
    principal: Principal,
    request_id: str,
    *,
    file_name: str,
    media_type: str,
    content: bytes,
) -> dict:
    ensure_role(principal, "preparer", "approver", "admin")
    row = _locked(session, principal, request_id)
    period = _open_period(session, principal, row.legal_entity_id, row.period_id)
    next_status(row.status, "receive")
    competence = f"{period.fiscal_year:04d}-{period.month:02d}"
    stored, _status = store_document(
        session,
        principal,
        file_name=file_name,
        media_type=media_type,
        content=content,
        document_type=row.document_type,
        legal_entity_id=row.legal_entity_id,
        competence=competence,
        source_ref=row.id,
        source_type="upload",
    )
    apply_tenant(session, principal.tenant_id)
    row = _locked(session, principal, request_id)
    next_status(row.status, "receive")
    document = get_document(session, principal, stored["document_id"])
    if document.legal_entity_id != row.legal_entity_id:
        raise DomainError(409, "Arquivo de outra empresa", "O arquivo já está ligado a outra empresa deste escritório.")
    row.status = "received"
    row.document_id = document.id
    row.received_by = principal.user_id
    row.updated_at = datetime.now(timezone.utc)
    session.flush()
    append_event(
        session,
        tenant_id=principal.tenant_id,
        event_type="other",
        actor_ref=principal.user_id,
        target_type="document_request",
        target_ref=row.id,
        metadata={"action": "document_request_received", "document_id": document.id, "sha256": document.sha256},
    )
    return request_dict(row)


def confirm_request(session: Session, principal: Principal, request_id: str) -> dict:
    ensure_role(principal, "approver", "admin")
    row = _locked(session, principal, request_id)
    _open_period(session, principal, row.legal_entity_id, row.period_id)
    next_status(row.status, "confirm")
    if not row.document_id:
        raise DomainError(409, "Arquivo ausente", "Confirme o pedido só depois que o arquivo chegar.")
    row.status = "confirmed"
    row.confirmed_by = principal.user_id
    row.updated_at = datetime.now(timezone.utc)
    session.flush()
    append_event(
        session,
        tenant_id=principal.tenant_id,
        event_type="other",
        actor_ref=principal.user_id,
        target_type="document_request",
        target_ref=row.id,
        metadata={"action": "document_request_confirmed", "document_id": row.document_id},
    )
    return request_dict(row)


def cancel_request(session: Session, principal: Principal, request_id: str, reason: str) -> dict:
    ensure_role(principal, "preparer", "approver", "admin")
    problem = cancel_reason_error(reason)
    if problem:
        raise DomainError(400, "Motivo curto", problem)
    row = _locked(session, principal, request_id)
    _open_period(session, principal, row.legal_entity_id, row.period_id)
    next_status(row.status, "cancel")
    cleaned = reason.strip()
    row.status = "cancelled"
    row.cancelled_by = principal.user_id
    row.cancel_reason = cleaned
    row.updated_at = datetime.now(timezone.utc)
    session.flush()
    append_event(
        session,
        tenant_id=principal.tenant_id,
        event_type="other",
        actor_ref=principal.user_id,
        target_type="document_request",
        target_ref=row.id,
        reason=cleaned,
        metadata={"action": "document_request_cancelled"},
    )
    return request_dict(row)


def _open_period(session: Session, principal: Principal, legal_entity_id: str, period_id: str):
    period = require_period(session, principal.tenant_id, legal_entity_id, period_id, for_posting=False)
    if period.status not in POSTING_PERIOD_STATUSES:
        raise DomainError(409, "Período fechado", "Só um período aberto ou reaberto aceita pedido de documento.")
    return period


def _locked(session: Session, principal: Principal, request_id: str) -> DocumentRequest:
    row = session.scalar(
        select(DocumentRequest)
        .where(DocumentRequest.id == request_id, DocumentRequest.tenant_id == principal.tenant_id)
        .with_for_update()
    )
    if row is None:
        raise DomainError(404, "Não encontrado", "Pedido de documento não encontrado.")
    return row
