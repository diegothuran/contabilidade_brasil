from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from contabil.platform.deps import Ctx, get_context
from contabil.platform.idempotency import persist, replay_guard
from contabil.submissions.service import classify_submission, discard_submission, list_submissions

router = APIRouter()


@router.get("/client-submissions")
def get_submissions(status: str | None = None, ctx: Ctx = Depends(get_context)) -> dict:
    return list_submissions(ctx.session, ctx.principal, status=status, own_company=False)


class ClassifyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period_id: str = Field(min_length=1, max_length=80)
    document_type: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=200)
    due_on: date


@router.post("/client-submissions/{submission_id}/classify")
def post_classify(submission_id: str, body: ClassifyBody, request: Request, ctx: Ctx = Depends(replay_guard)):
    return persist(
        ctx,
        request,
        200,
        classify_submission(
            ctx.session,
            ctx.principal,
            submission_id,
            period_id=body.period_id,
            document_type=body.document_type,
            title=body.title,
            due_on=body.due_on,
        ),
    )


class DiscardBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=2000)


@router.post("/client-submissions/{submission_id}/discard")
def post_discard(submission_id: str, body: DiscardBody, request: Request, ctx: Ctx = Depends(replay_guard)):
    return persist(ctx, request, 200, discard_submission(ctx.session, ctx.principal, submission_id, body.reason))
