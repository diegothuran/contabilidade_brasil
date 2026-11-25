"""Handler do outbox para `MonthReviewRequested` (ADR 036).

Uma chamada ao modelo por despacho. O log leva ids, contagens e stop_reason; nunca o pacote,
a resposta ou o nome de conta.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from contabil.ai_reviews.model import (
    INCOMPLETE_STOPS,
    AnthropicReviewClient,
    ReviewClient,
    build_review_prompt,
    validate_points,
)
from contabil.ai_reviews.packet import packet_refs, packet_sha256
from contabil.ai_reviews.service import current_packet
from contabil.imports.service import mark_operation_running
from contabil.platform.auth import apply_tenant
from contabil.platform.db import session_factory
from contabil.platform.ids import new_id
from contabil.platform.principal import Principal
from contabil.platform.settings import get_settings
from contabil.tables import AccountingPeriod, AiReview, AiReviewFinding, Operation

logger = logging.getLogger("contabil.ai_reviews")

INCOMPLETE_WARNING = "resposta_incompleta"


def _mark_failed(tenant_id: str, review_id: str) -> None:
    """Numa transação própria, para sobreviver ao rollback do handler que vai relançar o erro."""
    session = session_factory(admin=True)()
    try:
        apply_tenant(session, tenant_id)
        session.execute(
            update(AiReview)
            .where(AiReview.id == review_id, AiReview.tenant_id == tenant_id)
            .values(status="failed", stop_reason="error", completed_at=datetime.now(timezone.utc))
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def run_month_review(session: Session, tenant_id: str, payload: dict, client: ReviewClient | None = None) -> None:
    operation_id = payload.get("operation_id")
    mark_operation_running(session, tenant_id, operation_id)
    # Sem FOR UPDATE: a falha grava `failed` numa transação própria, que esperaria esta trava.
    # O outbox entrega cada evento a um relay só.
    review = session.scalar(
        select(AiReview).where(AiReview.id == str(payload.get("review_id") or ""), AiReview.tenant_id == tenant_id)
    )
    if review is None or review.status in {"completed", "incomplete"}:
        logger.info("month review skipped tenant=%s operation=%s reason=state", tenant_id, operation_id)
        return
    period = session.scalar(
        select(AccountingPeriod).where(AccountingPeriod.id == review.period_id, AccountingPeriod.tenant_id == tenant_id)
    )
    if period is None:
        logger.info("month review skipped tenant=%s operation=%s reason=scope", tenant_id, operation_id)
        return
    reader = Principal(review.requested_by, tenant_id, frozenset({"viewer"}), review.requested_by, "")
    packet = current_packet(session, reader, period)
    refs = packet_refs(packet)
    system, user = build_review_prompt(packet)
    if client is None:
        client = AnthropicReviewClient(get_settings().claude_api_key, review.model)
    try:
        result = client.review(system=system, user=user)
    except Exception as exc:
        _mark_failed(tenant_id, review.id)
        logger.warning(
            "month review failed tenant=%s operation=%s review=%s error=%s",
            tenant_id,
            operation_id,
            review.id,
            exc.__class__.__name__,
        )
        raise
    points = validate_points(result.answer, refs) if result.answer is not None else []
    incomplete = result.answer is None or result.stop_reason in INCOMPLETE_STOPS
    now = datetime.now(timezone.utc)
    review.status = "incomplete" if incomplete else "completed"
    review.stop_reason = (result.stop_reason or "unknown")[:40]
    review.input_tokens = result.input_tokens
    review.output_tokens = result.output_tokens
    review.input_sha256 = packet_sha256(packet)
    review.completed_at = now
    session.add_all(
        AiReviewFinding(
            id=new_id("aifind"),
            tenant_id=tenant_id,
            review_id=review.id,
            position=index + 1,
            relevance=point.relevance,
            category=point.category,
            title=point.title,
            explanation=point.explanation,
            evidence=point.evidence,
            created_at=now,
        )
        for index, point in enumerate(points)
    )
    if incomplete and operation_id:
        operation = session.scalar(select(Operation).where(Operation.id == operation_id, Operation.tenant_id == tenant_id))
        if operation is not None:
            operation.error_code = INCOMPLETE_WARNING
            operation.updated_at = now
    session.flush()
    logger.info(
        "month review done tenant=%s operation=%s review=%s points=%s stop_reason=%s",
        tenant_id,
        operation_id,
        review.id,
        len(points),
        review.stop_reason,
    )
