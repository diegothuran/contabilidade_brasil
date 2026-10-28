from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from contabil.documents.service import open_content
from contabil.imports.csv_layout import TEMPLATES, CsvParseError, CsvRow, parse_csv
from contabil.ledger.service import post_imported_journal
from contabil.master_data.service import create_account
from contabil.platform.constants import EFFECTIVE_JOURNAL_STATUSES, SCHEMA_VERSION
from contabil.platform.correlation import correlation_id
from contabil.platform.errors import DomainError
from contabil.platform.ids import new_id
from contabil.platform.money import format_amount
from contabil.platform.outbox import enqueue
from contabil.platform.principal import Principal, ensure_role
from contabil.platform.settings import get_settings
from contabil.tenancy.service import before_cursor, encode_cursor, page_limit
from contabil.tables import (
    Account,
    CostCenter,
    ExternalRef,
    ImportBatch,
    ImportBatchFile,
    ImportBatchJournal,
    ImportReport,
    ImportRow,
    JournalEntry,
    JournalLine,
    Operation,
    SourceDocument,
)
from contabil.tenancy.service import page_limit, require_entity

ACCEPTED_KINDS = frozenset({"chart_of_accounts", "opening_balance", "journal"})
ACCOUNT_TYPES = frozenset({"asset", "liability", "equity", "revenue", "expense"})
_AMOUNT = re.compile(r"^[0-9]+(\.[0-9]{1,6})?$")


@dataclass
class Classified:
    file_id: str
    kind: str
    row_no: int
    external_id: str | None
    raw: dict
    status: str = "valid"
    error_code: str | None = None
    error_message: str | None = None
    debit: Decimal = field(default_factory=lambda: Decimal("0"))
    credit: Decimal = field(default_factory=lambda: Decimal("0"))


def _money(value: str) -> Decimal | None:
    text = value.strip()
    if text in {"", "0", "0.0", "0.00"}:
        return Decimal("0")
    if _AMOUNT.fullmatch(text) is None:
        return None
    return Decimal(text)


def _fail(row: Classified, code: str, message: str) -> None:
    if row.status == "valid":
        row.status = "invalid"
        row.error_code = code
        row.error_message = message


def _account(session: Session, tenant_id: str, legal_entity_id: str, code: str) -> Account | None:
    return session.scalar(
        select(Account).where(Account.tenant_id == tenant_id, Account.legal_entity_id == legal_entity_id, Account.code == code)
    )


def _cost_center(session: Session, tenant_id: str, legal_entity_id: str, code: str) -> CostCenter | None:
    return session.scalar(
        select(CostCenter).where(
            CostCenter.tenant_id == tenant_id,
            CostCenter.legal_entity_id == legal_entity_id,
            CostCenter.code == code,
            CostCenter.active.is_(True),
        )
    )


def _external(session: Session, tenant_id: str, source_system: str, entity_type: str, external_id: str) -> ExternalRef | None:
    return session.scalar(
        select(ExternalRef).where(
            ExternalRef.tenant_id == tenant_id,
            ExternalRef.source_system == source_system,
            ExternalRef.entity_type == entity_type,
            ExternalRef.external_id == external_id,
        )
    )


def operation_dict(operation: Operation) -> dict:
    return {
        "operation_id": operation.id,
        "status": operation.status,
        "correlation_id": operation.correlation_id,
        "error_code": operation.error_code,
        "kind": operation.kind,
        "target_ref": operation.target_ref,
    }


def _batch_or_404(session: Session, tenant_id: str, batch_id: str) -> ImportBatch:
    batch = session.scalar(select(ImportBatch).where(ImportBatch.id == batch_id, ImportBatch.tenant_id == tenant_id))
    if batch is None:
        raise DomainError(404, "Não encontrado", "Lote não encontrado.")
    return batch


def batch_dict(session: Session, batch: ImportBatch) -> dict:
    files = session.scalars(select(ImportBatchFile).where(ImportBatchFile.batch_id == batch.id).order_by(ImportBatchFile.id)).all()
    documents = {
        document.id: document
        for document in session.scalars(
            select(SourceDocument).where(SourceDocument.id.in_([item.document_id for item in files] or [""]))
        ).all()
    }
    errors = session.scalars(
        select(ImportRow)
        .where(ImportRow.batch_id == batch.id, ImportRow.status == "invalid")
        .order_by(ImportRow.row_no)
        .limit(10000)
    ).all()
    return {
        "schema_version": batch.schema_version,
        "batch_id": batch.id,
        "tenant_id": batch.tenant_id,
        "legal_entity_id": batch.legal_entity_id,
        "period_id": batch.period_id,
        "source_system": batch.source_system,
        "mode": batch.mode,
        "status": batch.status,
        "idempotency_key": batch.idempotency_key,
        "created_by": batch.created_by,
        "published_by": batch.published_by,
        "files": [
            {
                "file_id": item.id,
                "file_name": documents[item.document_id].file_name if item.document_id in documents else item.id,
                "sha256": item.sha256,
                "kind": item.kind,
                "object_uri": documents[item.document_id].object_ref if item.document_id in documents else None,
            }
            for item in files
        ],
        "summary": {
            "rows_received": batch.rows_received,
            "rows_valid": batch.rows_valid,
            "rows_invalid": batch.rows_invalid,
            "debit_total": format_amount(batch.debit_total),
            "credit_total": format_amount(batch.credit_total),
            "difference": format_amount(batch.difference),
        },
        "errors": [
            {"row": item.row_no, "code": item.error_code or "INVALID", "message": item.error_message or "Linha inválida."}
            for item in errors
        ],
        "reconciliation_report_id": batch.reconciliation_report_id,
    }


