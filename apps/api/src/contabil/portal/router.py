from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from contabil.document_requests.service import add_comment, client_document, list_client_requests, receive_content, request_detail
from contabil.documents.service import open_content
from contabil.identity.notices import client_preference, set_client_preference
from contabil.submissions.service import create_submission, list_submissions
from contabil.platform.deps import Ctx, get_context
from contabil.platform.errors import IdempotentReplay
from contabil.platform.idempotency import claim_idempotency, persist, replay_guard

router = APIRouter()


@router.get("/portal/document-requests")
def get_portal_requests(
    status: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50),
    ctx: Ctx = Depends(get_context),
) -> dict:
    return list_client_requests(ctx.session, ctx.principal, status=status, cursor=cursor, limit=limit)


@router.get("/portal/document-requests/{request_id}")
def get_portal_request(request_id: str, ctx: Ctx = Depends(get_context)) -> dict:
    return request_detail(ctx.session, ctx.principal, request_id)


class CommentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1, max_length=1000)


@router.post("/portal/document-requests/{request_id}/comments")
def post_portal_comment(request_id: str, body: CommentBody, request: Request, ctx: Ctx = Depends(replay_guard)):
    return persist(ctx, request, 201, add_comment(ctx.session, ctx.principal, request_id, body.body))


@router.post("/portal/document-requests/{request_id}/content", response_model=None)
async def post_portal_content(
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


@router.get("/portal/documents/{document_id}/content")
def get_portal_document(document_id: str, ctx: Ctx = Depends(get_context)):
    document = client_document(ctx.session, ctx.principal, document_id)
    safe_name = document.file_name.replace('"', "").replace("\\", "_").replace("/", "_")
    return StreamingResponse(
        open_content(document),
        media_type=document.media_type,
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@router.get("/portal/submissions")
def get_portal_submissions(status: str | None = None, ctx: Ctx = Depends(get_context)) -> dict:
    return list_submissions(ctx.session, ctx.principal, status=status or "new,classified,discarded", own_company=True)


@router.post("/portal/submissions", response_model=None)
async def post_portal_submission(
    request: Request,
    file: UploadFile = File(...),
    note: str | None = Form(default=None),
    ctx: Ctx = Depends(get_context),
):
    content = await file.read()
    fingerprint = b"\n".join(
        [
            (file.filename or "arquivo").encode(),
            hashlib.sha256(content).hexdigest().encode(),
            (note or "").encode(),
        ]
    )
    try:
        claim_idempotency(request, ctx, fingerprint)
    except IdempotentReplay as replay:
        return JSONResponse(replay.body, status_code=replay.status_code)
    body = create_submission(
        ctx.session,
        ctx.principal,
        file_name=file.filename or "arquivo",
        media_type=file.content_type or "application/octet-stream",
        content=content,
        note=note,
    )
    return persist(ctx, request, 201, body)


class PreferenceBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notify_client: bool


@router.get("/portal/preferences")
def get_portal_preferences(ctx: Ctx = Depends(get_context)) -> dict:
    return client_preference(ctx.session, ctx.principal)


@router.patch("/portal/preferences")
def patch_portal_preferences(body: PreferenceBody, request: Request, ctx: Ctx = Depends(replay_guard)):
    return persist(ctx, request, 200, set_client_preference(ctx.session, ctx.principal, body.notify_client))
