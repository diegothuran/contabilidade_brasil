from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from contabil.client_summaries.service import generate_summary_status, get_summary, publish_summary, withdraw_summary
from contabil.ledger.schemas import ReasonBody
from contabil.platform.deps import Ctx, get_context
from contabil.platform.idempotency import persist, replay_guard

router = APIRouter()


@router.post("/periods/{period_id}/client-summary")
def post_client_summary(period_id: str, request: Request, ctx: Ctx = Depends(replay_guard)):
    body, created = generate_summary_status(ctx.session, ctx.principal, period_id)
    return persist(ctx, request, 201 if created else 200, body)


@router.get("/periods/{period_id}/client-summary")
def get_client_summary(period_id: str, ctx: Ctx = Depends(get_context)) -> dict:
    return get_summary(ctx.session, ctx.principal, period_id)


@router.post("/periods/{period_id}/client-summary/publish")
def post_publish(period_id: str, request: Request, ctx: Ctx = Depends(replay_guard)):
    return persist(ctx, request, 200, publish_summary(ctx.session, ctx.principal, period_id))


@router.post("/periods/{period_id}/client-summary/withdraw")
def post_withdraw(period_id: str, body: ReasonBody, request: Request, ctx: Ctx = Depends(replay_guard)):
    return persist(ctx, request, 200, withdraw_summary(ctx.session, ctx.principal, period_id, body.reason))