def list_batches(session: Session, principal: Principal, *, legal_entity_id: str, cursor: str | None, limit: int) -> dict:
    del cursor
    require_entity(session, principal.tenant_id, legal_entity_id)
    limit = page_limit(limit)
    rows = session.scalars(
        select(ImportBatch)
        .where(ImportBatch.tenant_id == principal.tenant_id, ImportBatch.legal_entity_id == legal_entity_id)
        .order_by(ImportBatch.created_at.desc())
        .limit(limit)
    ).all()
    return {"items": [batch_dict(session, row) for row in rows], "next_cursor": None}


def create_batch(session: Session, principal: Principal, body, idempotency_key: str) -> dict:
    ensure_role(principal, "preparer", "approver", "admin")
    if body.mode == "rollback":
        raise DomainError(409, "Não suportado", "Rollback de lote não é suportado nesta fase.")
    if body.mode != "dry_run":
        raise DomainError(409, "Dry-run obrigatório", "O lote precisa nascer como dry-run. A publicação é uma aprovação separada.")
    entity = require_entity(session, principal.tenant_id, body.legal_entity_id)
    kinds = {item.kind for item in body.files}
    if not kinds <= ACCEPTED_KINDS:
        raise DomainError(400, "Tipo de arquivo inválido", "Nesta fase o lote aceita plano de contas, saldo de abertura ou lançamentos.")
    if kinds & {"opening_balance", "journal"}:
        if not body.period_id:
            raise DomainError(400, "Período obrigatório", "Saldo de abertura e lançamentos exigem um período.")
        from contabil.periods.service import require_period

        require_period(session, principal.tenant_id, entity.id, body.period_id, for_posting=False)
    batch_id = new_id("batch")
    batch = ImportBatch(
        id=batch_id,
        schema_version=SCHEMA_VERSION,
        tenant_id=principal.tenant_id,
        legal_entity_id=entity.id,
        source_system=body.source_system,
        mode="dry_run",
        status="received",
        idempotency_key=idempotency_key,
        period_id=body.period_id,
        created_by=principal.user_id,
        rows_received=0,
        rows_valid=0,
        rows_invalid=0,
        debit_total=Decimal("0"),
        credit_total=Decimal("0"),
        difference=Decimal("0"),
    )
    session.add(batch)
    session.flush()
    for item in body.files:
        document = session.scalar(
            select(SourceDocument).where(SourceDocument.id == item.document_id, SourceDocument.tenant_id == principal.tenant_id)
        )
        if document is None:
            raise DomainError(400, "Documento inválido", "O arquivo não pertence a este escritório.")
        session.add(
            ImportBatchFile(
                id=new_id("file"),
                tenant_id=principal.tenant_id,
                batch_id=batch.id,
                document_id=document.id,
                kind=item.kind,
                sha256=document.sha256,
            )
        )
    operation = Operation(
        id=new_id("op"),
        tenant_id=principal.tenant_id,
        kind="import_batch_validate",
        status="accepted",
        correlation_id=correlation_id.get() or "",
        target_ref=batch.id,
    )
    session.add(operation)
    session.flush()
    enqueue(
        session,
        tenant_id=principal.tenant_id,
        event_type="ImportBatchReceived",
        payload={"batch_id": batch.id, "operation_id": operation.id, "legal_entity_id": entity.id},
    )
    return operation_dict(operation)


