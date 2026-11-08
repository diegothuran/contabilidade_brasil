from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from contabil.audit.hash import content_hash
from contabil.audit.service import append_event
from contabil.documents.service import get_document, store_document
from contabil.imports.service import mark_operation_running, operation_dict
from contabil.ledger.service import trial_balance
from contabil.periods.service import require_period
from contabil.platform.auth import apply_tenant, format_utc
from contabil.platform.correlation import correlation_id
from contabil.platform.errors import DomainError
from contabil.platform.ids import new_id
from contabil.platform.outbox import enqueue
from contabil.platform.principal import Principal, ensure_role
from contabil.tables import (
    AccountingPeriod,
    AuditEvent,
    DocumentRequest,
    JournalEntry,
    LegalEntity,
    Operation,
    OperationalExport,
    SourceDocument,
)
from contabil.tenancy.service import require_entity

EXPORT_KIND = "operational_v1"
ECD_PREVIEW_KIND = "ecd_preview_v1"
EXPORT_KINDS = {
    EXPORT_KIND: {"operation": "operational_export", "event": "OperationalExportRequested", "requested": "operational_export_requested"},
    ECD_PREVIEW_KIND: {"operation": "ecd_preview", "event": "EcdPreviewRequested", "requested": "ecd_preview_requested"},
}
PACKAGE_LIMIT = 200
DISCLAIMER = (
    "Este pacote reúne lançamentos, documentos, pedidos, auditoria e o resumo do balancete da competência. "
    "Não é livro autenticado no SPED e não tem assinatura ICP-Brasil. "
    "Não inclui certificado, senha nem arquivo transmitido a órgão."
)


def assemble_operational_package(
    *,
    generated_at: str,
    tenant_id: str,
    legal_entity_id: str,
    name: str,
    cnpj: str,
    period_id: str,
    fiscal_year: int,
    month: int,
    journals: list[dict],
    documents: list[dict],
    document_requests: list[dict],
    audit_events: list[dict],
    currency: str,
    debit_total: str,
    credit_total: str,
) -> dict:
    body = {
        "schema_version": "1.0.0",
        "kind": EXPORT_KIND,
        "generated_at": generated_at,
        "tenant_id": tenant_id,
        "legal_entity": {"legal_entity_id": legal_entity_id, "name": name, "cnpj": cnpj},
        "period": {"period_id": period_id, "fiscal_year": fiscal_year, "month": month},
        "disclaimer": DISCLAIMER,
        "journals": journals,
        "documents": documents,
        "document_requests": document_requests,
        "audit_events": audit_events,
        "trial_balance": {"currency": currency, "debit_total": debit_total, "credit_total": credit_total},
    }
    body["sha256"] = content_hash({key: value for key, value in body.items() if key != "sha256"})
    return body


def _last_period_of_year(session: Session, tenant_id: str, legal_entity_id: str, fiscal_year: int) -> AccountingPeriod:
    period = session.scalar(
        select(AccountingPeriod)
        .where(
            AccountingPeriod.tenant_id == tenant_id,
            AccountingPeriod.legal_entity_id == legal_entity_id,
            AccountingPeriod.fiscal_year == fiscal_year,
        )
        .order_by(AccountingPeriod.month.desc())
        .limit(1)
    )
    if period is None:
        raise DomainError(409, "Ano sem competências", f"A empresa não tem competências em {fiscal_year}.")
    return period


def create_export(
    session: Session,
    principal: Principal,
    *,
    legal_entity_id: str,
    period_id: str | None,
    kind: str,
    fiscal_year: int | None = None,
) -> dict:
    ensure_role(principal, "preparer", "approver", "admin")
    if kind not in EXPORT_KINDS:
        raise DomainError(400, "Tipo inválido", "Use operational_v1 ou ecd_preview_v1.")
    entity = require_entity(session, principal.tenant_id, legal_entity_id)
    if kind == ECD_PREVIEW_KIND:
        if fiscal_year is None:
            raise DomainError(400, "Ano ausente", "A prévia da ECD pede o ano-calendário em fiscal_year.")
        # A exportação guarda a última competência do ano como referência; a prévia cobre o ano inteiro.
        period = _last_period_of_year(session, principal.tenant_id, entity.id, fiscal_year)
    else:
        if not period_id:
            raise DomainError(400, "Competência ausente", "A exportação operacional pede period_id.")
        period = require_period(session, principal.tenant_id, entity.id, period_id, for_posting=False)
    spec = EXPORT_KINDS[kind]
    export_id = new_id("exp")
    operation = Operation(
        id=new_id("op"),
        tenant_id=principal.tenant_id,
        kind=spec["operation"],
        status="accepted",
        correlation_id=correlation_id.get() or "",
        target_ref=export_id,
    )
    session.add(operation)
    session.flush()
    session.add(
        OperationalExport(
            id=export_id,
            tenant_id=principal.tenant_id,
            legal_entity_id=entity.id,
            period_id=period.id,
            operation_id=operation.id,
            kind=kind,
            sha256=None,
            payload=None,
            created_by=principal.user_id,
            created_at=datetime.now(timezone.utc),
        )
    )
    session.flush()
    event_payload = {"export_id": export_id, "operation_id": operation.id, "legal_entity_id": entity.id}
    if kind == ECD_PREVIEW_KIND:
        event_payload["fiscal_year"] = fiscal_year
    enqueue(session, tenant_id=principal.tenant_id, event_type=spec["event"], payload=event_payload)
    metadata = {"action": spec["requested"], "period_id": period.id}
    if kind == ECD_PREVIEW_KIND:
        metadata["fiscal_year"] = fiscal_year
    append_event(
        session,
        tenant_id=principal.tenant_id,
        event_type="document_exported",
        actor_ref=principal.user_id,
        target_type="operational_export",
        target_ref=export_id,
        metadata=metadata,
    )
    payload = operation_dict(operation)
    payload["export_id"] = export_id
    return payload


