from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from contabil.platform.deps import Ctx, get_context
from contabil.platform.idempotency import persist, replay_guard
from contabil.platform.principal import ensure_office, ensure_role
from contabil.signatories.editing import entity_signatories, my_registration, save_entity_signatories, save_registration

router = APIRouter()


class RegistrationBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cpf: str = Field(min_length=1, max_length=14)
    crc_uf: str = Field(min_length=1, max_length=2)
    crc_number: str = Field(min_length=1, max_length=20)
    crc_category: str = Field(min_length=1, max_length=20)
    regularity_number: str | None = Field(default=None, max_length=40)
    regularity_valid_until: date | None = None


class SignatoriesBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accountant_user_id: str | None = Field(default=None, max_length=160)
    legal_rep_name: str | None = Field(default=None, max_length=200)
    legal_rep_cpf: str | None = Field(default=None, max_length=14)
    legal_rep_role: str | None = Field(default=None, max_length=40)


@router.get("/me/professional-registration")
def get_registration(ctx: Ctx = Depends(get_context)) -> dict:
    ensure_office(ctx.principal)
    return my_registration(ctx.session, ctx.principal)


@router.put("/me/professional-registration")
def put_registration(body: RegistrationBody, request: Request, ctx: Ctx = Depends(replay_guard)):
    ensure_office(ctx.principal)
    saved = save_registration(
        ctx.session,
        ctx.principal,
        cpf=body.cpf,
        crc_uf=body.crc_uf,
        crc_number=body.crc_number,
        crc_category=body.crc_category,
        regularity_number=body.regularity_number,
        regularity_valid_until=body.regularity_valid_until,
    )
    return persist(ctx, request, 200, saved)


@router.get("/legal-entities/{legal_entity_id}/signatories")
def get_signatories(legal_entity_id: str, ctx: Ctx = Depends(get_context)) -> dict:
    ensure_office(ctx.principal)
    return entity_signatories(ctx.session, ctx.principal, legal_entity_id)


@router.put("/legal-entities/{legal_entity_id}/signatories")
def put_signatories(legal_entity_id: str, body: SignatoriesBody, request: Request, ctx: Ctx = Depends(replay_guard)):
    ensure_office(ctx.principal)
    ensure_role(ctx.principal, "admin")
    saved = save_entity_signatories(
        ctx.session,
        ctx.principal,
        legal_entity_id,
        accountant_user_id=body.accountant_user_id,
        legal_rep_name=body.legal_rep_name,
        legal_rep_cpf=body.legal_rep_cpf,
        legal_rep_role=body.legal_rep_role,
    )
    return persist(ctx, request, 200, saved)