def request_publish(session: Session, principal: Principal, batch_id: str) -> dict:
    ensure_role(principal, "approver", "admin")
    batch = session.scalar(
        select(ImportBatch).where(ImportBatch.id == batch_id, ImportBatch.tenant_id == principal.tenant_id).with_for_update()
    )
    if batch is None:
        raise DomainError(404, "Não encontrado", "Lote não encontrado.")
    if batch.status != "ready":
        raise DomainError(409, "Estado inválido", "Só um lote pronto pode ser publicado.")
    if batch.created_by == principal.user_id:
        raise DomainError(403, "Segregação de funções", "Quem cria o lote não pode publicá-lo.")
    operation = Operation(
        id=new_id("op"),
        tenant_id=principal.tenant_id,
        kind="import_batch_publish",
        status="accepted",
        correlation_id=correlation_id.get() or "",
        target_ref=batch.id,
    )
    session.add(operation)
    session.flush()
    enqueue(
        session,
        tenant_id=principal.tenant_id,
        event_type="ImportBatchPublishRequested",
        payload={
            "batch_id": batch.id,
            "operation_id": operation.id,
            "legal_entity_id": batch.legal_entity_id,
            "published_by": principal.user_id,
        },
    )
    return operation_dict(operation)


def get_operation(session: Session, principal: Principal, operation_id: str) -> dict:
    operation = session.scalar(select(Operation).where(Operation.id == operation_id, Operation.tenant_id == principal.tenant_id))
    if operation is None:
        raise DomainError(404, "Não encontrado", "Operação não encontrada.")
    return operation_dict(operation)


_OPERATION_STATUSES = frozenset({"accepted", "running", "completed", "failed"})


def list_operations(
    session: Session,
    principal: Principal,
    *,
    kind: str | None,
    status: str | None,
    correlation: str | None,
    cursor: str | None,
    limit: int,
) -> dict:
    if status is not None and status not in _OPERATION_STATUSES:
        raise DomainError(400, "Estado inválido", "Filtre por accepted, running, completed ou failed.")
    limit = page_limit(limit)
    stmt = select(Operation).where(Operation.tenant_id == principal.tenant_id)
    if kind:
        stmt = stmt.where(Operation.kind == kind)
    if status:
        stmt = stmt.where(Operation.status == status)
    if correlation:
        stmt = stmt.where(Operation.correlation_id == correlation)
    comparison = before_cursor(Operation.created_at, Operation.id, cursor)
    if comparison is not None:
        stmt = stmt.where(comparison)
    rows = session.scalars(stmt.order_by(Operation.created_at.desc(), Operation.id.desc()).limit(limit + 1)).all()
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        rows = rows[:limit]
        next_cursor = encode_cursor(last.created_at, last.id)
    return {"items": [operation_dict(row) for row in rows], "next_cursor": next_cursor}


def list_rows(session: Session, principal: Principal, batch_id: str, status: str | None) -> dict:
    batch = _batch_or_404(session, principal.tenant_id, batch_id)
    stmt = select(ImportRow).where(ImportRow.batch_id == batch.id, ImportRow.tenant_id == principal.tenant_id)
    if status:
        stmt = stmt.where(ImportRow.status == status)
    rows = session.scalars(stmt.order_by(ImportRow.row_no).limit(500)).all()
    return {
        "items": [
            {
                "row": item.row_no,
                "external_id": item.external_id,
                "status": item.status,
                "error_code": item.error_code,
                "error_message": item.error_message,
                "raw": item.raw,
            }
            for item in rows
        ]
    }


def get_report(session: Session, principal: Principal, batch_id: str) -> dict:
    batch = _batch_or_404(session, principal.tenant_id, batch_id)
    report = session.scalar(select(ImportReport).where(ImportReport.batch_id == batch.id, ImportReport.tenant_id == principal.tenant_id))
    if report is None:
        raise DomainError(404, "Não encontrado", "O relatório ainda não foi gerado.")
    journals = session.scalars(
        select(ImportBatchJournal).where(ImportBatchJournal.batch_id == batch.id).order_by(ImportBatchJournal.external_id)
    ).all()
    return {
        "report_id": report.id,
        "batch_id": batch.id,
        "rows": report.rows,
        "debit_total": format_amount(report.debit_total),
        "credit_total": format_amount(report.credit_total),
        "difference": format_amount(report.difference),
        "journals": [{"journal_id": item.journal_id, "external_id": item.external_id} for item in journals],
    }


def template_csv(kind: str) -> str:
    header = TEMPLATES.get(kind)
    if header is None:
        raise DomainError(404, "Não encontrado", "Não há modelo para este tipo de arquivo.")
    return header + "\n"


def mark_operation_running(session: Session, tenant_id: str, operation_id: str | None) -> None:
    if not operation_id:
        return
    operation = session.scalar(select(Operation).where(Operation.id == operation_id, Operation.tenant_id == tenant_id))
    if operation is not None and operation.status == "accepted":
        operation.status = "running"
        operation.updated_at = datetime.now(timezone.utc)


def validate_batch(session: Session, tenant_id: str, payload: dict) -> None:
    mark_operation_running(session, tenant_id, payload.get("operation_id"))
    batch = session.scalar(
        select(ImportBatch).where(ImportBatch.id == payload["batch_id"], ImportBatch.tenant_id == tenant_id).with_for_update()
    )
    if batch is None or batch.status not in {"received", "validating"}:
        return
    batch.status = "validating"
    session.flush()
    session.execute(delete(ImportRow).where(ImportRow.batch_id == batch.id))
    files = list(session.scalars(select(ImportBatchFile).where(ImportBatchFile.batch_id == batch.id)).all())
    files.sort(key=lambda item: {"chart_of_accounts": 0, "opening_balance": 1, "journal": 2}.get(item.kind, 9))
    classified: list[Classified] = []
    batch_error: CsvParseError | None = None
    extra_codes: set[str] = set()
    for batch_file in files:
        document = session.scalar(select(SourceDocument).where(SourceDocument.id == batch_file.document_id))
        if document is None:
            batch_error = CsvParseError("MISSING_COLUMN", "Documento do lote não encontrado.")
            break
        try:
            content = b"".join(open_content(document))
            parsed = parse_csv(content, batch_file.kind)
        except CsvParseError as exc:
            batch_error = exc
            break
        if len(parsed) > get_settings().max_import_rows:
            batch_error = CsvParseError("TOO_MANY_ROWS", "O arquivo excede o limite de linhas do lote.")
            break
        part = _classify_file(session, batch, batch_file, parsed, extra_codes)
        classified.extend(part)
        extra_codes.update(row.raw.get("code", "") for row in part if row.status == "valid" and row.raw.get("code"))
    if batch_error is None:
        batch_error = _apply_group_rules(session, batch, classified)
    if batch_error is not None:
        classified.append(
            Classified(
                file_id=files[0].id if files else batch.id,
                kind="other",
                row_no=1,
                external_id=None,
                raw={"kind": "batch"},
                status="invalid",
                error_code=batch_error.code,
                error_message=batch_error.message,
            )
        )
        for item in classified:
            if item.status == "valid":
                _fail(item, batch_error.code, batch_error.message)
    _persist_rows(session, batch, classified)


def publish_batch(session: Session, tenant_id: str, payload: dict) -> None:
    mark_operation_running(session, tenant_id, payload.get("operation_id"))
    batch = session.scalar(
        select(ImportBatch).where(ImportBatch.id == payload["batch_id"], ImportBatch.tenant_id == tenant_id).with_for_update()
    )
    if batch is None or batch.status in {"published", "partially_published"}:
        return
    if batch.status != "ready":
        raise DomainError(409, "Estado inválido", "O lote não está pronto para publicação.")
    published_by = payload["published_by"]
    if published_by == batch.created_by:
        raise DomainError(403, "Segregação de funções", "Quem cria o lote não pode publicá-lo.")
    files = {
        item.id: item
        for item in session.scalars(select(ImportBatchFile).where(ImportBatchFile.batch_id == batch.id)).all()
    }
    rows = list(session.scalars(select(ImportRow).where(ImportRow.batch_id == batch.id).order_by(ImportRow.row_no)).all())
    _publish_chart(session, batch, [row for row in rows if row.status == "valid" and row.raw.get("kind") == "chart_of_accounts"])
    _publish_opening(session, batch, files, [row for row in rows if row.status == "valid" and row.raw.get("kind") == "opening_balance"], published_by)
    _publish_journals(session, batch, files, [row for row in rows if row.status == "valid" and row.raw.get("kind") == "journal"], published_by)
    invalid = any(row.status == "invalid" for row in rows)
    batch.published_by = published_by
    batch.published_at = datetime.now(timezone.utc).replace(microsecond=0)
    batch.status = "partially_published" if invalid else "published"
    report = _write_report(session, batch, rows)
    batch.reconciliation_report_id = report.id
    enqueue(
        session,
        tenant_id=batch.tenant_id,
        event_type="ImportBatchPublished",
        payload={"batch_id": batch.id, "legal_entity_id": batch.legal_entity_id},
    )
    session.flush()