def _ready_export(session: Session, principal: Principal, export_id: str) -> OperationalExport:
    export = session.scalar(
        select(OperationalExport).where(OperationalExport.id == export_id, OperationalExport.tenant_id == principal.tenant_id)
    )
    if export is None:
        raise DomainError(404, "Não encontrado", "Exportação não encontrada.")
    operation = session.scalar(
        select(Operation).where(Operation.id == export.operation_id, Operation.tenant_id == principal.tenant_id)
    )
    if operation is None or operation.status == "failed":
        raise DomainError(409, "Exportação falhou", "Não foi possível montar o pacote desta competência.")
    if operation.status != "completed" or export.payload is None:
        raise DomainError(409, "Exportação em andamento", "O pacote ainda está em fila ou sendo gerado.")
    return export


def get_export(session: Session, principal: Principal, export_id: str) -> dict:
    return _ready_export(session, principal, export_id).payload


def export_file(session: Session, principal: Principal, export_id: str) -> tuple[SourceDocument, str]:
    """Arquivo guardado de uma exportação que gera arquivo (hoje, só a prévia da ECD)."""
    export = _ready_export(session, principal, export_id)
    document_id = (export.payload or {}).get("document_id")
    if export.kind != ECD_PREVIEW_KIND or not document_id:
        raise DomainError(404, "Não encontrado", "Esta exportação não tem arquivo para baixar.")
    document = get_document(session, principal, document_id)
    return document, export.payload.get("file_name") or document.file_name


def run_ecd_preview(session: Session, tenant_id: str, payload: dict) -> None:
    """Handler do worker: monta a prévia, guarda o .txt no storage e o resumo na exportação."""
    from contabil.regulatory.ecd_preview import build_ecd_preview

    mark_operation_running(session, tenant_id, payload.get("operation_id"))
    export = session.scalar(
        select(OperationalExport)
        .where(OperationalExport.id == payload["export_id"], OperationalExport.tenant_id == tenant_id)
        .with_for_update()
    )
    if export is None or export.payload is not None:
        return
    fiscal_year = int(payload["fiscal_year"])
    preview = build_ecd_preview(session, tenant_id, export.legal_entity_id, fiscal_year, actor=export.created_by)
    writer = Principal(export.created_by, tenant_id, frozenset({"preparer"}), export.created_by, "")
    content = preview.encoded()
    document, _status = store_document(
        session,
        writer,
        file_name=preview.file_name,
        media_type=f"text/plain; charset={preview.encoding.lower()}",
        content=content,
        document_type="other",
        legal_entity_id=export.legal_entity_id,
        competence=None,
        source_ref=f"ecd-preview:{export.id}",
        source_type="generated",
    )
    apply_tenant(session, tenant_id)
    body = {
        "schema_version": "1.0.0",
        "kind": ECD_PREVIEW_KIND,
        "generated_at": format_utc(datetime.now(timezone.utc)),
        "legal_entity_id": export.legal_entity_id,
        "fiscal_year": fiscal_year,
        "layout": {"obligation": "ECD", "version": preview.layout_version, "encoding": preview.encoding},
        "notice": preview.notice,
        "transmittable": False,
        "file_name": preview.file_name,
        "document_id": document["document_id"],
        "sha256": document["original"]["sha256"],
        "size_bytes": len(content),
        "result": preview.result,
        "counts": preview.counts,
        "checks": preview.checks,
        "issues": [issue.as_dict() for issue in preview.issues],
    }
    export.payload = body
    export.sha256 = document["original"]["sha256"]
    session.flush()
    append_event(
        session,
        tenant_id=tenant_id,
        event_type="document_exported",
        actor_ref=export.created_by,
        target_type="operational_export",
        target_ref=export.id,
        metadata={"action": "ecd_preview_completed", "sha256": document["original"]["sha256"], "fiscal_year": fiscal_year},
    )


