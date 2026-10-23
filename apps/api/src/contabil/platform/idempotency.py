from __future__ import annotations

import hashlib
import logging

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from contabil.platform.auth import apply_tenant
from contabil.platform.deps import Ctx, get_context
from contabil.platform.errors import DomainError, IdempotentReplay
from contabil.platform.ids import new_id
from contabil.tables import IdempotencyKey

logger = logging.getLogger(__name__)


def _digest(method: str, path: str, raw: bytes) -> str:
    return hashlib.sha256(f"{method}\n{path}\n".encode() + raw).hexdigest()


def _constraint_name(exc: IntegrityError) -> str | None:
    diag = getattr(exc.orig, "diag", None)
    if diag is None:
        return None
    return getattr(diag, "constraint_name", None)


def claim_idempotency(request: Request, ctx: Ctx, raw: bytes) -> None:
    if len(raw) > 1_000_000:
        raise DomainError(413, "Payload grande demais", "O corpo excede o limite de 1 MB.")
    key = request.headers.get("idempotency-key")
    if key is None or not 8 <= len(key) <= 200:
        raise DomainError(400, "Idempotency-Key ausente", "Envie o cabeçalho Idempotency-Key com 8 a 200 caracteres.")
    digest = _digest(request.method, request.url.path, raw)
    existing = ctx.session.scalar(
        select(IdempotencyKey).where(IdempotencyKey.tenant_id == ctx.principal.tenant_id, IdempotencyKey.key == key)
    )
    if existing is not None:
        if existing.request_hash != digest:
            raise DomainError(409, "Chave de idempotência reutilizada", "A mesma chave foi enviada com outro pedido.")
        raise IdempotentReplay(existing.response_status, existing.response_body)
    request.state.idempotency_key = key
    request.state.idempotency_hash = digest


async def replay_guard(request: Request, ctx: Ctx = Depends(get_context)) -> Ctx:
    claim_idempotency(request, ctx, await request.body())
    return ctx


def persist(ctx: Ctx, request: Request, status_code: int, body: dict):
    from fastapi.responses import JSONResponse

    key = getattr(request.state, "idempotency_key", None)
    digest = getattr(request.state, "idempotency_hash", None)
    if not key or not digest:
        raise DomainError(500, "Falha interna", "A operação de escrita não passou pela idempotência.")
    ctx.session.add(
        IdempotencyKey(
            id=new_id("idem"),
            tenant_id=ctx.principal.tenant_id,
            key=key,
            request_hash=digest,
            response_status=status_code,
            response_body=body,
        )
    )
    try:
        ctx.session.commit()
    except SQLAlchemyError as exc:
        message = str(getattr(exc, "orig", exc))
        ctx.session.rollback()
        if "journal is not balanced" in message:
            raise DomainError(409, "Journal desequilibrado", "Débitos e créditos precisam ser iguais para publicar.") from exc
        if "immutable" in message or "append-only" in message:
            raise DomainError(409, "Registro imutável", "O banco recusou a alteração de um registro publicado ou de auditoria.") from exc
        if not isinstance(exc, IntegrityError):
            raise
        apply_tenant(ctx.session, ctx.principal.tenant_id)
        name = _constraint_name(exc)
        if name == "uq_idempotency_tenant_key":
            existing = ctx.session.scalar(
                select(IdempotencyKey).where(IdempotencyKey.tenant_id == ctx.principal.tenant_id, IdempotencyKey.key == key)
            )
            if existing is not None and existing.request_hash == digest:
                return JSONResponse(existing.response_body, status_code=existing.response_status)
            raise DomainError(409, "Chave de idempotência reutilizada", "A mesma chave foi enviada com outro pedido.") from exc
        if name == "uq_accounts_entity_code":
            raise DomainError(409, "Conta já existe", "Já existe uma conta com este código na empresa.") from exc
        logger.warning("integrity constraint %s", name)
        raise DomainError(409, "Conflito de persistência", "O banco rejeitou a operação.") from exc
    return JSONResponse(body, status_code=status_code)
