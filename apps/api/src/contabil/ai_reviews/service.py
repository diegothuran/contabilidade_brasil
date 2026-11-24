"""Revisão do mês por IA: pedido, leitura e decisão do contador (ADR 036).

Nada aqui cria lançamento, decide item do checklist ou publica para o cliente.
"""
from __future__ import annotations

from datetime import datetime, time, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from contabil.ai_reviews.model import PROMPT_VERSION
from contabil.ai_reviews.packet import PACKET_VERSION, build_packet, packet_sha256
from contabil.audit.service import append_event
from contabil.closing.service import period_counts
from contabil.imports.service import operation_dict
from contabil.platform.auth import format_utc
from contabil.platform.clock import BRASILIA, brasilia_today
from contabil.platform.correlation import correlation_id
from contabil.platform.errors import DomainError
from contabil.platform.ids import new_id
from contabil.platform.outbox import enqueue
from contabil.platform.principal import Principal, ensure_role
from contabil.platform.settings import get_settings
from contabil.tables import AccountingPeriod, AiReview, AiReviewDecision, AiReviewFinding, Operation

OPERATION_KIND = "month_review"
EVENT_TYPE = "MonthReviewRequested"
DECISIONS = ("procede", "nao_procede")
NOTE_LIMIT = 500
# Contagem do checklist (closing.period_counts) → chave do pacote.
_COUNT_KEYS = {
    "lancamentos_rascunho": "journals_draft",
    "lancamentos_pendentes": "journals_pending_approval",
    "lancamentos_aprovados_nao_publicados": "journals_approved",
    "casos_conciliacao_pendentes": "reconciliation_pending",
    "pedidos_documento_abertos": "document_requests_open",
    "alertas_extrato": "statement_alerts",
}


def reviews_today(session: Session, tenant_id: str, now: datetime | None = None) -> int:
    """Revisões pedidas pelo escritório desde 00:00 de Brasília, em qualquer estado."""
    start = datetime.combine(brasilia_today(now), time.min, tzinfo=BRASILIA).astimezone(timezone.utc)
    total = session.scalar(
        select(func.count()).select_from(AiReview).where(AiReview.tenant_id == tenant_id, AiReview.created_at >= start)
    )
    return int(total or 0)


def current_packet(session: Session, principal: Principal, period: AccountingPeriod) -> dict:
    counts = period_counts(session, principal, period)
    pending = {key: int(counts.get(source, 0) or 0) for key, source in _COUNT_KEYS.items()}
    return build_packet(session, principal, period, pending)


def _period(session: Session, tenant_id: str, period_id: str) -> AccountingPeriod:
    period = session.scalar(
        select(AccountingPeriod).where(AccountingPeriod.id == period_id, AccountingPeriod.tenant_id == tenant_id)
    )
    if period is None:
        raise DomainError(404, "Não encontrado", "Período não encontrado.")
    return period


def request_review(session: Session, principal: Principal, period_id: str) -> dict:
    ensure_role(principal, "preparer", "approver", "admin")
    settings = get_settings()
    if not settings.claude_api_key:
        raise DomainError(503, "Revisão por IA indisponível", "Este ambiente não tem a chave do modelo configurada.")
    period = _period(session, principal.tenant_id, period_id)
    if reviews_today(session, principal.tenant_id) >= settings.review_daily_limit:
        raise DomainError(
            429,
            "Limite diário de revisões por IA atingido",
            "O escritório já pediu o máximo de revisões hoje. Tente amanhã.",
        )
    now = datetime.now(timezone.utc)
    operation = Operation(
        id=new_id("op"),
        tenant_id=principal.tenant_id,
        kind=OPERATION_KIND,
        status="accepted",
        correlation_id=correlation_id.get() or "",
        target_ref=period.id,
    )
    session.add(operation)
    session.flush()
    review = AiReview(
        id=new_id("airev"),
        tenant_id=principal.tenant_id,
        legal_entity_id=period.legal_entity_id,
        period_id=period.id,
        operation_id=operation.id,
        status="requested",
        model=settings.review_model[:80],
        prompt_version=PROMPT_VERSION,
        packet_version=PACKET_VERSION,
        input_tokens=0,
        output_tokens=0,
        requested_by=principal.user_id,
        created_at=now,
    )
    session.add(review)
    session.flush()
    enqueue(
        session,
        tenant_id=principal.tenant_id,
        event_type=EVENT_TYPE,
        payload={"review_id": review.id, "operation_id": operation.id},
    )
    append_event(
        session,
        tenant_id=principal.tenant_id,
        event_type="other",
        actor_ref=principal.user_id,
        target_type="ai_review",
        target_ref=review.id,
        metadata={"action": "ai_review_requested", "period_id": period.id},
    )
    return {**operation_dict(operation), "review_id": review.id}


