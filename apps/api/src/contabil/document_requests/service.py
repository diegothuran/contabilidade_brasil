from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import func, select, tuple_
from sqlalchemy.orm import Session

from contabil.audit.service import append_event
from contabil.documents.service import DOCUMENT_TYPES, get_document, store_document
from contabil.periods.service import require_period
from contabil.platform.auth import apply_tenant, format_utc
from contabil.platform.constants import POSTING_PERIOD_STATUSES, SCHEMA_VERSION
from contabil.platform.errors import DomainError
from contabil.platform.ids import new_id
from contabil.platform.principal import Principal, ensure_client, ensure_role
from contabil.identity.notices import enqueue_notice
from contabil.tables import (
    AccountingPeriod,
    AuditEvent,
    DocumentRequest,
    DocumentRequestComment,
    DocumentRequestFile,
    LegalEntity,
    SourceDocument,
)
from contabil.tenancy.service import before_cursor, encode_cursor, page_limit, require_entity

BLOCKING_REQUEST_STATUSES = frozenset({"open", "received"})
QUEUE_STATUSES = frozenset({"open", "received", "confirmed", "cancelled"})
ACTIVE_FILE_LIMIT = 10
COMMENT_STATUSES = frozenset({"open", "received"})

TRANSITIONS = {
    ("open", "receive"): "received",
    ("open", "cancel"): "cancelled",
    ("received", "confirm"): "confirmed",
    ("received", "cancel"): "cancelled",
    ("received", "return"): "open",
}


def upload_target(status: str) -> str:
    if status == "received":
        return "received"
    return next_status(status, "receive")


def blocks_close(status: str) -> bool:
    return status in BLOCKING_REQUEST_STATUSES


def portal_summary(rows: list[tuple[str, date]], today: date) -> dict:
    open_count = 0
    received_count = 0
    overdue = 0
    upcoming: list[date] = []
    for status, due_on in rows:
        if status == "open":
            open_count += 1
        elif status == "received":
            received_count += 1
        if status in BLOCKING_REQUEST_STATUSES and due_on < today:
            overdue += 1
        elif status in BLOCKING_REQUEST_STATUSES:
            upcoming.append(due_on)
    return {
        "open": open_count,
        "received": received_count,
        "overdue": overdue,
        "next_due_on": min(upcoming).isoformat() if upcoming else None,
    }


def client_timestamps(
    status: str,
    updated_at: datetime | None,
    *,
    received_at: datetime | None,
    confirmed_at: datetime | None,
) -> tuple[datetime | None, datetime | None]:
    if status == "received" and received_at is None:
        received_at = updated_at
    if status == "confirmed" and confirmed_at is None:
        confirmed_at = updated_at
    return received_at, confirmed_at


def queue_statuses(raw: str | None) -> list[str]:
    if raw is None or not raw.strip():
        return ["open", "received"]
    chosen = [item.strip() for item in raw.split(",") if item.strip()]
    if not chosen or any(item not in QUEUE_STATUSES for item in chosen):
        raise DomainError(400, "Estado inválido", "Filtre por open, received, confirmed ou cancelled.")
    return list(dict.fromkeys(chosen))


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
    enqueue_notice(session, principal.tenant_id, row.id, "created", date.today())
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


def _queue_item(row: DocumentRequest, entity: LegalEntity, period: AccountingPeriod) -> dict:
    item = request_dict(row)
    item["legal_entity_name"] = entity.name
    item["cnpj"] = entity.cnpj
    item["period"] = f"{period.month:02d}/{period.fiscal_year}"
    item["blocks_close"] = blocks_close(row.status)
    return item


def _encode_queue_cursor(due_on: date, status: str, row_id: str) -> str:
    from base64 import urlsafe_b64encode

    return urlsafe_b64encode(f"{due_on.isoformat()}|{status}|{row_id}".encode()).decode()


def _decode_queue_cursor(cursor: str) -> tuple[date, str, str]:
    from base64 import urlsafe_b64decode

    try:
        raw = urlsafe_b64decode(cursor.encode()).decode()
        stamp, status, row_id = raw.split("|", 2)
        if status not in QUEUE_STATUSES:
            raise ValueError(status)
        return date.fromisoformat(stamp), status, row_id
    except (ValueError, UnicodeError) as exc:
        raise DomainError(400, "Cursor inválido", "O cursor de paginação não é válido.") from exc


def list_queue(
    session: Session,
    principal: Principal,
    *,
    status: str | None,
    due_before: date | None,
    year: int | None,
    month: int | None,
    cursor: str | None,
    limit: int,
) -> dict:
    if (year is None) != (month is None):
        raise DomainError(400, "Competência incompleta", "Informe o ano e o mês juntos.")
    if month is not None and not 1 <= month <= 12:
        raise DomainError(400, "Mês inválido", "O mês fica entre 1 e 12.")
    chosen = queue_statuses(status)
    limit = page_limit(limit)
    stmt = (
        select(DocumentRequest, LegalEntity, AccountingPeriod)
        .join(LegalEntity, LegalEntity.id == DocumentRequest.legal_entity_id)
        .join(AccountingPeriod, AccountingPeriod.id == DocumentRequest.period_id)
        .where(
            DocumentRequest.tenant_id == principal.tenant_id,
            DocumentRequest.status.in_(chosen),
        )
    )
    if due_before is not None:
        stmt = stmt.where(DocumentRequest.due_on <= due_before)
    if year is not None and month is not None:
        stmt = stmt.where(AccountingPeriod.fiscal_year == year, AccountingPeriod.month == month)
    if cursor is not None:
        due_on, status_mark, row_id = _decode_queue_cursor(cursor)
        stmt = stmt.where(
            tuple_(DocumentRequest.due_on, DocumentRequest.status, DocumentRequest.id)
            > tuple_(due_on, status_mark, row_id)
        )
    rows = session.execute(
        stmt.order_by(DocumentRequest.due_on.asc(), DocumentRequest.status.asc(), DocumentRequest.id.asc()).limit(limit + 1)
    ).all()
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1][0]
        rows = rows[:limit]
        next_cursor = _encode_queue_cursor(last.due_on, last.status, last.id)
    return {"items": [_queue_item(row, entity, period) for row, entity, period in rows], "next_cursor": next_cursor}


def list_client_requests(
    session: Session,
    principal: Principal,
    *,
    status: str | None,
    cursor: str | None,
    limit: int,
) -> dict:
    ensure_client(principal)
    chosen = queue_statuses(status)
    limit = page_limit(limit)
    entity = _client_entity(session, principal)
    owned = (
        DocumentRequest.tenant_id == principal.tenant_id,
        DocumentRequest.legal_entity_id == principal.legal_entity_id,
    )
    counted = session.execute(select(DocumentRequest.status, DocumentRequest.due_on).where(*owned)).all()
    stmt = (
        select(DocumentRequest, AccountingPeriod, SourceDocument.file_name)
        .join(AccountingPeriod, AccountingPeriod.id == DocumentRequest.period_id)
        .outerjoin(SourceDocument, SourceDocument.id == DocumentRequest.document_id)
        .where(*owned, DocumentRequest.status.in_(chosen))
    )
    if cursor is not None:
        due_on, row_id = _decode_client_cursor(cursor)
        stmt = stmt.where(tuple_(DocumentRequest.due_on, DocumentRequest.id) > tuple_(due_on, row_id))
    rows = session.execute(stmt.order_by(DocumentRequest.due_on.asc(), DocumentRequest.id.asc()).limit(limit + 1)).all()
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1][0]
        rows = rows[:limit]
        next_cursor = _encode_client_cursor(last.due_on, last.id)
    moments = _request_moments(session, principal.tenant_id, [row.id for row, _period, _name in rows])
    items = []
    for row, period, file_name in rows:
        received_at, confirmed_at = client_timestamps(
            row.status,
            row.updated_at,
            received_at=moments.get(row.id, {}).get("received_at"),
            confirmed_at=moments.get(row.id, {}).get("confirmed_at"),
        )
        item = _queue_item(row, entity, period)
        item["file_name"] = file_name
        item["received_at"] = format_utc(received_at) if received_at else None
        item["confirmed_at"] = format_utc(confirmed_at) if confirmed_at else None
        items.append(item)
    return {
        "items": items,
        "next_cursor": next_cursor,
        "summary": portal_summary([(item_status, due_on) for item_status, due_on in counted], date.today()),
    }


