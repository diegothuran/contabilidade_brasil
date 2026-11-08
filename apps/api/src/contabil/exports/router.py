from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from contabil.documents.service import open_content
from contabil.exports.service import create_export, export_file, get_export
from contabil.platform.deps import Ctx, get_context
from contabil.platform.idempotency import persist, replay_guard

router = APIRouter()


class ExportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period_id: str | None = Field(default=None, min_length=1, max_length=80)
    kind: str = Field(min_length=1, max_length=40)
    fiscal_year: int | None = Field(default=None, ge=2000, le=2100)


@router.post("/legal-entities/{legal_entity_id}/exports", status_code=202)
def post_export(legal_entity_id: str, body: ExportCreate, request: Request, ctx: Ctx = Depends(replay_guard)):
    created = create_export(
        ctx.session,
        ctx.principal,
        legal_entity_id=legal_entity_id,
        period_id=body.period_id,
        kind=body.kind,
        fiscal_year=body.fiscal_year,
    )
    return persist(ctx, request, 202, created)


@router.get("/exports/{export_id}")
def get_one_export(export_id: str, ctx: Ctx = Depends(get_context)) -> dict:
    return get_export(ctx.session, ctx.principal, export_id)


@router.get("/exports/{export_id}/file")
def get_export_file(export_id: str, ctx: Ctx = Depends(get_context)):
    document, file_name = export_file(ctx.session, ctx.principal, export_id)
    safe_name = file_name.replace('"', "").replace("\\", "_").replace("/", "_")
    return StreamingResponse(
        open_content(document),
        media_type=document.media_type,
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )
