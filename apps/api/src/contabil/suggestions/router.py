from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from contabil.platform.deps import Ctx
from contabil.platform.idempotency import persist, replay_guard
from contabil.suggestions.service import request_counterpart_suggestions

router = APIRouter()


class CounterpartSuggestionsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period_id: str = Field(min_length=1, max_length=160)


@router.post("/bank-accounts/{bank_account_id}/counterpart-suggestions", status_code=202, response_model=None)
def post_counterpart_suggestions(
    bank_account_id: str,
    body: CounterpartSuggestionsRequest,
    request: Request,
    ctx: Ctx = Depends(replay_guard),
):
    created = request_counterpart_suggestions(ctx.session, ctx.principal, bank_account_id, body.period_id)
    return persist(ctx, request, 202, created)