def _encode_client_cursor(due_on: date, row_id: str) -> str:
    from base64 import urlsafe_b64encode

    return urlsafe_b64encode(f"{due_on.isoformat()}|{row_id}".encode()).decode()


def _decode_client_cursor(cursor: str) -> tuple[date, str]:
    from base64 import urlsafe_b64decode

    try:
        raw = urlsafe_b64decode(cursor.encode()).decode()
        stamp, row_id = raw.split("|", 1)
        if not row_id:
            raise ValueError(row_id)
        return date.fromisoformat(stamp), row_id
    except (ValueError, UnicodeError) as exc:
        raise DomainError(400, "Cursor inválido", "O cursor de paginação não é válido.") from exc


def _request_moments(session: Session, tenant_id: str, request_ids: list[str]) -> dict[str, dict[str, datetime]]:
    if not request_ids:
        return {}
    events = session.scalars(
        select(AuditEvent).where(
            AuditEvent.tenant_id == tenant_id,
            AuditEvent.target_type == "document_request",
            AuditEvent.target_ref.in_(request_ids),
        )
    ).all()
    found: dict[str, dict[str, datetime]] = {}
    for event in events:
        action = (event.details or {}).get("action")
        bucket = found.setdefault(event.target_ref, {})
        if action == "document_request_received":
            bucket["received_at"] = event.occurred_at
        elif action == "document_request_confirmed":
            bucket["confirmed_at"] = event.occurred_at
    return found


def _client_entity(session: Session, principal: Principal) -> LegalEntity:
    entity = session.get(LegalEntity, principal.legal_entity_id)
    if entity is None or entity.tenant_id != principal.tenant_id:
        raise DomainError(403, "Ação não permitida", "O acesso de cliente precisa estar ligado a uma empresa.")
    return entity


def client_document(session: Session, principal: Principal, document_id: str):
    ensure_client(principal)
    linked = session.scalar(
        select(DocumentRequestFile.id)
        .join(DocumentRequest, DocumentRequest.id == DocumentRequestFile.request_id)
        .where(
            DocumentRequest.tenant_id == principal.tenant_id,
            DocumentRequest.legal_entity_id == principal.legal_entity_id,
            DocumentRequestFile.document_id == document_id,
        )
    )
    if linked is None:
        linked = session.scalar(
            select(DocumentRequest.id).where(
                DocumentRequest.tenant_id == principal.tenant_id,
                DocumentRequest.legal_entity_id == principal.legal_entity_id,
                DocumentRequest.document_id == document_id,
            )
        )
    if linked is None:
        raise DomainError(404, "Não encontrado", "Pedido de documento não encontrado.")
    return get_document(session, principal, document_id)


