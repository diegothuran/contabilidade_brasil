from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from contabil.platform.deps import Ctx, get_context
from contabil.platform.errors import DomainError
from contabil.platform.idempotency import persist, replay_guard
from contabil.platform.principal import ensure_office
from contabil.regulatory.registration import RegistrationInput, get_registration, put_registration
from contabil.regulatory.registry import reinf_natures
from contabil.withholdings.validators import BENEFICIARY_KINDS

router = APIRouter()


class EcdRegistrationBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uf: str = Field(min_length=2, max_length=2)
    municipality_ibge: str = Field(min_length=7, max_length=9)
    registry_kind: str = Field(min_length=1, max_length=20)
    nire: str | None = Field(default=None, max_length=20)
    registry_date: date | None = None
    conversion_date: date | None = None
    special_situation: str | None = Field(default=None, max_length=1)
    book_number: int = Field(ge=1, le=999999)


@router.get("/legal-entities/{legal_entity_id}/ecd-registration")
def get_ecd_registration(legal_entity_id: str, ctx: Ctx = Depends(get_context)) -> dict:
    return get_registration(ctx.session, ctx.principal, legal_entity_id)


@router.put("/legal-entities/{legal_entity_id}/ecd-registration")
def put_ecd_registration(legal_entity_id: str, body: EcdRegistrationBody, request: Request, ctx: Ctx = Depends(replay_guard)):
    saved = put_registration(
        ctx.session,
        ctx.principal,
        legal_entity_id,
        RegistrationInput(
            uf=body.uf,
            municipality_ibge=body.municipality_ibge,
            registry_kind=body.registry_kind,
            nire=body.nire,
            registry_date=body.registry_date,
            conversion_date=body.conversion_date,
            special_situation=body.special_situation,
            book_number=body.book_number,
        ),
    )
    return persist(ctx, request, 200, saved)


@router.get("/regulatory/reinf/natures")
def get_reinf_natures(beneficiary_kind: str | None = None, ctx: Ctx = Depends(get_context)) -> dict:
    """Recorte da Tabela 01 da EFD-Reinf para o select da tela (ADR 032). Sem alíquota."""
    ensure_office(ctx.principal)
    if beneficiary_kind is not None and beneficiary_kind not in BENEFICIARY_KINDS:
        raise DomainError(
            400,
            "Tipo de beneficiário inválido",
            "Use pj ou pf.",
            errors=[{"loc": ["beneficiary_kind"], "msg": "Use pj (pessoa jurídica) ou pf (pessoa física)."}],
        )
    table = reinf_natures()
    return {"version": table.version, "items": [nature.as_dict() for nature in table.items(beneficiary_kind)]}
