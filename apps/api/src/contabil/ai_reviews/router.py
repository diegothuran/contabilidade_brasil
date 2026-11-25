from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from contabil.ai_reviews.service import decide_finding, list_reviews, request_review
from contabil.platform.deps import Ctx, get_context
from contabil.platform.idempotency import persist, replay_guard

router = APIRouter()


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["procede", "nao_procede"]
    note: str | None = Field(default=None, max_length=500)


@router.post("/periods/{period_id}/ai-reviews", status_code=202, response_model=None)
def post_ai_review(period_id: str, request: Request, ctx: Ctx = Depends(replay_guard)):
    created = request_review(ctx.session, ctx.principal, period_id)
    return persist(ctx, request, 202, created)


@router.get("/periods/{period_id}/ai-reviews")
def get_ai_reviews(period_id: str, ctx: Ctx = Depends(get_context)) -> dict:
    return list_reviews(ctx.session, ctx.principal, period_id)


@router.post("/ai-review-findings/{finding_id}/decisions", status_code=201, response_model=None)
def post_finding_decision(finding_id: str, body: DecisionRequest, request: Request, ctx: Ctx = Depends(replay_guard)):
    created = decide_finding(ctx.session, ctx.principal, finding_id, body.decision, body.note)
    return persist(ctx, request, 201, created)