def receive_content(
    session: Session,
    principal: Principal,
    request_id: str,
    *,
    file_name: str,
    media_type: str,
    content: bytes,
) -> dict:
    client_access = principal.roles == frozenset({"client"})
    if client_access:
        ensure_client(principal)
    else:
        ensure_role(principal, "preparer", "approver", "admin")
    row = _locked(session, principal, request_id)
    if client_access and row.legal_entity_id != principal.legal_entity_id:
        raise DomainError(404, "Não encontrado", "Pedido de documento não encontrado.")
    period = _open_period(session, principal, row.legal_entity_id, row.period_id)
    upload_target(row.status)
    if _active_files(session, principal.tenant_id, row.id) >= ACTIVE_FILE_LIMIT:
        raise DomainError(409, "Limite de arquivos", "Este pedido já tem 10 arquivos ativos.")
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
        allow_client=client_access,
    )
    apply_tenant(session, principal.tenant_id)
    row = _locked(session, principal, request_id)
    upload_target(row.status)
    if _active_files(session, principal.tenant_id, row.id) >= ACTIVE_FILE_LIMIT:
        raise DomainError(409, "Limite de arquivos", "Este pedido já tem 10 arquivos ativos.")
    document = get_document(session, principal, stored["document_id"])
    if document.legal_entity_id != row.legal_entity_id:
        raise DomainError(409, "Arquivo de outra empresa", "O arquivo já está ligado a outra empresa deste escritório.")
    row.status = "received"
    row.document_id = document.id
    row.received_by = principal.user_id
    row.updated_at = datetime.now(timezone.utc)
    session.add(
        DocumentRequestFile(
            id=new_id("dfile"),
            tenant_id=principal.tenant_id,
            request_id=row.id,
            document_id=document.id,
            uploaded_by=principal.user_id,
            uploaded_at=row.updated_at,
            state="active",
            returned_reason=None,
        )
    )
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
    if _confirm_blocked(session, principal.tenant_id, row):
        raise DomainError(409, "Arquivo ausente", "Confirme o pedido só depois que houver um arquivo ativo.")
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


def return_request(session: Session, principal: Principal, request_id: str, reason: str) -> dict:
    ensure_role(principal, "approver", "admin")
    problem = cancel_reason_error(reason)
    if problem:
        raise DomainError(400, "Motivo curto", problem)
    row = _locked(session, principal, request_id)
    _open_period(session, principal, row.legal_entity_id, row.period_id)
    next_status(row.status, "return")
    cleaned = reason.strip()
    now = datetime.now(timezone.utc)
    for item in _files(session, principal.tenant_id, row.id):
        if item.state == "active":
            item.state = "returned"
            item.returned_reason = cleaned
    row.status = "open"
    row.updated_at = now
    session.flush()
    append_event(
        session,
        tenant_id=principal.tenant_id,
        event_type="other",
        actor_ref=principal.user_id,
        target_type="document_request",
        target_ref=row.id,
        reason=cleaned,
        metadata={"action": "document_request_returned"},
    )
    enqueue_notice(session, principal.tenant_id, row.id, "returned", date.today())
    return request_dict(row)


def add_comment(session: Session, principal: Principal, request_id: str, body: str) -> dict:
    cleaned = body.strip()
    if not cleaned or len(cleaned) > 1000:
        raise DomainError(400, "Comentário inválido", "Escreva uma mensagem com até 1000 caracteres.")
    client_access = principal.roles == frozenset({"client"})
    if client_access:
        ensure_client(principal)
    else:
        ensure_role(principal, "preparer", "approver", "admin")
    row = _locked(session, principal, request_id)
    if client_access and row.legal_entity_id != principal.legal_entity_id:
        raise DomainError(404, "Não encontrado", "Pedido de documento não encontrado.")
    if row.status not in COMMENT_STATUSES:
        raise DomainError(409, "Estado inválido", "Este pedido não aceita comentário.")
    comment = DocumentRequestComment(
        id=new_id("dcom"),
        tenant_id=principal.tenant_id,
        request_id=row.id,
        author_ref=principal.user_id,
        author_kind="client" if client_access else "office",
        body=cleaned,
        created_at=datetime.now(timezone.utc),
    )
    session.add(comment)
    session.flush()
    append_event(
        session,
        tenant_id=principal.tenant_id,
        event_type="other",
        actor_ref=principal.user_id,
        target_type="document_request",
        target_ref=row.id,
        metadata={"action": "document_request_commented", "comment_id": comment.id},
    )
    return _comment_dict(comment)