def _classify_file(
    session: Session,
    batch: ImportBatch,
    batch_file: ImportBatchFile,
    parsed: list[CsvRow],
    extra_codes: set[str],
) -> list[Classified]:
    rows: list[Classified] = []
    seen: set[str] = set()
    chart_codes = {
        account.code
        for account in session.scalars(
            select(Account).where(Account.tenant_id == batch.tenant_id, Account.legal_entity_id == batch.legal_entity_id)
        ).all()
    } | extra_codes
    incoming_codes = {row.values.get("code", "") for row in parsed} if batch_file.kind == "chart_of_accounts" else set()
    known_codes = chart_codes | incoming_codes
    for parsed_row in parsed:
        values = parsed_row.values
        item = Classified(file_id=batch_file.id, kind=batch_file.kind, row_no=parsed_row.row_no, external_id=None, raw={"kind": batch_file.kind})
        if batch_file.kind == "chart_of_accounts":
            _classify_account(session, batch, item, values, seen)
        elif batch_file.kind == "opening_balance":
            _classify_opening(session, batch, item, values, seen, known_codes)
        else:
            _classify_journal_line(session, batch, item, values, known_codes)
        item.raw["debit"] = format_amount(item.debit)
        item.raw["credit"] = format_amount(item.credit)
        rows.append(item)
    if batch_file.kind == "chart_of_accounts":
        _check_parents(rows, chart_codes)
    if batch_file.kind == "journal":
        _check_journal_groups(rows)
    if batch_file.kind == "opening_balance":
        _check_opening_balance(rows)
    return rows


def _classify_account(session, batch, item: Classified, values: dict, seen: set[str]) -> None:
    external_id = values.get("external_id", "")
    item.external_id = external_id or None
    item.raw.update(
        {
            "external_id": external_id,
            "code": values.get("code", ""),
            "name": values.get("name", ""),
            "account_type": values.get("account_type", ""),
            "parent_code": values.get("parent_code", ""),
        }
    )
    if not external_id or not values.get("code") or not values.get("name"):
        _fail(item, "MISSING_COLUMN", "Identificador, código e nome são obrigatórios.")
        return
    if external_id in seen:
        _fail(item, "DUPLICATE_EXTERNAL_ID_IN_FILE", "O identificador externo está repetido no arquivo.")
        return
    seen.add(external_id)
    if _external(session, batch.tenant_id, batch.source_system, "account", external_id):
        item.status = "already_imported"
        return
    if values.get("account_type") not in ACCOUNT_TYPES:
        _fail(item, "INVALID_ACCOUNT_TYPE", "Tipo de conta inválido.")
        return
    postable = {"true": True, "1": True, "sim": True, "yes": True, "false": False, "0": False, "nao": False, "não": False, "no": False}.get(
        values.get("postable", "").lower()
    )
    if postable is None:
        _fail(item, "MISSING_COLUMN", "Informe se a conta é postável com true ou false.")
        return
    item.raw["postable"] = postable
    if _account(session, batch.tenant_id, batch.legal_entity_id, values["code"]) is not None:
        _fail(item, "ACCOUNT_CODE_EXISTS", "Já existe uma conta com este código na empresa.")
    if values.get("parent_code"):
        item.raw["parent_unresolved"] = True


def _check_parents(rows: list[Classified], existing_codes: set[str]) -> None:
    resolvable = set(existing_codes)
    for row in rows:
        if row.status == "valid" and not row.raw.get("parent_code"):
            resolvable.add(row.raw.get("code") or "")
    changed = True
    while changed:
        changed = False
        for row in rows:
            code = row.raw.get("code") or ""
            parent = row.raw.get("parent_code") or ""
            if row.status == "valid" and parent and parent in resolvable and code not in resolvable:
                resolvable.add(code)
                changed = True
    for row in rows:
        if row.status == "valid" and row.raw.get("parent_unresolved") and (row.raw.get("code") or "") not in resolvable:
            _fail(row, "PARENT_NOT_FOUND", "A conta pai não existe no arquivo nem na empresa.")


def _classify_opening(session, batch, item: Classified, values: dict, seen: set[str], known_codes: set[str]) -> None:
    external_id = values.get("external_account_id", "")
    code = values.get("account_code", "")
    item.external_id = external_id or None
    item.raw.update({"external_id": external_id, "account_code": code, "code": code})
    if not external_id or not code:
        _fail(item, "MISSING_COLUMN", "Conta e identificador externo são obrigatórios.")
        return
    if external_id in seen:
        _fail(item, "DUPLICATE_EXTERNAL_ID_IN_FILE", "A conta de abertura está repetida no arquivo.")
        return
    seen.add(external_id)
    if _external(session, batch.tenant_id, batch.source_system, "opening", external_id):
        item.status = "already_imported"
        return
    debit = _money(values.get("debit", ""))
    credit = _money(values.get("credit", ""))
    if debit is None or credit is None or (debit > 0 and credit > 0) or (debit == 0 and credit == 0):
        _fail(item, "INVALID_AMOUNT", "Informe débito ou crédito, com decimal e ponto.")
        return
    item.debit = debit
    item.credit = credit
    account = _account(session, batch.tenant_id, batch.legal_entity_id, code)
    if account is None and code not in known_codes:
        _fail(item, "ACCOUNT_NOT_FOUND", "Conta não mapeada.")
        return
    if account is not None and (not account.postable or not account.active):
        _fail(item, "ACCOUNT_NOT_POSTABLE", "A conta de abertura precisa ser postável e estar ativa.")


