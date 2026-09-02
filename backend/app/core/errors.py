"""One place that maps domain failures to HTTP responses (CONVENTIONS).

Handlers and services raise `AppError` subclasses; nothing in the codebase
builds an HTTPException by hand, so the error envelope stays identical
everywhere: {"code": ..., "message": ..., "details": ...}.
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFound(AppError):
    status_code = 404
    code = "not_found"


class Conflict(AppError):
    status_code = 409
    code = "conflict"


class Unauthorized(AppError):
    status_code = 401
    code = "unauthorized"


class Forbidden(AppError):
    status_code = 403
    code = "forbidden"


class EmailNotVerified(Forbidden):
    code = "email_not_verified"


class TooManyRequests(AppError):
    status_code = 429
    code = "too_many_requests"


class UpstreamUnavailable(AppError):
    status_code = 503
    code = "upstream_unavailable"


def _envelope(code: str, message: str, details: dict[str, Any]) -> dict[str, Any]:
    return {"code": code, "message": message, "details": details}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_envelope("validation_error", "ورودی نامعتبر است", {"errors": exc.errors()}),
        )