def list_comments(session: Session, principal: Principal, request_id: str) -> dict:
    row = _visible_request(session, principal, request_id)
    return {"items": [_comment_dict(item) for item in _comments(session, principal.tenant_id, row.id)]}


def request_detail(session: Session, principal: Principal, request_id: str) -> dict:
    row = _visible_request(session, principal, request_id)
    period = session.get(AccountingPeriod, row.period_id)
    entity = session.get(LegalEntity, row.legal_entity_id)
    if period is None or entity is None:
        raise DomainError(404, "Não encontrado", "Pedido de documento não encontrado.")
    body = _queue_item(row, entity, period)
    body["files"] = [_file_dict(item, name) for item, name in _named_files(session, principal.tenant_id, row.id)]
    body["comments"] = [_comment_dict(item) for item in _comments(session, principal.tenant_id, row.id)]
    return body


def _visible_request(session: Session, principal: Principal, request_id: str) -> DocumentRequest:
    client_access = principal.roles == frozenset({"client"})
    if client_access:
        ensure_client(principal)
    row = session.scalar(
        select(DocumentRequest).where(DocumentRequest.id == request_id, DocumentRequest.tenant_id == principal.tenant_id)
    )
    if row is None or (client_access and row.legal_entity_id != principal.legal_entity_id):
        raise DomainError(404, "Não encontrado", "Pedido de documento não encontrado.")
    return row


def _active_files(session: Session, tenant_id: str, request_id: str) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(DocumentRequestFile)
            .where(
                DocumentRequestFile.tenant_id == tenant_id,
                DocumentRequestFile.request_id == request_id,
                DocumentRequestFile.state == "active",
            )
        )
        or 0
    )


def _confirm_blocked(session: Session, tenant_id: str, row: DocumentRequest) -> bool:
    tracked = int(
        session.scalar(
            select(func.count())
            .select_from(DocumentRequestFile)
            .where(DocumentRequestFile.tenant_id == tenant_id, DocumentRequestFile.request_id == row.id)
        )
        or 0
    )
    if tracked == 0:
        return not row.document_id
    return _active_files(session, tenant_id, row.id) < 1


def _files(session: Session, tenant_id: str, request_id: str) -> list[DocumentRequestFile]:
    return list(
        session.scalars(
            select(DocumentRequestFile).where(
                DocumentRequestFile.tenant_id == tenant_id,
                DocumentRequestFile.request_id == request_id,
            )
        ).all()
    )


def _named_files(session: Session, tenant_id: str, request_id: str) -> list[tuple[DocumentRequestFile, str]]:
    return list(
        session.execute(
            select(DocumentRequestFile, SourceDocument.file_name)
            .join(SourceDocument, SourceDocument.id == DocumentRequestFile.document_id)
            .where(DocumentRequestFile.tenant_id == tenant_id, DocumentRequestFile.request_id == request_id)
            .order_by(DocumentRequestFile.uploaded_at.asc(), DocumentRequestFile.id.asc())
        ).all()
    )


def _comments(session: Session, tenant_id: str, request_id: str) -> list[DocumentRequestComment]:
    return list(
        session.scalars(
            select(DocumentRequestComment)
            .where(DocumentRequestComment.tenant_id == tenant_id, DocumentRequestComment.request_id == request_id)
            .order_by(DocumentRequestComment.created_at.asc(), DocumentRequestComment.id.asc())
        ).all()
    )


def _file_dict(row: DocumentRequestFile, file_name: str) -> dict:
    return {
        "file_id": row.id,
        "document_id": row.document_id,
        "file_name": file_name,
        "state": row.state,
        "uploaded_by": row.uploaded_by,
        "uploaded_at": format_utc(row.uploaded_at),
        "returned_reason": row.returned_reason,
    }


def _comment_dict(row: DocumentRequestComment) -> dict:
    return {
        "comment_id": row.id,
        "author_ref": row.author_ref,
        "author_kind": row.author_kind,
        "body": row.body,
        "created_at": format_utc(row.created_at),
    }


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
