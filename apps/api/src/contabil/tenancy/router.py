from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from contabil.platform.deps import Ctx, get_context
from contabil.platform.idempotency import persist, replay_guard
from contabil.platform.principal import ensure_role
from contabil.tables import LegalEntity
from contabil.tenancy.service import create_legal_entity, entity_dict

router = APIRouter()


class LegalEntityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    cnpj: str = Field(min_length=1, max_length=32)
    fiscal_year: int = Field(ge=2000, le=2100)


@router.get("/me")
def me(ctx: Ctx = Depends(get_context)) -> dict:
    return {
        "user_id": ctx.principal.user_id,
        "display_name": ctx.principal.display_name,
        "tenant_id": ctx.principal.tenant_id,
        "tenant_name": ctx.principal.tenant_name,
        "roles": sorted(ctx.principal.roles),
    }


@router.post("/legal-entities", status_code=201)
def post_legal_entity(body: LegalEntityCreate, request: Request, ctx: Ctx = Depends(replay_guard)):
    ensure_role(ctx.principal, "admin")
    created = create_legal_entity(
        ctx.session,
        ctx.principal,
        name=body.name,
        cnpj=body.cnpj,
        fiscal_year=body.fiscal_year,
    )
    return persist(ctx, request, 201, created)


@router.get("/legal-entities")
def legal_entities(ctx: Ctx = Depends(get_context)) -> dict:
    rows = ctx.session.scalars(select(LegalEntity).where(LegalEntity.tenant_id == ctx.principal.tenant_id).order_by(LegalEntity.name)).all()
    return {"items": [entity_dict(row) for row in rows]}
