from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from contabil.document_requests.service import client_document, list_client_requests, receive_content
from contabil.documents.service import open_content
from contabil.platform.deps import Ctx, get_context
from contabil.platform.errors import IdempotentReplay
from contabil.platform.idempotency import claim_idempotency, persist

router = APIRouter()


@router.get("/portal/document-requests")
def get_portal_requests(ctx: Ctx = Depends(get_context)) -> dict:
    return list_client_requests(ctx.session, ctx.principal)


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
