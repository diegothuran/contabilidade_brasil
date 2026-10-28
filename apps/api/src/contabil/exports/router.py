from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from contabil.exports.service import create_export, get_export
from contabil.platform.deps import Ctx, get_context
from contabil.platform.idempotency import persist, replay_guard

router = APIRouter()


class ExportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period_id: str = Field(min_length=1, max_length=80)
    kind: str = Field(min_length=1, max_length=40)


@router.post("/legal-entities/{legal_entity_id}/exports", status_code=202)
def post_export(legal_entity_id: str, body: ExportCreate, request: Request, ctx: Ctx = Depends(replay_guard)):
    created = create_export(
        ctx.session,
        ctx.principal,
        legal_entity_id=legal_entity_id,
        period_id=body.period_id,
        kind=body.kind,
    )
    return persist(ctx, request, 202, created)


@router.get("/exports/{export_id}")
def get_one_export(export_id: str, ctx: Ctx = Depends(get_context)) -> dict:
    return get_export(ctx.session, ctx.principal, export_id)
