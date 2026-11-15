"""Resumo do mês para o empresário: gera, publica e retira (ADR 034). Sem IA; as frases são fixas."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from contabil.audit.service import append_event
from contabil.client_summaries.compose import compose_summary
from contabil.ledger.service import account_sums
from contabil.ledger.statements import income_statement
from contabil.periods.service import lock_period
from contabil.platform.auth import format_utc
from contabil.platform.errors import DomainError
from contabil.platform.ids import new_id
from contabil.platform.principal import Principal, ensure_client, ensure_role
from contabil.tables import AccountingPeriod, BankAccount, ClientSummary

MIN_REASON = 10
REOPEN_REASON = "Competência reaberta"


def summary_dict(row: ClientSummary) -> dict:
    return {
        "summary_id": row.id,
        "period_id": row.period_id,
        "legal_entity_id": row.legal_entity_id,
        "status": row.status,
        "payload": row.payload,
        "created_by": row.created_by,
        "published_by": row.published_by,
        "published_at": format_utc(row.published_at) if row.published_at else None,
        "withdrawn_reason": row.withdrawn_reason,
    }


def portal_dict(row: ClientSummary) -> dict:
    """O cliente não vê quem gerou nem quem publicou (ADR 025)."""
    return {
        "summary_id": row.id,
        "period_id": row.period_id,
        "competence": row.payload.get("competence"),
        "payload": row.payload,
        "published_at": format_utc(row.published_at) if row.published_at else None,
    }


def _live(session: Session, tenant_id: str, period_id: str, *, lock: bool = False) -> ClientSummary | None:
    query = select(ClientSummary).where(
        ClientSummary.tenant_id == tenant_id, ClientSummary.period_id == period_id, ClientSummary.status != "withdrawn"
    )
    return session.scalar(query.with_for_update() if lock else query)


def _section_month(statement: dict, account_type: str) -> Decimal:
    section = next(item for item in statement["sections"] if item["account_type"] == account_type)
    return Decimal(section["month"])


def _cash(session: Session, tenant_id: str, legal_entity_id: str, period: AccountingPeriod) -> Decimal:
    bank_accounts = set(
        session.scalars(
            select(BankAccount.account_id).where(
                BankAccount.tenant_id == tenant_id, BankAccount.legal_entity_id == legal_entity_id
            )
        ).all()
    )
    sums = account_sums(session, tenant_id, legal_entity_id, AccountingPeriod.end_date <= period.end_date)
    return sum((sums.get(account_id, Decimal("0")) for account_id in bank_accounts), Decimal("0"))


def generate_summary_status(session: Session, principal: Principal, period_id: str) -> tuple[dict, bool]:
    ensure_role(principal, "preparer", "approver", "admin")
    period = lock_period(session, principal.tenant_id, period_id)
    if period.status != "closed":
        raise DomainError(409, "Competência aberta", "O resumo só é gerado depois do fechamento da competência.")
    row = _live(session, principal.tenant_id, period.id, lock=True)
    if row is not None and row.status == "published":
        raise DomainError(409, "Resumo já publicado", "Retire o resumo publicado antes de gerar outro.")
    statement = income_statement(session, principal, period.legal_entity_id, period.id)
    payload = compose_summary(
        revenue=_section_month(statement, "revenue"),
        expense=_section_month(statement, "expense"),
        cash=_cash(session, principal.tenant_id, period.legal_entity_id, period),
        fiscal_year=period.fiscal_year,
        month=period.month,
    )
    created = row is None
    if row is None:
        row = ClientSummary(
            id=new_id("csum"),
            tenant_id=principal.tenant_id,
            legal_entity_id=period.legal_entity_id,
            period_id=period.id,
            status="draft",
            payload=payload,
            created_by=principal.user_id,
        )
        session.add(row)
    else:
        row.payload = payload
        row.created_by = principal.user_id
    session.flush()
    append_event(
        session,
        tenant_id=principal.tenant_id,
        event_type="other",
        actor_ref=principal.user_id,
        target_type="client_summary",
        target_ref=row.id,
        metadata={"action": "client_summary_generated", "period_id": period.id},
    )
    return summary_dict(row), created


def generate_summary(session: Session, principal: Principal, period_id: str) -> dict:
    return generate_summary_status(session, principal, period_id)[0]


def get_summary(session: Session, principal: Principal, period_id: str) -> dict:
    """O não retirado mais recente; sem ele, o retirado mais recente, com o motivo."""
    period = session.scalar(
        select(AccountingPeriod).where(AccountingPeriod.id == period_id, AccountingPeriod.tenant_id == principal.tenant_id)
    )
    if period is None:
        raise DomainError(404, "Não encontrado", "Período não encontrado.")
    row = _live(session, principal.tenant_id, period.id)
    if row is None:
        row = session.scalar(
            select(ClientSummary)
            .where(
                ClientSummary.tenant_id == principal.tenant_id,
                ClientSummary.period_id == period.id,
                ClientSummary.status == "withdrawn",
            )
            .order_by(ClientSummary.created_at.desc(), ClientSummary.id.desc())
            .limit(1)
        )
    if row is None:
        raise DomainError(404, "Não encontrado", "Não há resumo para esta competência.")
    return summary_dict(row)


def publish_summary(session: Session, principal: Principal, period_id: str) -> dict:
    ensure_role(principal, "approver", "admin")
    period = lock_period(session, principal.tenant_id, period_id)
    row = _live(session, principal.tenant_id, period.id, lock=True)
    if row is None:
        raise DomainError(404, "Não encontrado", "Não há resumo para esta competência.")
    if row.status != "draft":
        raise DomainError(409, "Estado inválido", "O resumo já está publicado.")
    if period.status != "closed":
        raise DomainError(409, "Competência aberta", "A competência foi reaberta; gere o resumo de novo depois de fechar.")
    if principal.user_id == row.created_by:
        raise DomainError(409, "Quem gerou não publica", "Outra pessoa autorizada precisa publicar o resumo.")
    row.status = "published"
    row.published_by = principal.user_id
    row.published_at = datetime.now(timezone.utc).replace(microsecond=0)
    session.flush()
    append_event(
        session,
        tenant_id=principal.tenant_id,
        event_type="other",
        actor_ref=principal.user_id,
        target_type="client_summary",
        target_ref=row.id,
        metadata={"action": "client_summary_published", "period_id": period.id},
    )
    return summary_dict(row)


def withdraw_summary(session: Session, principal: Principal, period_id: str, reason: str) -> dict:
    ensure_role(principal, "approver", "admin")
    reason = (reason or "").strip()
    if len(reason) < MIN_REASON:
        raise DomainError(400, "Motivo insuficiente", f"Explique a retirada com pelo menos {MIN_REASON} caracteres.")
    period = lock_period(session, principal.tenant_id, period_id)
    row = _live(session, principal.tenant_id, period.id, lock=True)
    if row is None or row.status != "published":
        raise DomainError(404, "Não encontrado", "Não há resumo publicado nesta competência.")
    row.status = "withdrawn"
    row.withdrawn_reason = reason[:500]
    session.flush()
    append_event(
        session,
        tenant_id=principal.tenant_id,
        event_type="other",
        actor_ref=principal.user_id,
        target_type="client_summary",
        target_ref=row.id,
        reason=reason,
        metadata={"action": "client_summary_withdrawn", "period_id": period.id},
    )
    return summary_dict(row)


def withdraw_on_reopen(session: Session, tenant_id: str, period_id: str) -> None:
    """Chamada na mesma transação da reabertura: o resumo publicado ou em rascunho deixa de valer."""
    row = _live(session, tenant_id, period_id, lock=True)
    if row is None:
        return
    # Rascunho também sai: depois do novo fechamento ele teria números velhos.
    row.status = "withdrawn"
    row.withdrawn_reason = REOPEN_REASON
    session.flush()
    append_event(
        session,
        tenant_id=tenant_id,
        event_type="other",
        actor_ref="system",
        actor_kind="system",
        target_type="client_summary",
        target_ref=row.id,
        reason=REOPEN_REASON,
        metadata={"action": "client_summary_withdrawn", "period_id": period_id},
    )


def list_client_summaries(session: Session, principal: Principal) -> dict:
    ensure_client(principal)
    rows = session.scalars(
        select(ClientSummary)
        .where(
            ClientSummary.tenant_id == principal.tenant_id,
            ClientSummary.legal_entity_id == principal.legal_entity_id,
            ClientSummary.status == "published",
        )
        .order_by(ClientSummary.published_at.desc(), ClientSummary.id.desc())
    ).all()
    return {"items": [portal_dict(row) for row in rows]}


def client_summary(session: Session, principal: Principal, summary_id: str) -> dict:
    ensure_client(principal)
    row = session.scalar(
        select(ClientSummary).where(
            ClientSummary.id == summary_id,
            ClientSummary.tenant_id == principal.tenant_id,
            ClientSummary.legal_entity_id == principal.legal_entity_id,
            ClientSummary.status == "published",
        )
    )
    if row is None:
        raise DomainError(404, "Não encontrado", "Resumo não encontrado.")
    return portal_dict(row)
