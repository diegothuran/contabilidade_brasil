"""Pagamentos com retenção na fonte de uma competência, base da prévia da EFD-Reinf R-4000 (ADR 032)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from contabil.audit.service import append_event
from contabil.periods.service import require_period
from contabil.platform.auth import format_utc
from contabil.platform.errors import DomainError
from contabil.platform.ids import new_id
from contabil.platform.principal import Principal, ensure_office, ensure_role
from contabil.tables import AccountingPeriod, WithholdingPayment
from contabil.tenancy.service import require_entity
from contabil.withholdings.validators import CleanPayment, PaymentInput, validate_payment

WRITER_ROLES = ("preparer", "approver", "admin")
LIST_LIMIT = 500


def _money(value: Decimal | None) -> str | None:
    return None if value is None else format(Decimal(value).quantize(Decimal("0.01")), "f")


def payment_dict(row: WithholdingPayment) -> dict:
    return {
        "id": row.id,
        "legal_entity_id": row.legal_entity_id,
        "period_id": row.period_id,
        "payment_date": row.payment_date.isoformat(),
        "beneficiary_kind": row.beneficiary_kind,
        "beneficiary_document": row.beneficiary_document,
        "beneficiary_name": row.beneficiary_name,
        "nature_code": row.nature_code,
        "gross_amount": _money(row.gross_amount),
        "ir_base": _money(row.ir_base),
        "ir_amount": _money(row.ir_amount),
        "csrf_base": _money(row.csrf_base),
        "csrf_amount": _money(row.csrf_amount),
        "description": row.description,
        "created_by": row.created_by,
        "created_at": format_utc(row.created_at) if row.created_at else None,
    }


def payments_of_period(session: Session, tenant_id: str, legal_entity_id: str, period_id: str) -> list[WithholdingPayment]:
    return list(
        session.scalars(
            select(WithholdingPayment)
            .where(
                WithholdingPayment.tenant_id == tenant_id,
                WithholdingPayment.legal_entity_id == legal_entity_id,
                WithholdingPayment.period_id == period_id,
            )
            .order_by(WithholdingPayment.payment_date, WithholdingPayment.created_at, WithholdingPayment.id)
        ).all()
    )


def list_payments(session: Session, principal: Principal, legal_entity_id: str, period_id: str | None) -> dict:
    ensure_office(principal)
    entity = require_entity(session, principal.tenant_id, legal_entity_id)
    query = select(WithholdingPayment).where(
        WithholdingPayment.tenant_id == principal.tenant_id, WithholdingPayment.legal_entity_id == entity.id
    )
    if period_id:
        query = query.where(WithholdingPayment.period_id == period_id)
    rows = session.scalars(
        query.order_by(WithholdingPayment.payment_date, WithholdingPayment.created_at, WithholdingPayment.id).limit(LIST_LIMIT)
    ).all()
    return {"items": [payment_dict(row) for row in rows]}


def insert_payment(
    session: Session, tenant_id: str, actor: str, legal_entity_id: str, period: AccountingPeriod, clean: CleanPayment
) -> WithholdingPayment:
    """Grava o pagamento já conferido e registra a auditoria. Quem chama confere papel e competência."""
    row = WithholdingPayment(
        id=new_id("whp"),
        tenant_id=tenant_id,
        legal_entity_id=legal_entity_id,
        period_id=period.id,
        payment_date=clean.payment_date,
        beneficiary_kind=clean.beneficiary_kind,
        beneficiary_document=clean.beneficiary_document,
        beneficiary_name=clean.beneficiary_name,
        nature_code=clean.nature_code,
        gross_amount=clean.gross_amount,
        ir_base=clean.ir_base,
        ir_amount=clean.ir_amount,
        csrf_base=clean.csrf_base,
        csrf_amount=clean.csrf_amount,
        description=clean.description,
        created_by=actor,
        created_at=datetime.now(timezone.utc),
    )
    session.add(row)
    session.flush()
    # A trilha não leva CPF, CNPJ nem nome do beneficiário.
    append_event(
        session,
        tenant_id=tenant_id,
        event_type="other",
        actor_ref=actor,
        target_type="withholding_payment",
        target_ref=row.id,
        metadata={
            "action": "withholding_payment_created",
            "legal_entity_id": legal_entity_id,
            "period_id": period.id,
            "beneficiary_kind": clean.beneficiary_kind,
            "nature_code": clean.nature_code,
            "gross_amount": _money(clean.gross_amount),
        },
    )
    return row


def create_payment(session: Session, principal: Principal, legal_entity_id: str, period_id: str | None, data: PaymentInput) -> dict:
    ensure_office(principal)
    ensure_role(principal, *WRITER_ROLES)
    entity = require_entity(session, principal.tenant_id, legal_entity_id)
    if not period_id:
        raise DomainError(400, "Pagamento inválido", "Confira os campos destacados.", errors=[{"loc": ["period_id"], "msg": "Informe a competência."}])
    period = require_period(session, principal.tenant_id, entity.id, period_id, for_posting=True)
    clean = validate_payment(data, period_start=period.start_date, period_end=period.end_date)
    row = insert_payment(session, principal.tenant_id, principal.user_id, entity.id, period, clean)
    return payment_dict(row)


def delete_payment(session: Session, principal: Principal, legal_entity_id: str, payment_id: str) -> None:
    ensure_office(principal)
    ensure_role(principal, *WRITER_ROLES)
    entity = require_entity(session, principal.tenant_id, legal_entity_id)
    row = session.scalar(
        select(WithholdingPayment).where(
            WithholdingPayment.id == payment_id,
            WithholdingPayment.tenant_id == principal.tenant_id,
            WithholdingPayment.legal_entity_id == entity.id,
        )
    )
    if row is None:
        raise DomainError(404, "Não encontrado", "Pagamento não encontrado.")
    period = require_period(session, principal.tenant_id, entity.id, row.period_id, for_posting=True)
    metadata = {
        "action": "withholding_payment_deleted",
        "legal_entity_id": entity.id,
        "period_id": period.id,
        "beneficiary_kind": row.beneficiary_kind,
        "nature_code": row.nature_code,
        "gross_amount": _money(row.gross_amount),
    }
    session.delete(row)
    session.flush()
    append_event(
        session,
        tenant_id=principal.tenant_id,
        event_type="other",
        actor_ref=principal.user_id,
        target_type="withholding_payment",
        target_ref=payment_id,
        metadata=metadata,
    )
