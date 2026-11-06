from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, Response

from contabil.ledger.schemas import JournalCreate, ReasonBody, YearEndClosingCreate
from contabil.ledger.service import (
    account_lines,
    account_lines_csv_export,
    approve_journal,
    create_journal,
    get_journal,
    list_journals,
    publish_journal,
    reject_journal,
    reverse_journal,
    submit_journal,
    trial_balance,
    trial_balance_csv_export,
)
from contabil.ledger.statements import balance_sheet, balance_sheet_csv_export, income_statement, income_statement_csv_export
from contabil.ledger.year_end import build_closing_draft
from contabil.platform.deps import Ctx, get_context
from contabil.platform.idempotency import persist, replay_guard

router = APIRouter()


@router.post("/journals", status_code=201)
def post_journal(body: JournalCreate, request: Request, ctx: Ctx = Depends(replay_guard)):
    return persist(ctx, request, 201, create_journal(ctx.session, ctx.principal, body))


@router.get("/journals")
def get_journals(
    legal_entity_id: str = Query(min_length=1),
    period_id: str | None = None,
    status: str | None = None,
    reverses_journal_id: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    ctx: Ctx = Depends(get_context),
) -> dict:
    return list_journals(
        ctx.session,
        ctx.principal,
        legal_entity_id=legal_entity_id,
        period_id=period_id,
        status=status,
        reverses_journal_id=reverses_journal_id,
        cursor=cursor,
        limit=limit,
    )


@router.get("/journals/{journal_id}")
def get_one_journal(journal_id: str, ctx: Ctx = Depends(get_context)) -> dict:
    return get_journal(ctx.session, ctx.principal, journal_id)


@router.post("/journals/{journal_id}/submit")
def post_submit(journal_id: str, request: Request, ctx: Ctx = Depends(replay_guard)):
    return persist(ctx, request, 200, submit_journal(ctx.session, ctx.principal, journal_id))


@router.post("/journals/{journal_id}/approve")
def post_approve(journal_id: str, request: Request, ctx: Ctx = Depends(replay_guard)):
    return persist(ctx, request, 200, approve_journal(ctx.session, ctx.principal, journal_id))


@router.post("/journals/{journal_id}/reject")
def post_reject(journal_id: str, body: ReasonBody, request: Request, ctx: Ctx = Depends(replay_guard)):
    return persist(ctx, request, 200, reject_journal(ctx.session, ctx.principal, journal_id, body.reason))


@router.post("/journals/{journal_id}/publish")
def post_publish(journal_id: str, request: Request, ctx: Ctx = Depends(replay_guard)):
    return persist(ctx, request, 200, publish_journal(ctx.session, ctx.principal, journal_id))


@router.post("/journals/{journal_id}/reverse", status_code=201)
def post_reverse(journal_id: str, request: Request, ctx: Ctx = Depends(replay_guard)):
    return persist(ctx, request, 201, reverse_journal(ctx.session, ctx.principal, journal_id))


@router.get("/legal-entities/{legal_entity_id}/trial-balance")
def get_trial_balance(legal_entity_id: str, period_id: str = Query(min_length=1), ctx: Ctx = Depends(get_context)) -> dict:
    return trial_balance(ctx.session, ctx.principal, legal_entity_id, period_id)


@router.get("/accounts/{account_id}/lines")
def get_account_lines(account_id: str, period_id: str = Query(min_length=1), ctx: Ctx = Depends(get_context)) -> dict:
    return account_lines(ctx.session, ctx.principal, account_id, period_id)


def _csv(file_name: str, content: str) -> Response:
    return Response(
        content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )


@router.get("/legal-entities/{legal_entity_id}/trial-balance.csv")
def get_trial_balance_csv(legal_entity_id: str, period_id: str = Query(min_length=1), ctx: Ctx = Depends(get_context)) -> Response:
    return _csv(*trial_balance_csv_export(ctx.session, ctx.principal, legal_entity_id, period_id))


@router.get("/accounts/{account_id}/lines.csv")
def get_account_lines_csv(account_id: str, period_id: str = Query(min_length=1), ctx: Ctx = Depends(get_context)) -> Response:
    return _csv(*account_lines_csv_export(ctx.session, ctx.principal, account_id, period_id))


@router.get("/legal-entities/{legal_entity_id}/income-statement")
def get_income_statement(legal_entity_id: str, period_id: str = Query(min_length=1), ctx: Ctx = Depends(get_context)) -> dict:
    return income_statement(ctx.session, ctx.principal, legal_entity_id, period_id)


@router.get("/legal-entities/{legal_entity_id}/income-statement.csv")
def get_income_statement_csv(legal_entity_id: str, period_id: str = Query(min_length=1), ctx: Ctx = Depends(get_context)) -> Response:
    return _csv(*income_statement_csv_export(ctx.session, ctx.principal, legal_entity_id, period_id))


@router.get("/legal-entities/{legal_entity_id}/balance-sheet")
def get_balance_sheet(legal_entity_id: str, period_id: str = Query(min_length=1), ctx: Ctx = Depends(get_context)) -> dict:
    return balance_sheet(ctx.session, ctx.principal, legal_entity_id, period_id)


@router.get("/legal-entities/{legal_entity_id}/balance-sheet.csv")
def get_balance_sheet_csv(legal_entity_id: str, period_id: str = Query(min_length=1), ctx: Ctx = Depends(get_context)) -> Response:
    return _csv(*balance_sheet_csv_export(ctx.session, ctx.principal, legal_entity_id, period_id))


@router.post("/legal-entities/{legal_entity_id}/year-end-closing", status_code=201)
def post_year_end_closing(legal_entity_id: str, body: YearEndClosingCreate, request: Request, ctx: Ctx = Depends(replay_guard)):
    result = build_closing_draft(ctx.session, ctx.principal, legal_entity_id, body.fiscal_year, body.retained_earnings_account_id)
    return persist(ctx, request, 201, result)
