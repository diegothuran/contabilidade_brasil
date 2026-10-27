from __future__ import annotations

from fastapi.responses import JSONResponse

from contabil.platform.correlation import correlation_id


class DomainError(Exception):
    def __init__(self, status_code: int, title: str, detail: str, *, errors: list | None = None) -> None:
        self.status_code = status_code
        self.title = title
        self.detail = detail
        self.errors = errors
        super().__init__(detail)


class IdempotentReplay(Exception):
    def __init__(self, status_code: int, body: dict) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__("idempotent replay")


def problem_response(status_code: int, title: str, detail: str, *, errors: list | None = None) -> JSONResponse:
    payload: dict = {
        "type": "about:blank",
        "title": title,
        "status": status_code,
        "detail": detail,
        "correlation_id": correlation_id.get(),
    }
    if errors is not None:
        payload["errors"] = errors
    return JSONResponse(payload, status_code=status_code, media_type="application/problem+json")
