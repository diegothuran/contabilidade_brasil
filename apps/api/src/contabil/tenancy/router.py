from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select

from contabil.platform.deps import Ctx, get_context
from contabil.tables import LegalEntity
from contabil.tenancy.service import entity_dict

router = APIRouter()


@router.get("/me")
def me(ctx: Ctx = Depends(get_context)) -> dict:
    return {
        "user_id": ctx.principal.user_id,
        "display_name": ctx.principal.display_name,
        "tenant_id": ctx.principal.tenant_id,
        "tenant_name": ctx.principal.tenant_name,
        "roles": sorted(ctx.principal.roles),
    }


@router.get("/legal-entities")
def legal_entities(ctx: Ctx = Depends(get_context)) -> dict:
    rows = ctx.session.scalars(select(LegalEntity).where(LegalEntity.tenant_id == ctx.principal.tenant_id).order_by(LegalEntity.name)).all()
    return {"items": [entity_dict(row) for row in rows]}
