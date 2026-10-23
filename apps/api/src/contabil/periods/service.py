from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from contabil.audit.service import append_event
from contabil.platform.constants import POSTING_PERIOD_STATUSES
from contabil.platform.errors import DomainError
from contabil.platform.ids import new_id
from contabil.platform.outbox import enqueue
from contabil.platform.principal import Principal, ensure_role
from contabil.tables import AccountingPeriod, ReopenRequest


def period_dict(period: AccountingPeriod) -> dict:
    return {
        "period_id": period.id,
        "legal_entity_id": period.legal_entity_id,
        "fiscal_year": period.fiscal_year,
        "month": period.month,
        "start_date": period.start_date.isoformat(),
        "end_date": period.end_date.isoformat(),
        "status": period.status,
    }


def list_periods(session: Session, tenant_id: str, legal_entity_id: str) -> list[AccountingPeriod]:
    return list(
        session.scalars(
            select(AccountingPeriod)
            .where(AccountingPeriod.tenant_id == tenant_id, AccountingPeriod.legal_entity_id == legal_entity_id)
            .order_by(AccountingPeriod.fiscal_year, AccountingPeriod.month)
        ).all()
    )


def require_period(session: Session, tenant_id: str, legal_entity_id: str, period_id: str, *, for_posting: bool) -> AccountingPeriod:
    period = session.scalar(
        select(AccountingPeriod)
        .where(AccountingPeriod.id == period_id, AccountingPeriod.tenant_id == tenant_id)
        .with_for_update()
    )
    if period is None or period.legal_entity_id != legal_entity_id:
        raise DomainError(404, "Não encontrado", "Período não encontrado.")
    if for_posting and period.status not in POSTING_PERIOD_STATUSES:
        raise DomainError(409, "Período fechado", "Período fechado não aceita postagem normal.")
    return period


def lock_period(session: Session, tenant_id: str, period_id: str) -> AccountingPeriod:
    period = session.scalar(
        select(AccountingPeriod).where(AccountingPeriod.id == period_id, AccountingPeriod.tenant_id == tenant_id).with_for_update()
    )
    if period is None:
        raise DomainError(404, "Não encontrado", "Período não encontrado.")
    return period


def close_period(session: Session, principal: Principal, period_id: str) -> AccountingPeriod:
    ensure_role(principal, "approver", "admin")
    period = lock_period(session, principal.tenant_id, period_id)
    if period.status not in POSTING_PERIOD_STATUSES:
        raise DomainError(409, "Estado inválido", "Somente período aberto ou reaberto pode ser fechado.")
    period.status = "closed"
    append_event(
        session,
        tenant_id=principal.tenant_id,
        event_type="other",
        actor_ref=principal.user_id,
        target_type="accounting_period",
        target_ref=period.id,
        reason="Fechamento manual da competência",
        metadata={"action": "period_closed"},
    )
    enqueue(
        session,
        tenant_id=principal.tenant_id,
        event_type="PeriodClosed",
        payload={"period_id": period.id, "legal_entity_id": period.legal_entity_id},
    )
    return period


def request_reopen(session: Session, principal: Principal, period_id: str, reason: str) -> ReopenRequest:
    ensure_role(principal, "preparer", "approver", "admin")
    period = lock_period(session, principal.tenant_id, period_id)
    if period.status != "closed":
        raise DomainError(409, "Estado inválido", "Somente período fechado pode ser reaberto.")
    pending = session.scalar(
        select(ReopenRequest).where(
            ReopenRequest.tenant_id == principal.tenant_id,
            ReopenRequest.period_id == period.id,
            ReopenRequest.status == "pending",
        )
    )
    if pending is not None:
        raise DomainError(409, "Solicitação pendente", "Já existe um pedido de reabertura pendente para este período.")
    reopen = ReopenRequest(
        id=new_id("rop"),
        tenant_id=principal.tenant_id,
        period_id=period.id,
        reason=reason,
        status="pending",
        requested_by=principal.user_id,
    )
    session.add(reopen)
    session.flush()
    return reopen


def approve_reopen(session: Session, principal: Principal, request_id: str) -> AccountingPeriod:
    ensure_role(principal, "approver", "admin")
    reopen = session.scalar(
        select(ReopenRequest).where(ReopenRequest.id == request_id, ReopenRequest.tenant_id == principal.tenant_id).with_for_update()
    )
    if reopen is None:
        raise DomainError(404, "Não encontrado", "Pedido de reabertura não encontrado.")
    if reopen.status != "pending":
        raise DomainError(409, "Estado inválido", "O pedido de reabertura não está pendente.")
    if reopen.requested_by == principal.user_id:
        raise DomainError(403, "Segregação de funções", "Quem solicita a reabertura não pode aprová-la.")
    period = lock_period(session, principal.tenant_id, reopen.period_id)
    if period.status != "closed":
        raise DomainError(409, "Estado inválido", "O período não está fechado.")
    reopen.status = "approved"
    reopen.approved_by = principal.user_id
    reopen.approved_at = datetime.now(timezone.utc).replace(microsecond=0)
    period.status = "reopened"
    append_event(
        session,
        tenant_id=principal.tenant_id,
        event_type="period_reopened",
        actor_ref=principal.user_id,
        target_type="accounting_period",
        target_ref=period.id,
        reason=reopen.reason,
        metadata={"action": "period_reopened", "reopen_request_id": reopen.id},
    )
    enqueue(
        session,
        tenant_id=principal.tenant_id,
        event_type="PeriodReopened",
        payload={"period_id": period.id, "legal_entity_id": period.legal_entity_id, "reopen_request_id": reopen.id},
    )
    return period


def reopen_dict(reopen: ReopenRequest) -> dict:
    return {
        "reopen_request_id": reopen.id,
        "period_id": reopen.period_id,
        "reason": reopen.reason,
        "status": reopen.status,
        "requested_by": reopen.requested_by,
        "approved_by": reopen.approved_by,
    }
