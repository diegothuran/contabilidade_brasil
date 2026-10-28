from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from contabil.imports.service import (
    batch_dict,
    create_batch,
    get_operation,
    get_report,
    list_batches,
    list_operations,
    list_rows,
    request_publish,
    template_csv,
)
from contabil.imports.service import _batch_or_404
from contabil.platform.deps import Ctx, get_context
from contabil.platform.idempotency import persist, replay_guard

router = APIRouter()


class FileIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1, max_length=160)
    kind: str = Field(min_length=1, max_length=40)


class BatchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    legal_entity_id: str = Field(min_length=1, max_length=160)
    source_system: str = Field(min_length=1, max_length=160)
    mode: Literal["dry_run", "publish", "rollback"]
    period_id: str | None = Field(default=None, max_length=80)
    files: list[FileIn] = Field(min_length=1, max_length=20)


@router.get("/import-batches/templates/{kind}")
def get_template(kind: str, ctx: Ctx = Depends(get_context)) -> Response:
    del ctx
    return Response(template_csv(kind), media_type="text/csv; charset=utf-8")


@router.post("/import-batches", status_code=202, response_model=None)
def post_batch(body: BatchCreate, request: Request, ctx: Ctx = Depends(replay_guard)):
    operation = create_batch(ctx.session, ctx.principal, body, request.state.idempotency_key)
    return persist(ctx, request, 202, operation)


@router.get("/import-batches")
def get_batches(
    legal_entity_id: str,
    cursor: str | None = None,
    limit: int = Query(default=50),
    ctx: Ctx = Depends(get_context),
) -> dict:
    return list_batches(ctx.session, ctx.principal, legal_entity_id=legal_entity_id, cursor=cursor, limit=limit)


@router.get("/import-batches/{batch_id}")
def get_batch(batch_id: str, ctx: Ctx = Depends(get_context)) -> dict:
    return batch_dict(ctx.session, _batch_or_404(ctx.session, ctx.principal.tenant_id, batch_id))


@router.get("/import-batches/{batch_id}/rows")
def get_rows(batch_id: str, status: str | None = None, ctx: Ctx = Depends(get_context)) -> dict:
    return list_rows(ctx.session, ctx.principal, batch_id, status)


@router.get("/import-batches/{batch_id}/report")
def get_batch_report(batch_id: str, ctx: Ctx = Depends(get_context)) -> dict:
    return get_report(ctx.session, ctx.principal, batch_id)


@router.post("/import-batches/{batch_id}/publish", status_code=202, response_model=None)
def post_publish(batch_id: str, request: Request, ctx: Ctx = Depends(replay_guard)):
    operation = request_publish(ctx.session, ctx.principal, batch_id)
    return persist(ctx, request, 202, operation)


@router.get("/operations")
def get_operations(
    kind: str | None = None,
    status: str | None = None,
    correlation_id: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50),
    ctx: Ctx = Depends(get_context),
) -> dict:
    return list_operations(
        ctx.session,
        ctx.principal,
        kind=kind,
        status=status,
        correlation=correlation_id,
        cursor=cursor,
        limit=limit,
    )


@router.get("/operations/{operation_id}")
def get_one_operation(operation_id: str, ctx: Ctx = Depends(get_context)) -> dict:
    return get_operation(ctx.session, ctx.principal, operation_id)
