from __future__ import annotations

import hashlib
from datetime import date

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from contabil.document_requests.service import (
    add_comment,
    cancel_request,
    confirm_request,
    create_request,
    list_comments,
    list_queue,
    list_requests,
    receive_content,
    request_detail,
    return_request,
)
from contabil.platform.deps import Ctx, get_context
from contabil.platform.errors import IdempotentReplay
from contabil.platform.idempotency import claim_idempotency, persist, replay_guard

router = APIRouter()


@router.get("/document-requests/queue")
def get_queue(
    status: str | None = None,
    due_before: date | None = None,
    year: int | None = None,
    month: int | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50),
    ctx: Ctx = Depends(get_context),
) -> dict:
    return list_queue(
        ctx.session,
        ctx.principal,
        status=status,
        due_before=due_before,
        year=year,
        month=month,
        cursor=cursor,
        limit=limit,
    )


class RequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    legal_entity_id: str = Field(min_length=1, max_length=160)
    period_id: str = Field(min_length=1, max_length=80)
    document_type: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=200)
    due_on: date


class CancelBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=2000)


@router.post("/document-requests")
def post_request(body: RequestCreate, request: Request, ctx: Ctx = Depends(replay_guard)):
    created = create_request(
        ctx.session,
        ctx.principal,
        legal_entity_id=body.legal_entity_id,
        period_id=body.period_id,
        document_type=body.document_type,
        title=body.title,
        due_on=body.due_on,
    )
    return persist(ctx, request, 201, created)


@router.get("/document-requests")
def get_requests(
    legal_entity_id: str,
    period_id: str,
    cursor: str | None = None,
    limit: int = Query(default=50),
    ctx: Ctx = Depends(get_context),
) -> dict:
    return list_requests(
        ctx.session,
        ctx.principal,
        legal_entity_id=legal_entity_id,
        period_id=period_id,
        cursor=cursor,
        limit=limit,
    )


@router.get("/document-requests/{request_id}")
def get_request(request_id: str, ctx: Ctx = Depends(get_context)) -> dict:
    return request_detail(ctx.session, ctx.principal, request_id)


@router.post("/document-requests/{request_id}/return")
def post_return(request_id: str, body: CancelBody, request: Request, ctx: Ctx = Depends(replay_guard)):
    return persist(ctx, request, 200, return_request(ctx.session, ctx.principal, request_id, body.reason))


@router.get("/document-requests/{request_id}/comments")
def get_comments(request_id: str, ctx: Ctx = Depends(get_context)) -> dict:
    return list_comments(ctx.session, ctx.principal, request_id)


class CommentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1, max_length=1000)


@router.post("/document-requests/{request_id}/comments")
def post_comment(request_id: str, body: CommentBody, request: Request, ctx: Ctx = Depends(replay_guard)):
    return persist(ctx, request, 201, add_comment(ctx.session, ctx.principal, request_id, body.body))


@router.post("/document-requests/{request_id}/content", response_model=None)
async def post_content(
    request_id: str,
    request: Request,
    file: UploadFile = File(...),
    ctx: Ctx = Depends(get_context),
):
    content = await file.read()
    fingerprint = b"\n".join(
        [
            request_id.encode(),
            (file.filename or "arquivo").encode(),
            hashlib.sha256(content).hexdigest().encode(),
        ]
    )
    try:
        claim_idempotency(request, ctx, fingerprint)
    except IdempotentReplay as replay:
        return JSONResponse(replay.body, status_code=replay.status_code)
    body = receive_content(
        ctx.session,
        ctx.principal,
        request_id,
        file_name=file.filename or "arquivo",
        media_type=file.content_type or "application/octet-stream",
        content=content,
    )
    return persist(ctx, request, 200, body)


@router.post("/document-requests/{request_id}/confirm")
def post_confirm(request_id: str, request: Request, ctx: Ctx = Depends(replay_guard)):
    return persist(ctx, request, 200, confirm_request(ctx.session, ctx.principal, request_id))


@router.post("/document-requests/{request_id}/cancel")
def post_cancel(request_id: str, body: CancelBody, request: Request, ctx: Ctx = Depends(replay_guard)):
    return persist(ctx, request, 200, cancel_request(ctx.session, ctx.principal, request_id, body.reason))
