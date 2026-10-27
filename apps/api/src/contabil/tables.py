from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from contabil.platform.db import Base


def _now() -> datetime:
    from datetime import timezone

    return datetime.now(timezone.utc)


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AppUser(Base):
    __tablename__ = "app_users"

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", name="uq_memberships_tenant_user"),)

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("app_users.id"))
    roles: Mapped[list[str]] = mapped_column(ARRAY(String(40)))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class LegalEntity(Base):
    __tablename__ = "legal_entities"
    __table_args__ = (UniqueConstraint("tenant_id", "cnpj", name="uq_legal_entities_tenant_cnpj"),)

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    name: Mapped[str] = mapped_column(String(200))
    cnpj: Mapped[str] = mapped_column(String(14))
    currency: Mapped[str] = mapped_column(String(3))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Establishment(Base):
    __tablename__ = "establishments"

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    legal_entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"))
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ChartOfAccounts(Base):
    __tablename__ = "charts_of_accounts"
    __table_args__ = (UniqueConstraint("legal_entity_id", name="uq_charts_entity"),)

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    legal_entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"))
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("legal_entity_id", "code", name="uq_accounts_entity_code"),)

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    legal_entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"))
    chart_id: Mapped[str] = mapped_column(ForeignKey("charts_of_accounts.id"))
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    account_type: Mapped[str] = mapped_column(String(20))
    postable: Mapped[bool] = mapped_column(Boolean)
    active: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class CostCenter(Base):
    __tablename__ = "cost_centers"
    __table_args__ = (UniqueConstraint("legal_entity_id", "code", name="uq_cost_centers_entity_code"),)

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    legal_entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"))
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    active: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AccountingPeriod(Base):
    __tablename__ = "accounting_periods"
    __table_args__ = (UniqueConstraint("legal_entity_id", "fiscal_year", "month", name="uq_periods_entity_month"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    legal_entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"))
    fiscal_year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ReopenRequest(Base):
    __tablename__ = "reopen_requests"

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    period_id: Mapped[str] = mapped_column(ForeignKey("accounting_periods.id"))
    reason: Mapped[str] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(20))
    requested_by: Mapped[str] = mapped_column(String(160))
    approved_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(20))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    legal_entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"))
    period_id: Mapped[str] = mapped_column(ForeignKey("accounting_periods.id"))
    status: Mapped[str] = mapped_column(String(32))
    currency: Mapped[str] = mapped_column(String(3))
    entry_date: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(2000))
    source_type: Mapped[str] = mapped_column(String(40))
    source_id: Mapped[str] = mapped_column(String(200))
    source_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reverses_journal_id: Mapped[str | None] = mapped_column(ForeignKey("journal_entries.id"), nullable=True)
    reversal_journal_id: Mapped[str | None] = mapped_column(ForeignKey("journal_entries.id"), nullable=True)
    created_by: Mapped[str] = mapped_column(String(160))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    audit_event_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class JournalLine(Base):
    __tablename__ = "journal_lines"
    __table_args__ = (UniqueConstraint("journal_id", "line_no", name="uq_lines_journal_no"),)

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    journal_id: Mapped[str] = mapped_column(ForeignKey("journal_entries.id", ondelete="CASCADE"))
    line_no: Mapped[int] = mapped_column(Integer)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    side: Mapped[str] = mapped_column(String(10))
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    description: Mapped[str] = mapped_column(String(1000))
    cost_center_id: Mapped[str | None] = mapped_column(ForeignKey("cost_centers.id"), nullable=True)
    dimension_values: Mapped[dict[str, str]] = mapped_column(JSONB)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(20))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    event_type: Mapped[str] = mapped_column(String(64))
    actor_kind: Mapped[str] = mapped_column(String(20))
    actor_ref: Mapped[str] = mapped_column(String(160))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    target_type: Mapped[str] = mapped_column(String(120))
    target_ref: Mapped[str] = mapped_column(String(200))
    reason: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    details: Mapped[dict] = mapped_column("metadata", JSONB)
    event_hash: Mapped[str] = mapped_column(String(200))
    previous_hash: Mapped[str | None] = mapped_column(String(200), nullable=True)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (UniqueConstraint("tenant_id", "key", name="uq_idempotency_tenant_key"),)

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    key: Mapped[str] = mapped_column(String(200))
    request_hash: Mapped[str] = mapped_column(String(64))
    response_status: Mapped[int] = mapped_column(Integer)
    response_body: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    event_type: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    dead_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SourceDocument(Base):
    __tablename__ = "source_documents"
    __table_args__ = (UniqueConstraint("tenant_id", "sha256", name="uq_documents_tenant_sha"),)

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(20))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    legal_entity_id: Mapped[str | None] = mapped_column(ForeignKey("legal_entities.id"), nullable=True)
    document_type: Mapped[str] = mapped_column(String(40))
    competence: Mapped[str | None] = mapped_column(String(7), nullable=True)
    file_name: Mapped[str] = mapped_column(String(300))
    media_type: Mapped[str] = mapped_column(String(160))
    sha256: Mapped[str] = mapped_column(String(64))
    object_ref: Mapped[str] = mapped_column(String(1000))
    size_bytes: Mapped[int] = mapped_column(Integer)
    source_type: Mapped[str] = mapped_column(String(20))
    source_ref: Mapped[str | None] = mapped_column(String(300), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    retention_policy_id: Mapped[str] = mapped_column(String(160))
    legal_hold: Mapped[bool] = mapped_column(Boolean)
    retain_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    classification: Mapped[str | None] = mapped_column(String(160), nullable=True)
    derived_versions: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(20))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    legal_entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"))
    source_system: Mapped[str] = mapped_column(String(160))
    mode: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(32))
    idempotency_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    period_id: Mapped[str | None] = mapped_column(ForeignKey("accounting_periods.id"), nullable=True)
    created_by: Mapped[str] = mapped_column(String(160))
    published_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    rows_received: Mapped[int] = mapped_column(Integer, default=0)
    rows_valid: Mapped[int] = mapped_column(Integer, default=0)
    rows_invalid: Mapped[int] = mapped_column(Integer, default=0)
    debit_total: Mapped[Decimal] = mapped_column(Numeric(20, 6), default=Decimal("0"))
    credit_total: Mapped[Decimal] = mapped_column(Numeric(20, 6), default=Decimal("0"))
    difference: Mapped[Decimal] = mapped_column(Numeric(20, 6), default=Decimal("0"))
    reconciliation_report_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ImportBatchFile(Base):
    __tablename__ = "import_batch_files"

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    batch_id: Mapped[str] = mapped_column(ForeignKey("import_batches.id"))
    document_id: Mapped[str] = mapped_column(ForeignKey("source_documents.id"))
    kind: Mapped[str] = mapped_column(String(40))
    sha256: Mapped[str] = mapped_column(String(64))