def _check_opening_balance(rows: list[Classified]) -> None:
    valid = [row for row in rows if row.status == "valid"]
    if not valid:
        return
    debit = sum((row.debit for row in valid), Decimal("0"))
    credit = sum((row.credit for row in valid), Decimal("0"))
    if debit != credit:
        for row in valid:
            _fail(row, "BATCH_UNBALANCED", "O arquivo de saldo de abertura não fecha débito e crédito.")


def _classify_journal_line(session, batch, item: Classified, values: dict, known_codes: set[str]) -> None:
    external_id = values.get("external_journal_id", "")
    code = values.get("account_code", "")
    item.external_id = external_id or None
    item.raw.update(
        {
            "external_id": external_id,
            "account_code": code,
            "code": code,
            "entry_date": values.get("entry_date", ""),
            "description": values.get("description", ""),
            "line_description": values.get("line_description", ""),
            "side": values.get("side", ""),
            "cost_center_code": values.get("cost_center_code", ""),
        }
    )
    if not external_id or not code or not values.get("description") or not values.get("line_description"):
        _fail(item, "MISSING_COLUMN", "Lançamento, conta, descrição e histórico são obrigatórios.")
        return
    if _external(session, batch.tenant_id, batch.source_system, "journal", external_id):
        item.status = "already_imported"
        return
    amount = _money(values.get("amount", ""))
    if amount is None or amount <= 0 or values.get("side") not in {"debit", "credit"}:
        _fail(item, "INVALID_AMOUNT", "Informe lado debit ou credit e um valor positivo.")
        return
    item.raw["amount"] = format_amount(amount)
    if values["side"] == "debit":
        item.debit = amount
    else:
        item.credit = amount
    parsed_date = _parse_date(values.get("entry_date", ""))
    if parsed_date is None:
        _fail(item, "PERIOD_MISMATCH", "A data do lançamento é inválida.")
        return
    if batch.period_id:
        from contabil.periods.service import require_period

        period = require_period(session, batch.tenant_id, batch.legal_entity_id, batch.period_id, for_posting=False)
        if not period.start_date <= parsed_date <= period.end_date:
            _fail(item, "PERIOD_MISMATCH", "A data do lançamento está fora do período.")
            return
    account = _account(session, batch.tenant_id, batch.legal_entity_id, code)
    if account is None and code not in known_codes:
        _fail(item, "ACCOUNT_NOT_FOUND", "Conta não mapeada.")
        return
    if account is not None and (not account.postable or not account.active):
        _fail(item, "ACCOUNT_NOT_POSTABLE", "A conta precisa ser postável e estar ativa.")
        return
    center_code = values.get("cost_center_code", "")
    if center_code:
        center = _cost_center(session, batch.tenant_id, batch.legal_entity_id, center_code)
        if center is None:
            _fail(item, "COST_CENTER_NOT_FOUND", "Centro de custo não encontrado.")
            return
        item.raw["cost_center_id"] = center.id


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _check_journal_groups(rows: list[Classified]) -> None:
    groups: dict[str, list[Classified]] = {}
    for row in rows:
        if row.external_id:
            groups.setdefault(row.external_id, []).append(row)
    for group in groups.values():
        valid = [row for row in group if row.status == "valid"]
        if not valid:
            continue
        debit = sum((row.debit for row in valid), Decimal("0"))
        credit = sum((row.credit for row in valid), Decimal("0"))
        dates = {row.raw.get("entry_date") for row in valid}
        if len(valid) < 2 or debit != credit or len(dates) != 1:
            for row in valid:
                _fail(row, "JOURNAL_UNBALANCED", "O lançamento precisa ter ao menos duas linhas e fechar débito e crédito.")


def _apply_group_rules(session: Session, batch: ImportBatch, rows: list[Classified]) -> CsvParseError | None:
    del session, batch
    return None


def summarize(rows: list[Classified]) -> tuple[int, int, int, int, Decimal, Decimal]:
    received = len(rows)
    valid = sum(1 for item in rows if item.status == "valid")
    invalid = sum(1 for item in rows if item.status == "invalid")
    already = sum(1 for item in rows if item.status == "already_imported")
    debit = sum((item.debit for item in rows if item.status == "valid"), Decimal("0"))
    credit = sum((item.credit for item in rows if item.status == "valid"), Decimal("0"))
    return received, valid, invalid, already, debit, credit


