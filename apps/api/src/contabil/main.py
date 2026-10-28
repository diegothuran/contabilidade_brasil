from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from contabil.audit.router import router as audit_router
from contabil.closing.router import router as closing_router
from contabil.document_requests.router import router as document_requests_router
from contabil.documents.router import router as documents_router
from contabil.exports.router import router as exports_router
from contabil.imports.router import router as imports_router
from contabil.ledger.router import router as ledger_router
from contabil.master_data.router import router as master_data_router
from contabil.periods.router import router as periods_router
from contabil.portal.router import router as portal_router
from contabil.reconciliation.router import router as reconciliation_router
from contabil.platform.correlation import correlation_id
from contabil.platform.db import get_engine
from contabil.platform.deps import require_office
from contabil.platform.errors import DomainError, IdempotentReplay, problem_response
from contabil.platform.settings import get_settings
from contabil.tenancy.router import router as tenancy_router

logger = logging.getLogger("contabil")


class CorrelationMiddleware:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {key.decode().lower(): value.decode() for key, value in scope.get("headers", [])}
        incoming = headers.get("x-correlation-id") or str(uuid4())
        token = correlation_id.set(incoming)
        status_holder = {"status": 500}

        async def send_with_correlation(message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                raw = list(message.get("headers", []))
                raw.append((b"x-correlation-id", incoming.encode()))
                message = {**message, "headers": raw}
            await send(message)

        try:
            await self.app(scope, receive, send_with_correlation)
        finally:
            if scope.get("method") != "OPTIONS":
                logger.info("%s %s %s", scope.get("method"), scope.get("path"), status_holder["status"])
            correlation_id.reset(token)


def _mount_spa(app: FastAPI, static_dir: str) -> None:
    root = Path(static_dir)
    if not root.is_dir() or not (root / "index.html").is_file():
        return
    assets = root / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    def spa(full_path: str = "") -> FileResponse:
        if full_path:
            candidate = (root / full_path).resolve()
            if candidate.is_file() and root.resolve() in candidate.parents:
                return FileResponse(candidate)
        return FileResponse(root / "index.html")

    app.add_api_route("/", spa, methods=["GET"], include_in_schema=False)
    app.add_api_route("/{full_path:path}", spa, methods=["GET"], include_in_schema=False)


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        stop = threading.Event()
        thread: threading.Thread | None = None
        if settings.outbox_in_process:
            from contabil.worker import run_loop

            thread = threading.Thread(target=run_loop, args=(stop,), name="outbox", daemon=True)
            thread.start()
        yield
        stop.set()
        if thread is not None:
            thread.join(timeout=5)

    app = FastAPI(title="Contabilidade Brasil API", version="0.1.0", lifespan=lifespan)
    origins = [item.strip() for item in settings.cors_origins.split(",") if item.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Correlation-Id", "X-Tenant-Id"],
        expose_headers=["X-Correlation-Id"],
    )
    app.add_middleware(CorrelationMiddleware)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else "Erro HTTP"
        return problem_response(exc.status_code, "Erro HTTP", detail)

    @app.exception_handler(DomainError)
    async def handle_domain(_: Request, exc: DomainError) -> JSONResponse:
        return problem_response(exc.status_code, exc.title, exc.detail, errors=exc.errors)

    @app.exception_handler(IdempotentReplay)
    async def handle_replay(_: Request, exc: IdempotentReplay) -> JSONResponse:
        return JSONResponse(exc.body, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{"loc": [str(part) for part in error["loc"]], "msg": error["msg"]} for error in exc.errors()]
        return problem_response(422, "Payload inválido", "O corpo não segue o contrato.", errors=errors)

    @app.exception_handler(SQLAlchemyError)
    async def handle_database(_: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.exception("database error")
        message = str(getattr(exc, "orig", exc))
        if "journal is not balanced" in message:
            return problem_response(409, "Journal desequilibrado", "Débitos e créditos precisam ser iguais para publicar.")
        if "immutable" in message or "append-only" in message:
            return problem_response(409, "Registro imutável", "O banco recusou a alteração.")
        return problem_response(500, "Falha interna", "A operação não foi concluída.")

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error: %s", exc.__class__.__name__)
        return problem_response(500, "Falha interna", "A operação não foi concluída.")

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok"}

    @app.get("/readyz", response_model=None)
    def readyz() -> JSONResponse:
        try:
            with get_engine().connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError:
            logger.exception("readiness failed")
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return JSONResponse({"status": "ready"})

    office = [Depends(require_office)]
    app.include_router(tenancy_router, prefix="/v1")
    app.include_router(master_data_router, prefix="/v1", dependencies=office)
    app.include_router(periods_router, prefix="/v1", dependencies=office)
    app.include_router(closing_router, prefix="/v1", dependencies=office)
    app.include_router(ledger_router, prefix="/v1", dependencies=office)
    app.include_router(documents_router, prefix="/v1", dependencies=office)
    app.include_router(document_requests_router, prefix="/v1", dependencies=office)
    app.include_router(imports_router, prefix="/v1", dependencies=office)
    app.include_router(exports_router, prefix="/v1", dependencies=office)
    app.include_router(reconciliation_router, prefix="/v1", dependencies=office)
    app.include_router(audit_router, prefix="/v1", dependencies=office)
    app.include_router(portal_router, prefix="/v1")
    if settings.static_dir:
        _mount_spa(app, settings.static_dir)
    return app


app = create_app()
