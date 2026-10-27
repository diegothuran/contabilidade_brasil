from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from contabil.ledger.schemas import ReasonBody
from sqlalchemy import select

from contabil.closing.service import latest_runs
from contabil.periods.service import (
    approve_reopen,
    close_period,
    list_periods,
    period_dict,
    reopen_dict,
    request_reopen,
)
from contabil.tables import ReopenRequest
from contabil.platform.deps import Ctx, get_context
from contabil.platform.idempotency import persist, replay_guard
from contabil.tenancy.service import require_entity

router = APIRouter()


@router.get("/legal-entities/{legal_entity_id}/periods")
def get_periods(legal_entity_id: str, ctx: Ctx = Depends(get_context)) -> dict:
    require_entity(ctx.session, ctx.principal.tenant_id, legal_entity_id)
    periods = list_periods(ctx.session, ctx.principal.tenant_id, legal_entity_id)
    pending = {
        row.period_id: row.id
        for row in ctx.session.scalars(
            select(ReopenRequest).where(ReopenRequest.tenant_id == ctx.principal.tenant_id, ReopenRequest.status == "pending")
        ).all()
    }
    runs = latest_runs(ctx.session, ctx.principal.tenant_id, [period.id for period in periods])
    items = []
    for period in periods:
        payload = period_dict(period)
        payload["pending_reopen_request_id"] = pending.get(period.id)
        run = runs.get(period.id)
        payload["close_run_id"] = run.id if run is not None else None
        payload["close_run_status"] = run.status if run is not None else None
        payload["close_run_number"] = run.run_number if run is not None else None
        items.append(payload)
    return {"items": items}


@router.post("/periods/{period_id}/close")
def post_close(period_id: str, request: Request, ctx: Ctx = Depends(replay_guard)):
    period = close_period(ctx.session, ctx.principal, period_id)
    return persist(ctx, request, 200, period_dict(period))


@router.post("/periods/{period_id}/reopen-requests", status_code=201)
def post_reopen(period_id: str, body: ReasonBody, request: Request, ctx: Ctx = Depends(replay_guard)):
    reopen = request_reopen(ctx.session, ctx.principal, period_id, body.reason)
    return persist(ctx, request, 201, reopen_dict(reopen))


@router.post("/reopen-requests/{request_id}/approve")
def post_approve_reopen(request_id: str, request: Request, ctx: Ctx = Depends(replay_guard)):
    period = approve_reopen(ctx.session, ctx.principal, request_id)
    return persist(ctx, request, 200, period_dict(period))