def _persist_rows(session: Session, batch: ImportBatch, rows: list[Classified]) -> None:
    for item in rows:
        session.add(
            ImportRow(
                id=new_id("row"),
                tenant_id=batch.tenant_id,
                batch_id=batch.id,
                file_id=item.file_id,
                row_no=item.row_no,
                external_id=item.external_id,
                raw=item.raw,
                status=item.status,
                error_code=item.error_code,
                error_message=item.error_message,
            )
        )
    received, valid, invalid, already, debit, credit = summarize(rows)
    batch.rows_received = received
    batch.rows_valid = valid
    batch.rows_invalid = invalid
    batch.debit_total = debit
    batch.credit_total = credit
    batch.difference = abs(debit - credit)
    batch.status = "ready" if valid or already else "failed"
    if invalid and not valid and not already:
        batch.status = "failed"
    session.flush()


def _publish_chart(session: Session, batch: ImportBatch, rows: list[ImportRow]) -> None:
    pending = list(rows)
    guard = 0
    while pending and guard < len(rows) + 1:
        guard += 1
        blocked: list[ImportRow] = []
        progressed = False
        for row in pending:
            parent_code = row.raw.get("parent_code") or ""
            parent_id = None
            if parent_code:
                parent = _account(session, batch.tenant_id, batch.legal_entity_id, parent_code)
                if parent is None:
                    blocked.append(row)
                    continue
                parent_id = parent.id
            account = create_account(
                session,
                tenant_id=batch.tenant_id,
                legal_entity_id=batch.legal_entity_id,
                code=row.raw["code"],
                name=row.raw["name"],
                account_type=row.raw["account_type"],
                postable=bool(row.raw.get("postable")),
                parent_id=parent_id,
            )
            _remember(session, batch, "account", row.external_id or row.raw["code"], account.id)
            progressed = True
        if not progressed:
            raise DomainError(409, "Conta pai inválida", "Não foi possível criar a hierarquia do plano importado.")
        pending = blocked


def _publish_opening(session, batch: ImportBatch, files: dict, rows: list[ImportRow], published_by: str) -> None:
    if not rows or not batch.period_id:
        return
    lines = []
    for row in rows:
        account = _account(session, batch.tenant_id, batch.legal_entity_id, row.raw["account_code"])
        if account is None:
            raise DomainError(409, "Conta inválida", "A conta de abertura não existe no momento da publicação.")
        side = "debit" if Decimal(row.raw.get("debit") or "0") > 0 else "credit"
        amount = Decimal(row.raw["debit"] if side == "debit" else row.raw["credit"])
        lines.append(
            {
                "account_id": account.id,
                "side": side,
                "amount": amount,
                "description": "Saldo de abertura",
                "cost_center_id": None,
            }
        )
    file_id = rows[0].file_id
    source_hash = files[file_id].sha256 if file_id in files else None
    journal_id = post_imported_journal(
        session,
        tenant_id=batch.tenant_id,
        legal_entity_id=batch.legal_entity_id,
        period_id=batch.period_id,
        created_by=batch.created_by,
        published_by=published_by,
        entry_date=_period_start(session, batch),
        description="Saldo de abertura importado",
        source_id=f"opening:{batch.id}",
        source_hash=source_hash,
        lines=lines,
    )
    for row in rows:
        _remember(session, batch, "opening", row.external_id or row.raw["account_code"], journal_id)
    session.add(
        ImportBatchJournal(
            id=new_id("ibj"),
            tenant_id=batch.tenant_id,
            batch_id=batch.id,
            journal_id=journal_id,
            external_id="opening",
        )
    )


def _publish_journals(session, batch: ImportBatch, files: dict, rows: list[ImportRow], published_by: str) -> None:
    groups: dict[str, list[ImportRow]] = {}
    for row in rows:
        groups.setdefault(row.external_id or "", []).append(row)
    for external_id, group in groups.items():
        if _external(session, batch.tenant_id, batch.source_system, "journal", external_id):
            continue
        lines = []
        for row in group:
            account = _account(session, batch.tenant_id, batch.legal_entity_id, row.raw["account_code"])
            if account is None:
                raise DomainError(409, "Conta inválida", "A conta do lançamento não existe no momento da publicação.")
            lines.append(
                {
                    "account_id": account.id,
                    "side": row.raw["side"],
                    "amount": Decimal(row.raw["amount"]),
                    "description": row.raw.get("line_description") or row.raw.get("description") or "Importação",
                    "cost_center_id": row.raw.get("cost_center_id"),
                }
            )
        file_id = group[0].file_id
        source_hash = files[file_id].sha256 if file_id in files else None
        journal_id = post_imported_journal(
            session,
            tenant_id=batch.tenant_id,
            legal_entity_id=batch.legal_entity_id,
            period_id=batch.period_id,
            created_by=batch.created_by,
            published_by=published_by,
            entry_date=date.fromisoformat(group[0].raw["entry_date"]),
            description=group[0].raw.get("description") or "Lançamento importado",
            source_id=batch.id,
            source_hash=source_hash,
            lines=lines,
        )
        _remember(session, batch, "journal", external_id, journal_id)
        session.add(
            ImportBatchJournal(
                id=new_id("ibj"),
                tenant_id=batch.tenant_id,
                batch_id=batch.id,
                journal_id=journal_id,
                external_id=external_id,
            )
        )


