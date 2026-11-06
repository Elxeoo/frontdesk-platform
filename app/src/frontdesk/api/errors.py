"""One error shape for every failure: {"error": {"code": ..., "message": ...}} (docs/api.md)."""

from __future__ import annotations

import logging
from collections.abc import Mapping

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from frontdesk.db import DatabaseUnavailable
from frontdesk.domain import DomainError

log = logging.getLogger(__name__)

_CODES = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 500: "INTERNAL"}


class InjectedFault(Exception):
    """Raised by the fault switch (platform contract C7); answered like a real server error."""


def error_response(
    status: int, code: str, message: str, headers: Mapping[str, str] | None = None
) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": code, "message": message}}, status_code=status, headers=headers
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return error_response(exc.status, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in err['loc'] if part != 'body')}: {err['msg']}"
            for err in exc.errors()
        )
        return error_response(422, "VALIDATION", problems or "The request is not valid.")

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
        code = _CODES.get(exc.status_code, "HTTP_ERROR")
        # Keep headers such as `Allow` on a 405.
        return error_response(exc.status_code, code, str(exc.detail), exc.headers)

    @app.exception_handler(DatabaseUnavailable)
    async def database_unavailable(_: Request, exc: DatabaseUnavailable) -> JSONResponse:
        log.warning("database unavailable", extra={"reason": type(exc.__cause__).__name__})
        return error_response(
            503, "UNAVAILABLE", "The database is not reachable right now.", {"Retry-After": "5"}
        )

    @app.exception_handler(InjectedFault)
    async def injected_fault(_: Request, __: InjectedFault) -> JSONResponse:
        return error_response(500, "INTERNAL", "Injected fault (FAULT_ERROR_RATE).")

    # Unexpected exceptions are answered by RequestContextMiddleware, which also logs them.
