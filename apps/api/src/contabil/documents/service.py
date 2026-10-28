from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from contabil.audit.service import append_event
from contabil.platform.auth import apply_tenant, format_utc
from contabil.platform.constants import SCHEMA_VERSION
from contabil.platform.errors import DomainError
from contabil.platform.ids import new_id
from contabil.platform.outbox import enqueue
from contabil.platform.principal import Principal, ensure_role
from contabil.platform.settings import get_settings
from contabil.platform.storage import document_key, get_object_store, object_ref
from contabil.tables import SourceDocument
from contabil.tenancy.service import before_cursor, encode_cursor, page_limit, require_entity

DOCUMENT_TYPES = frozenset(
    {"invoice", "bank_statement", "receipt", "contract", "tax_file", "government_response", "journal_support", "other"}
)
_COMPETENCE = re.compile(r"^[0-9]{4}-[0-9]{2}$")
RETENTION_POLICY = "retention_pending"


def document_dict(document: SourceDocument) -> dict:
    return {
        "schema_version": document.schema_version,
        "document_id": document.id,
        "tenant_id": document.tenant_id,
        "legal_entity_id": document.legal_entity_id,
        "document_type": document.document_type,
        "competence": document.competence,
        "original": {
            "file_name": document.file_name,
            "media_type": document.media_type,
            "sha256": document.sha256,
            "object_ref": document.object_ref,
            "size_bytes": document.size_bytes,
        },
        "provenance": {
            "source_type": document.source_type,
            "source_ref": document.source_ref,
            "received_at": format_utc(document.received_at),
            "received_by": document.received_by,
        },
        "retention": {
            "policy_id": document.retention_policy_id,
            "legal_hold": document.legal_hold,
            "retain_until": document.retain_until.isoformat() if document.retain_until else None,
        },
        "classification": document.classification,
        "derived_versions": document.derived_versions or [],
    }


def _find_hash(session: Session, tenant_id: str, sha256: str) -> SourceDocument | None:
    return session.scalar(select(SourceDocument).where(SourceDocument.tenant_id == tenant_id, SourceDocument.sha256 == sha256))


def store_document(
    session: Session,
    principal: Principal,
    *,
    file_name: str,
    media_type: str,
    content: bytes,
    document_type: str,
    legal_entity_id: str | None,
    competence: str | None,
    source_ref: str | None,
    source_type: str = "upload",
    allow_client: bool = False,
) -> tuple[dict, int]:
    if allow_client and principal.roles == frozenset({"client"}):
        if not principal.legal_entity_id or legal_entity_id != principal.legal_entity_id:
            raise DomainError(404, "Não encontrado", "Pedido de documento não encontrado.")
    else:
        ensure_role(principal, "preparer", "approver", "admin")
    if document_type not in DOCUMENT_TYPES:
        raise DomainError(400, "Tipo inválido", "O tipo de documento não é aceito.")
    if competence is not None and _COMPETENCE.fullmatch(competence) is None:
        raise DomainError(400, "Competência inválida", "Use a competência no formato AAAA-MM.")
    if legal_entity_id:
        require_entity(session, principal.tenant_id, legal_entity_id)
    settings = get_settings()
    if len(content) > settings.max_upload_bytes:
        raise DomainError(413, "Arquivo grande demais", "O arquivo excede o limite de upload deste ambiente.")
    if not file_name or len(file_name) > 300:
        raise DomainError(400, "Nome inválido", "O arquivo precisa de um nome com até 300 caracteres.")
    digest = hashlib.sha256(content).hexdigest()
    existing = _find_hash(session, principal.tenant_id, digest)
    if existing is not None:
        return document_dict(existing), 200
    key = document_key(principal.tenant_id, digest)
    store = get_object_store()
    import io

    store.put(key, io.BytesIO(content), len(content), media_type or "application/octet-stream")
    document = SourceDocument(
        id=new_id("doc"),
        schema_version=SCHEMA_VERSION,
        tenant_id=principal.tenant_id,
        legal_entity_id=legal_entity_id,
        document_type=document_type,
        competence=competence,
        file_name=file_name,
        media_type=media_type or "application/octet-stream",
        sha256=digest,
        object_ref=object_ref(settings.object_storage_bucket, key),
        size_bytes=len(content),
        source_type=source_type,
        source_ref=source_ref,
        received_at=datetime.now(timezone.utc),
        received_by=principal.user_id,
        retention_policy_id=RETENTION_POLICY,
        legal_hold=False,
        retain_until=None,
        classification=None,
        derived_versions=[],
    )
    session.add(document)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        apply_tenant(session, principal.tenant_id)
        raced = _find_hash(session, principal.tenant_id, digest)
        if raced is None:
            raise
        return document_dict(raced), 200
    append_event(
        session,
        tenant_id=principal.tenant_id,
        event_type="other",
        actor_ref=principal.user_id,
        target_type="source_document",
        target_ref=document.id,
        metadata={"action": "document_received", "sha256": digest, "document_type": document_type},
    )
    enqueue(session, tenant_id=principal.tenant_id, event_type="DocumentReceived", payload={"document_id": document.id})
    return document_dict(document), 201


def list_documents(
    session: Session,
    principal: Principal,
    *,
    legal_entity_id: str | None,
    document_type: str | None,
    cursor: str | None,
    limit: int,
) -> dict:
    if legal_entity_id:
        require_entity(session, principal.tenant_id, legal_entity_id)
    limit = page_limit(limit)
    stmt = select(SourceDocument).where(SourceDocument.tenant_id == principal.tenant_id)
    if legal_entity_id:
        stmt = stmt.where(SourceDocument.legal_entity_id == legal_entity_id)
    if document_type:
        stmt = stmt.where(SourceDocument.document_type == document_type)
    comparison = before_cursor(SourceDocument.received_at, SourceDocument.id, cursor)
    if comparison is not None:
        stmt = stmt.where(comparison)
    rows = session.scalars(stmt.order_by(SourceDocument.received_at.desc(), SourceDocument.id.desc()).limit(limit + 1)).all()
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        rows = rows[:limit]
        next_cursor = encode_cursor(last.received_at, last.id)
    return {"items": [document_dict(row) for row in rows], "next_cursor": next_cursor}


def get_document(session: Session, principal: Principal, document_id: str) -> SourceDocument:
    document = session.scalar(
        select(SourceDocument).where(SourceDocument.id == document_id, SourceDocument.tenant_id == principal.tenant_id)
    )
    if document is None:
        raise DomainError(404, "Não encontrado", "Documento não encontrado.")
    return document


def open_content(document: SourceDocument):
    key = document_key(document.tenant_id, document.sha256)
    return get_object_store().open(key)