class ImportRow(Base):
    __tablename__ = "import_rows"

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    batch_id: Mapped[str] = mapped_column(ForeignKey("import_batches.id"))
    file_id: Mapped[str] = mapped_column(ForeignKey("import_batch_files.id"))
    row_no: Mapped[int] = mapped_column(Integer)
    external_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    raw: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(32))
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class ExternalRef(Base):
    __tablename__ = "external_refs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_system", "entity_type", "external_id", name="uq_external_refs"),
    )

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    source_system: Mapped[str] = mapped_column(String(160))
    entity_type: Mapped[str] = mapped_column(String(40))
    external_id: Mapped[str] = mapped_column(String(200))
    internal_id: Mapped[str] = mapped_column(String(160))
    batch_id: Mapped[str] = mapped_column(ForeignKey("import_batches.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ImportBatchJournal(Base):
    __tablename__ = "import_batch_journals"

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    batch_id: Mapped[str] = mapped_column(ForeignKey("import_batches.id"))
    journal_id: Mapped[str] = mapped_column(ForeignKey("journal_entries.id"))
    external_id: Mapped[str] = mapped_column(String(200))


class ImportReport(Base):
    __tablename__ = "import_reports"
    __table_args__ = (UniqueConstraint("batch_id", name="uq_import_reports_batch"),)

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    batch_id: Mapped[str] = mapped_column(ForeignKey("import_batches.id"))
    rows: Mapped[list] = mapped_column(JSONB)
    debit_total: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    credit_total: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    difference: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Operation(Base):
    __tablename__ = "operations"

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    kind: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20))
    correlation_id: Mapped[str] = mapped_column(String(80))
    target_ref: Mapped[str] = mapped_column(String(200))
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class BankAccount(Base):
    __tablename__ = "bank_accounts"
    __table_args__ = (UniqueConstraint("legal_entity_id", "account_id", name="uq_bank_accounts_entity_account"),)

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    legal_entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"))
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    name: Mapped[str] = mapped_column(String(200))
    bank_code: Mapped[str] = mapped_column(String(8))
    branch: Mapped[str] = mapped_column(String(20))
    account_number_masked: Mapped[str] = mapped_column(String(4))
    currency: Mapped[str] = mapped_column(String(3))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class BankStatement(Base):
    __tablename__ = "bank_statements"

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    bank_account_id: Mapped[str] = mapped_column(ForeignKey("bank_accounts.id"))
    document_id: Mapped[str] = mapped_column(ForeignKey("source_documents.id"))
    format: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(20))
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    closing_balance: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    transactions_received: Mapped[int] = mapped_column(Integer, default=0)
    transactions_new: Mapped[int] = mapped_column(Integer, default=0)
    transactions_duplicate: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_by: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class BankTransaction(Base):
    __tablename__ = "bank_transactions"
    __table_args__ = (UniqueConstraint("bank_account_id", "fingerprint", name="uq_bank_transactions_fingerprint"),)

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    bank_account_id: Mapped[str] = mapped_column(ForeignKey("bank_accounts.id"))
    statement_id: Mapped[str] = mapped_column(ForeignKey("bank_statements.id"))
    transaction_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    direction: Mapped[str] = mapped_column(String(10))
    description: Mapped[str] = mapped_column(String(2000))
    external_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ReconciliationCase(Base):
    __tablename__ = "reconciliation_cases"
    __table_args__ = (UniqueConstraint("transaction_id", name="uq_reconciliation_cases_transaction"),)

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(20))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    bank_account_id: Mapped[str] = mapped_column(ForeignKey("bank_accounts.id"))
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    transaction_id: Mapped[str] = mapped_column(ForeignKey("bank_transactions.id"))
    status: Mapped[str] = mapped_column(String(20))
    candidates: Mapped[list] = mapped_column(JSONB)
    selected_candidate_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    audit_event_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    journal_id: Mapped[str | None] = mapped_column(ForeignKey("journal_entries.id"), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ReconciliationMatch(Base):
    __tablename__ = "reconciliation_matches"

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    case_id: Mapped[str] = mapped_column(ForeignKey("reconciliation_cases.id"))
    journal_line_id: Mapped[str] = mapped_column(ForeignKey("journal_lines.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class CloseRun(Base):
    __tablename__ = "close_runs"
    __table_args__ = (UniqueConstraint("period_id", "run_number", name="uq_close_runs_period_number"),)

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    legal_entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"))
    period_id: Mapped[str] = mapped_column(ForeignKey("accounting_periods.id"))
    run_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))
    checklist_version: Mapped[str] = mapped_column(String(40))
    closed_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    snapshot_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reopened_reason: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    audit_event_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_by: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class CloseRunDecision(Base):
    __tablename__ = "close_run_decisions"
    __table_args__ = (UniqueConstraint("close_run_id", "item_id", name="uq_close_run_decisions_item"),)

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    close_run_id: Mapped[str] = mapped_column(ForeignKey("close_runs.id"))
    item_id: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    decided_by: Mapped[str] = mapped_column(String(160))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class CloseSnapshot(Base):
    __tablename__ = "close_snapshots"
    __table_args__ = (UniqueConstraint("close_run_id", name="uq_close_snapshots_run"),)

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    close_run_id: Mapped[str] = mapped_column(ForeignKey("close_runs.id"))
    payload: Mapped[dict] = mapped_column(JSONB)
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