def _remember(session: Session, batch: ImportBatch, entity_type: str, external_id: str, internal_id: str) -> None:
    if _external(session, batch.tenant_id, batch.source_system, entity_type, external_id):
        return
    session.add(
        ExternalRef(
            id=new_id("ext"),
            tenant_id=batch.tenant_id,
            source_system=batch.source_system,
            entity_type=entity_type,
            external_id=external_id,
            internal_id=internal_id,
            batch_id=batch.id,
        )
    )
    session.flush()


def _period_start(session: Session, batch: ImportBatch) -> date:
    from contabil.periods.service import require_period

    period = require_period(session, batch.tenant_id, batch.legal_entity_id, batch.period_id or "", for_posting=True)
    return period.start_date


def _write_report(session: Session, batch: ImportBatch, rows: list[ImportRow]) -> ImportReport:
    buckets: dict[str, dict] = {}
    for row in rows:
        code = row.raw.get("account_code") or row.raw.get("code") or ""
        if not code:
            continue
        bucket = buckets.setdefault(
            code,
            {"account_code": code, "source_debit": Decimal("0"), "source_credit": Decimal("0"), "notes": []},
        )
        bucket["source_debit"] += Decimal(row.raw.get("debit") or "0")
        bucket["source_credit"] += Decimal(row.raw.get("credit") or "0")
        if row.status == "invalid":
            bucket["notes"].append(f"linha inválida {row.row_no}")
            if row.error_code == "ACCOUNT_NOT_FOUND":
                bucket["notes"].append("conta não mapeada")
        if row.status == "already_imported" and row.external_id:
            kind = row.raw.get("kind")
            entity_type = {"chart_of_accounts": "account", "opening_balance": "opening", "journal": "journal"}.get(kind or "", "journal")
            ref = _external(session, batch.tenant_id, batch.source_system, entity_type, row.external_id)
            bucket["notes"].append(f"já importado em batch {ref.batch_id}" if ref else "já importado")
    ledger = _ledger_totals(session, batch)
    report_rows = []
    source_debit = Decimal("0")
    source_credit = Decimal("0")
    ledger_debit = Decimal("0")
    ledger_credit = Decimal("0")
    difference = Decimal("0")
    for code, bucket in sorted(buckets.items()):
        posted = ledger.get(code, {"debit": Decimal("0"), "credit": Decimal("0")})
        source_net = bucket["source_debit"] - bucket["source_credit"]
        ledger_net = posted["debit"] - posted["credit"]
        gap = abs(source_net - ledger_net)
        notes = list(dict.fromkeys(bucket["notes"]))
        report_rows.append(
            {
                "account_code": code,
                "source_debit": format_amount(bucket["source_debit"]),
                "source_credit": format_amount(bucket["source_credit"]),
                "ledger_debit": format_amount(posted["debit"]),
                "ledger_credit": format_amount(posted["credit"]),
                "difference": format_amount(gap),
                "explanation": "; ".join(notes),
            }
        )
        source_debit += bucket["source_debit"]
        source_credit += bucket["source_credit"]
        ledger_debit += posted["debit"]
        ledger_credit += posted["credit"]
        difference += gap
    report = ImportReport(
        id=new_id("rpt"),
        tenant_id=batch.tenant_id,
        batch_id=batch.id,
        rows=report_rows,
        debit_total=source_debit,
        credit_total=source_credit,
        difference=difference,
    )
    session.add(report)
    session.flush()
    del ledger_debit, ledger_credit
    return report


def _ledger_totals(session: Session, batch: ImportBatch) -> dict[str, dict[str, Decimal]]:
    journal_ids = list(
        session.scalars(select(ImportBatchJournal.journal_id).where(ImportBatchJournal.batch_id == batch.id)).all()
    )
    totals: dict[str, dict[str, Decimal]] = {}
    if not journal_ids:
        return totals
    rows = session.execute(
        select(Account.code, JournalLine.side, JournalLine.amount)
        .join(JournalLine, JournalLine.account_id == Account.id)
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_id)
        .where(
            JournalLine.journal_id.in_(journal_ids),
            JournalEntry.tenant_id == batch.tenant_id,
            JournalEntry.status.in_(EFFECTIVE_JOURNAL_STATUSES),
        )
    ).all()
    for code, side, amount in rows:
        bucket = totals.setdefault(code, {"debit": Decimal("0"), "credit": Decimal("0")})
        bucket["debit" if side == "debit" else "credit"] += Decimal(amount)
    return totals
