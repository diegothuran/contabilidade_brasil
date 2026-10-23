from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from contabil.audit.service import to_dict, verify_chain
from contabil.platform.deps import Ctx, get_context
from contabil.tables import AuditEvent
from contabil.tenancy.service import before_cursor, encode_cursor, page_limit
from sqlalchemy import select

router = APIRouter()


@router.get("/audit-events")
def get_audit_events(
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    ctx: Ctx = Depends(get_context),
) -> dict:
    limit = page_limit(limit)
    stmt = select(AuditEvent).where(AuditEvent.tenant_id == ctx.principal.tenant_id)
    comparison = before_cursor(AuditEvent.occurred_at, AuditEvent.id, cursor)
    if comparison is not None:
        stmt = stmt.where(comparison)
    rows = ctx.session.scalars(stmt.order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc()).limit(limit + 1)).all()
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        rows = rows[:limit]
        next_cursor = encode_cursor(last.occurred_at, last.id)
    return {"items": [to_dict(row) for row in rows], "next_cursor": next_cursor}


@router.get("/audit-events/verify")
def get_audit_verify(ctx: Ctx = Depends(get_context)) -> dict:
    return verify_chain(ctx.session, ctx.principal.tenant_id)
