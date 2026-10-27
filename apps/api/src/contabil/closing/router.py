from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from contabil.closing.service import close_run, decide_item, evidence_package, get_close_run, open_close_run
from contabil.platform.deps import Ctx, get_context
from contabil.platform.idempotency import persist, replay_guard

router = APIRouter()


class ItemDecisionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["completed", "not_applicable"]
    reason: str | None = None


@router.post("/periods/{period_id}/close-runs")
def post_close_run(period_id: str, request: Request, ctx: Ctx = Depends(replay_guard)):
    created, payload = open_close_run(ctx.session, ctx.principal, period_id)
    return persist(ctx, request, 201 if created else 200, payload)


@router.get("/close-runs/{close_run_id}")
def get_run(close_run_id: str, ctx: Ctx = Depends(get_context)) -> dict:
    return get_close_run(ctx.session, ctx.principal, close_run_id)


@router.post("/close-runs/{close_run_id}/items/{item_id}")
def post_item(
    close_run_id: str,
    item_id: str,
    body: ItemDecisionBody,
    request: Request,
    ctx: Ctx = Depends(replay_guard),
):
    payload = decide_item(
        ctx.session,
        ctx.principal,
        close_run_id,
        item_id,
        status=body.status,
        reason=body.reason,
    )
    return persist(ctx, request, 200, payload)


@router.post("/close-runs/{close_run_id}/close")
def post_close(close_run_id: str, request: Request, ctx: Ctx = Depends(replay_guard)):
    payload = close_run(ctx.session, ctx.principal, close_run_id)
    return persist(ctx, request, 200, payload)


@router.get("/close-runs/{close_run_id}/evidence-package")
def get_package(close_run_id: str, ctx: Ctx = Depends(get_context)) -> JSONResponse:
    payload = evidence_package(ctx.session, ctx.principal, close_run_id)
    ctx.session.commit()
    return JSONResponse(
        payload,
        headers={"Content-Disposition": f'attachment; filename="pacote-{close_run_id}.json"'},
    )
