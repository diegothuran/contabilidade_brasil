from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from contabil.ledger.schemas import AccountCreate
from contabil.master_data.service import account_dict, create_account, list_accounts
from contabil.platform.deps import Ctx, get_context
from contabil.platform.idempotency import persist, replay_guard
from contabil.platform.principal import ensure_role
from contabil.tenancy.service import require_entity

router = APIRouter()


@router.get("/legal-entities/{legal_entity_id}/accounts")
def get_accounts(legal_entity_id: str, ctx: Ctx = Depends(get_context)) -> dict:
    require_entity(ctx.session, ctx.principal.tenant_id, legal_entity_id)
    return {"items": [account_dict(row) for row in list_accounts(ctx.session, ctx.principal.tenant_id, legal_entity_id)]}


@router.post("/legal-entities/{legal_entity_id}/accounts", status_code=201)
def post_account(
    legal_entity_id: str,
    body: AccountCreate,
    request: Request,
    ctx: Ctx = Depends(replay_guard),
):
    ensure_role(ctx.principal, "preparer", "admin")
    require_entity(ctx.session, ctx.principal.tenant_id, legal_entity_id)
    account = create_account(
        ctx.session,
        tenant_id=ctx.principal.tenant_id,
        legal_entity_id=legal_entity_id,
        code=body.code,
        name=body.name,
        account_type=body.account_type,
        postable=body.postable,
        parent_id=body.parent_id,
    )
    return persist(ctx, request, 201, account_dict(account))