def run_operational_export(session: Session, tenant_id: str, payload: dict) -> None:
    mark_operation_running(session, tenant_id, payload.get("operation_id"))
    export = session.scalar(
        select(OperationalExport)
        .where(OperationalExport.id == payload["export_id"], OperationalExport.tenant_id == tenant_id)
        .with_for_update()
    )
    if export is None or export.payload is not None:
        return
    entity = session.scalar(select(LegalEntity).where(LegalEntity.id == export.legal_entity_id, LegalEntity.tenant_id == tenant_id))
    period = session.scalar(
        select(AccountingPeriod).where(AccountingPeriod.id == export.period_id, AccountingPeriod.tenant_id == tenant_id)
    )
    if entity is None or period is None:
        raise DomainError(404, "Não encontrado", "Empresa ou competência da exportação não existe.")
    competence = f"{period.fiscal_year:04d}-{period.month:02d}"
    journals = session.scalars(
        select(JournalEntry)
        .where(
            JournalEntry.tenant_id == tenant_id,
            JournalEntry.legal_entity_id == entity.id,
            JournalEntry.period_id == period.id,
            JournalEntry.status.in_(("published", "reversed")),
        )
        .order_by(JournalEntry.entry_date, JournalEntry.id)
        .limit(PACKAGE_LIMIT)
    ).all()
    documents = session.scalars(
        select(SourceDocument)
        .where(
            SourceDocument.tenant_id == tenant_id,
            SourceDocument.legal_entity_id == entity.id,
            SourceDocument.competence == competence,
        )
        .order_by(SourceDocument.received_at, SourceDocument.id)
        .limit(PACKAGE_LIMIT)
    ).all()
    requests = session.scalars(
        select(DocumentRequest)
        .where(
            DocumentRequest.tenant_id == tenant_id,
            DocumentRequest.legal_entity_id == entity.id,
            DocumentRequest.period_id == period.id,
        )
        .order_by(DocumentRequest.due_on, DocumentRequest.id)
        .limit(PACKAGE_LIMIT)
    ).all()
    refs = {item.id for item in journals} | {item.id for item in documents} | {item.id for item in requests}
    recent = session.scalars(
        select(AuditEvent).where(AuditEvent.tenant_id == tenant_id).order_by(AuditEvent.occurred_at.desc()).limit(500)
    ).all()
    events = [
        event
        for event in recent
        if event.target_ref in refs or (event.details or {}).get("period_id") == period.id
    ][:PACKAGE_LIMIT]
    balance = trial_balance(
        session,
        Principal(export.created_by, tenant_id, frozenset({"viewer"}), export.created_by, entity.name),
        entity.id,
        period.id,
    )
    package = assemble_operational_package(
        generated_at=format_utc(datetime.now(timezone.utc)),
        tenant_id=tenant_id,
        legal_entity_id=entity.id,
        name=entity.name,
        cnpj=entity.cnpj,
        period_id=period.id,
        fiscal_year=period.fiscal_year,
        month=period.month,
        journals=[
            {
                "journal_id": item.id,
                "entry_date": item.entry_date.isoformat(),
                "description": item.description,
                "status": item.status,
            }
            for item in journals
        ],
        documents=[
            {
                "document_id": item.id,
                "document_type": item.document_type,
                "file_name": item.file_name,
                "sha256": item.sha256,
                "competence": item.competence,
            }
            for item in documents
        ],
        document_requests=[
            {
                "document_request_id": item.id,
                "title": item.title,
                "status": item.status,
                "due_on": item.due_on.isoformat(),
                "blocks_close": item.status in {"open", "received"},
            }
            for item in requests
        ],
        audit_events=[
            {
                "event_id": item.id,
                "event_type": item.event_type,
                "occurred_at": format_utc(item.occurred_at),
                "target_type": item.target_type,
                "target_ref": item.target_ref,
            }
            for item in events
        ],
        currency=balance["currency"],
        debit_total=balance["debit_total"],
        credit_total=balance["credit_total"],
    )
    export.payload = package
    export.sha256 = package["sha256"]
    session.flush()
    append_event(
        session,
        tenant_id=tenant_id,
        event_type="document_exported",
        actor_ref=export.created_by,
        target_type="operational_export",
        target_ref=export.id,
        metadata={"action": "operational_export_completed", "sha256": package["sha256"], "period_id": period.id},
    )
