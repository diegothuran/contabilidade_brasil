from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import StreamingResponse

from contabil.documents.service import document_dict, get_document, list_documents, open_content, store_document
from contabil.platform.deps import Ctx, get_context
from contabil.platform.errors import IdempotentReplay
from contabil.platform.idempotency import claim_idempotency, persist

router = APIRouter()


@router.post("/documents", response_model=None)
async def post_document(
    request: Request,
    file: UploadFile = File(...),
    document_type: str = Form(...),
    legal_entity_id: str | None = Form(None),
    competence: str | None = Form(None),
    source_ref: str | None = Form(None),
    ctx: Ctx = Depends(get_context),
):
    content = await file.read()
    fingerprint = "\n".join(
        [
            document_type,
            legal_entity_id or "",
            competence or "",
            source_ref or "",
            hashlib.sha256(content).hexdigest(),
        ]
    ).encode()
    try:
        claim_idempotency(request, ctx, fingerprint)
    except IdempotentReplay as replay:
        from fastapi.responses import JSONResponse

        return JSONResponse(replay.body, status_code=replay.status_code)
    body, status_code = store_document(
        ctx.session,
        ctx.principal,
        file_name=file.filename or "arquivo",
        media_type=file.content_type or "application/octet-stream",
        content=content,
        document_type=document_type,
        legal_entity_id=legal_entity_id or None,
        competence=competence or None,
        source_ref=source_ref or None,
    )
    return persist(ctx, request, status_code, body)


@router.get("/documents")
def get_documents(
    legal_entity_id: str | None = None,
    document_type: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50),
    ctx: Ctx = Depends(get_context),
) -> dict:
    return list_documents(
        ctx.session,
        ctx.principal,
        legal_entity_id=legal_entity_id,
        document_type=document_type,
        cursor=cursor,
        limit=limit,
    )


@router.get("/documents/{document_id}")
def get_one_document(document_id: str, ctx: Ctx = Depends(get_context)) -> dict:
    return document_dict(get_document(ctx.session, ctx.principal, document_id))


@router.get("/documents/{document_id}/content")
def get_document_content(document_id: str, ctx: Ctx = Depends(get_context)):
    document = get_document(ctx.session, ctx.principal, document_id)
    safe_name = document.file_name.replace('"', "").replace("\\", "_").replace("/", "_")
    return StreamingResponse(
        open_content(document),
        media_type=document.media_type,
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )
