from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from contabil.identity.directory import UserDirectory, get_user_directory
from contabil.platform.deps import Ctx, get_context
from contabil.platform.idempotency import persist, replay_guard
from contabil.platform.principal import ensure_role
from contabil.platform.auth import bind_user, offices_visible
from contabil.tables import LegalEntity, Membership, Tenant
from contabil.tenancy.service import create_legal_entity, entity_dict, invite_user, list_users

router = APIRouter()


class UserInvite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=200)
    roles: list[str] = Field(min_length=1, max_length=4)


class LegalEntityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    cnpj: str = Field(min_length=1, max_length=32)
    fiscal_year: int = Field(ge=2000, le=2100)


@router.get("/users")
def users(ctx: Ctx = Depends(get_context)) -> dict:
    ensure_role(ctx.principal, "admin")
    return list_users(ctx.session, ctx.principal)


@router.post("/users", status_code=201)
def post_user(
    body: UserInvite,
    request: Request,
    ctx: Ctx = Depends(replay_guard),
    directory: UserDirectory = Depends(get_user_directory),
):
    ensure_role(ctx.principal, "admin")
    created = invite_user(
        ctx.session,
        ctx.principal,
        directory,
        username=body.username,
        display_name=body.display_name,
        email=body.email,
        roles=body.roles,
    )
    return persist(ctx, request, 201, created)


@router.get("/me")
def me(ctx: Ctx = Depends(get_context)) -> dict:
    bind_user(ctx.session, ctx.principal.user_id)
    home_id = ctx.principal.home_tenant_id or ctx.principal.tenant_id
    home_roles = ctx.session.scalar(
        select(Membership.roles).where(Membership.user_id == ctx.principal.user_id, Membership.tenant_id == home_id)
    )
    rows = ctx.session.execute(
        select(Tenant.id, Tenant.name)
        .join(Membership, Membership.tenant_id == Tenant.id)
        .where(Membership.user_id == ctx.principal.user_id)
        .order_by(Tenant.name)
    ).all()
    offices = offices_visible("admin" in set(home_roles or []), ctx.principal.tenant_id, [(tenant_id, name) for tenant_id, name in rows])
    return {
        "user_id": ctx.principal.user_id,
        "display_name": ctx.principal.display_name,
        "tenant_id": ctx.principal.tenant_id,
        "tenant_name": ctx.principal.tenant_name,
        "roles": sorted(ctx.principal.roles),
        "offices": [{"tenant_id": tenant_id, "tenant_name": name} for tenant_id, name in offices],
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
