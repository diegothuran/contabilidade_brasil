from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from contabil.ledger.schemas import ReasonBody
from contabil.platform.deps import Ctx, get_context
from contabil.platform.idempotency import persist, replay_guard
from contabil.reconciliation.service import (
    approve_case,
    bank_account_summary,
    create_bank_account,
    create_journal_from_case,
    create_statement,
    get_case,
    get_statement,
    ignore_case,
    list_bank_accounts,
    list_cases,
    list_statements,
    reject_case,
    resuggest_case,
    reverse_case,
)

router = APIRouter()


class BankAccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    legal_entity_id: str = Field(min_length=1, max_length=160)
    account_id: str = Field(min_length=1, max_length=160)
    name: str = Field(min_length=1, max_length=200)
    bank_code: str = Field(min_length=1, max_length=8)
    branch: str = Field(min_length=1, max_length=20)
    account_number_masked: str = Field(pattern=r"^[0-9]{4}$")


class StatementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1, max_length=160)


class ApproveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(min_length=1, max_length=200)


class JournalFromCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    counterpart_account_id: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    cost_center_id: str | None = Field(default=None, max_length=160)


@router.post("/bank-accounts", status_code=201, response_model=None)
def post_bank_account(body: BankAccountCreate, request: Request, ctx: Ctx = Depends(replay_guard)):
    return persist(ctx, request, 201, create_bank_account(ctx.session, ctx.principal, body))


@router.get("/bank-accounts")
def get_bank_accounts(legal_entity_id: str = Query(min_length=1), ctx: Ctx = Depends(get_context)) -> dict:
    return list_bank_accounts(ctx.session, ctx.principal, legal_entity_id)


@router.get("/bank-accounts/{bank_account_id}/summary")
def get_bank_summary(bank_account_id: str, period_id: str = Query(min_length=1), ctx: Ctx = Depends(get_context)) -> dict:
    return bank_account_summary(ctx.session, ctx.principal, bank_account_id, period_id)


@router.post("/bank-accounts/{bank_account_id}/statements", status_code=202, response_model=None)
def post_statement(bank_account_id: str, body: StatementCreate, request: Request, ctx: Ctx = Depends(replay_guard)):
    return persist(ctx, request, 202, create_statement(ctx.session, ctx.principal, bank_account_id, body.document_id))


@router.get("/bank-accounts/{bank_account_id}/statements")
def get_statements(bank_account_id: str, ctx: Ctx = Depends(get_context)) -> dict:
    return list_statements(ctx.session, ctx.principal, bank_account_id)


@router.get("/bank-statements/{statement_id}")
def get_one_statement(statement_id: str, ctx: Ctx = Depends(get_context)) -> dict:
    return get_statement(ctx.session, ctx.principal, statement_id)


@router.get("/reconciliation-cases")
def get_cases(
    bank_account_id: str = Query(min_length=1),
    status: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    ctx: Ctx = Depends(get_context),
) -> dict:
    return list_cases(
        ctx.session,
        ctx.principal,
        bank_account_id=bank_account_id,
        status=status,
        cursor=cursor,
        limit=limit,
    )


@router.get("/reconciliation-cases/{case_id}")
def get_one_case(case_id: str, ctx: Ctx = Depends(get_context)) -> dict:
    return get_case(ctx.session, ctx.principal, case_id)


@router.post("/reconciliation-cases/{case_id}/approve", response_model=None)
def post_approve(case_id: str, body: ApproveBody, request: Request, ctx: Ctx = Depends(replay_guard)):
    return persist(ctx, request, 200, approve_case(ctx.session, ctx.principal, case_id, body.candidate_id))


@router.post("/reconciliation-cases/{case_id}/reject", response_model=None)
def post_reject(case_id: str, body: ReasonBody, request: Request, ctx: Ctx = Depends(replay_guard)):
    return persist(ctx, request, 200, reject_case(ctx.session, ctx.principal, case_id, body.reason))


@router.post("/reconciliation-cases/{case_id}/ignore", response_model=None)
def post_ignore(case_id: str, body: ReasonBody, request: Request, ctx: Ctx = Depends(replay_guard)):
    return persist(ctx, request, 200, ignore_case(ctx.session, ctx.principal, case_id, body.reason))


@router.post("/reconciliation-cases/{case_id}/reverse", response_model=None)
def post_reverse(case_id: str, body: ReasonBody, request: Request, ctx: Ctx = Depends(replay_guard)):
    return persist(ctx, request, 200, reverse_case(ctx.session, ctx.principal, case_id, body.reason))


@router.post("/reconciliation-cases/{case_id}/resuggest", response_model=None)
def post_resuggest(case_id: str, request: Request, ctx: Ctx = Depends(replay_guard)):
    return persist(ctx, request, 200, resuggest_case(ctx.session, ctx.principal, case_id))


@router.post("/reconciliation-cases/{case_id}/journal", status_code=201, response_model=None)
def post_journal_from_case(case_id: str, body: JournalFromCase, request: Request, ctx: Ctx = Depends(replay_guard)):
    return persist(ctx, request, 201, create_journal_from_case(ctx.session, ctx.principal, case_id, body))
