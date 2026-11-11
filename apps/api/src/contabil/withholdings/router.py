from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from contabil.platform.deps import Ctx, get_context
from contabil.platform.idempotency import persist, replay_guard
from contabil.withholdings.service import create_payment, delete_payment, list_payments
from contabil.withholdings.validators import PaymentInput

router = APIRouter()


class PaymentCreate(BaseModel):
    """Os campos chegam como texto: a conferência por campo responde 400 com errors[].loc (ADR 032)."""

    model_config = ConfigDict(extra="forbid")

    period_id: str | None = Field(default=None, max_length=160)
    payment_date: str | None = Field(default=None, max_length=40)
    beneficiary_kind: str | None = Field(default=None, max_length=20)
    beneficiary_document: str | None = Field(default=None, max_length=40)
    beneficiary_name: str | None = Field(default=None, max_length=1000)
    nature_code: str | None = Field(default=None, max_length=20)
    gross_amount: str | None = Field(default=None, max_length=40)
    ir_base: str | None = Field(default=None, max_length=40)
    ir_amount: str | None = Field(default=None, max_length=40)
    csrf_base: str | None = Field(default=None, max_length=40)
    csrf_amount: str | None = Field(default=None, max_length=40)
    description: str | None = Field(default=None, max_length=2000)


@router.get("/legal-entities/{legal_entity_id}/withholding-payments")
def get_payments(legal_entity_id: str, period_id: str | None = None, ctx: Ctx = Depends(get_context)) -> dict:
    return list_payments(ctx.session, ctx.principal, legal_entity_id, period_id)


@router.post("/legal-entities/{legal_entity_id}/withholding-payments", status_code=201)
def post_payment(legal_entity_id: str, body: PaymentCreate, request: Request, ctx: Ctx = Depends(replay_guard)):
    created = create_payment(
        ctx.session,
        ctx.principal,
        legal_entity_id,
        body.period_id,
        PaymentInput(
            beneficiary_kind=body.beneficiary_kind,
            beneficiary_document=body.beneficiary_document,
            beneficiary_name=body.beneficiary_name,
            nature_code=body.nature_code,
            payment_date=body.payment_date,
            gross_amount=body.gross_amount,
            ir_base=body.ir_base,
            ir_amount=body.ir_amount,
            csrf_base=body.csrf_base,
            csrf_amount=body.csrf_amount,
            description=body.description,
        ),
    )
    return persist(ctx, request, 201, created)


@router.delete("/legal-entities/{legal_entity_id}/withholding-payments/{payment_id}", status_code=204)
def remove_payment(legal_entity_id: str, payment_id: str, request: Request, ctx: Ctx = Depends(replay_guard)):
    delete_payment(ctx.session, ctx.principal, legal_entity_id, payment_id)
    return persist(ctx, request, 204, {})