def _latest_decisions(session: Session, tenant_id: str, finding_ids: list[str]) -> dict[str, AiReviewDecision]:
    if not finding_ids:
        return {}
    rows = session.scalars(
        select(AiReviewDecision)
        .where(AiReviewDecision.tenant_id == tenant_id, AiReviewDecision.finding_id.in_(finding_ids))
        .order_by(AiReviewDecision.created_at, AiReviewDecision.id)
    ).all()
    latest: dict[str, AiReviewDecision] = {}
    for row in rows:
        latest[row.finding_id] = row
    return latest


def _decision_dict(row: AiReviewDecision | None) -> dict | None:
    if row is None:
        return None
    return {"decision": row.decision, "note": row.note, "decided_by": row.decided_by, "decided_at": format_utc(row.created_at)}


def _review_dict(review: AiReview, findings: list[AiReviewFinding], decisions: dict[str, AiReviewDecision]) -> dict:
    return {
        "review_id": review.id,
        "period_id": review.period_id,
        "legal_entity_id": review.legal_entity_id,
        "operation_id": review.operation_id,
        "status": review.status,
        "model": review.model,
        "prompt_version": review.prompt_version,
        "packet_version": review.packet_version,
        "stop_reason": review.stop_reason,
        "requested_by": review.requested_by,
        "requested_at": format_utc(review.created_at),
        "completed_at": format_utc(review.completed_at) if review.completed_at else None,
        "stale": False,
        "findings": [
            {
                "finding_id": finding.id,
                "position": finding.position,
                "relevance": finding.relevance,
                "category": finding.category,
                "title": finding.title,
                "explanation": finding.explanation,
                "evidence": list(finding.evidence or []),
                "source": "model",
                "decision": _decision_dict(decisions.get(finding.id)),
            }
            for finding in findings
        ],
    }


def list_reviews(session: Session, principal: Principal, period_id: str) -> dict:
    period = _period(session, principal.tenant_id, period_id)
    reviews = session.scalars(
        select(AiReview)
        .where(AiReview.tenant_id == principal.tenant_id, AiReview.period_id == period.id)
        .order_by(AiReview.created_at.desc(), AiReview.id.desc())
    ).all()
    review_ids = [review.id for review in reviews]
    findings = (
        session.scalars(
            select(AiReviewFinding)
            .where(AiReviewFinding.tenant_id == principal.tenant_id, AiReviewFinding.review_id.in_(review_ids))
            .order_by(AiReviewFinding.review_id, AiReviewFinding.position)
        ).all()
        if review_ids
        else []
    )
    decisions = _latest_decisions(session, principal.tenant_id, [finding.id for finding in findings])
    by_review: dict[str, list[AiReviewFinding]] = {}
    for finding in findings:
        by_review.setdefault(finding.review_id, []).append(finding)
    items = [_review_dict(review, by_review.get(review.id, []), decisions) for review in reviews]
    # Só a mais recente concluída ganha o aviso; recalcular o pacote de todas custaria caro.
    for item, review in zip(items, reviews):
        if review.input_sha256:
            item["stale"] = packet_sha256(current_packet(session, principal, period)) != review.input_sha256
            break
    return {
        "period_id": period.id,
        "ai_reviews_enabled": bool(get_settings().claude_api_key),
        "items": items,
    }


def decide_finding(session: Session, principal: Principal, finding_id: str, decision: str, note: str | None) -> dict:
    ensure_role(principal, "preparer", "approver", "admin")
    if decision not in DECISIONS:
        raise DomainError(400, "Decisão inválida", "Use procede ou nao_procede.")
    finding = session.scalar(
        select(AiReviewFinding).where(AiReviewFinding.id == finding_id, AiReviewFinding.tenant_id == principal.tenant_id)
    )
    if finding is None:
        raise DomainError(404, "Não encontrado", "Ponto da revisão não encontrado.")
    text = (note or "").strip()[:NOTE_LIMIT] or None
    row = AiReviewDecision(
        id=new_id("aidec"),
        tenant_id=principal.tenant_id,
        finding_id=finding.id,
        decision=decision,
        note=text,
        decided_by=principal.user_id,
        created_at=datetime.now(timezone.utc),
    )
    session.add(row)
    session.flush()
    append_event(
        session,
        tenant_id=principal.tenant_id,
        event_type="other",
        actor_ref=principal.user_id,
        target_type="ai_review_finding",
        target_ref=finding.id,
        metadata={"action": "ai_review_finding_decided", "review_id": finding.review_id, "decision": decision},
    )
    return {"finding_id": finding.id, "review_id": finding.review_id, **(_decision_dict(row) or {})}
