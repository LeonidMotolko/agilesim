"""Domain errors and their translation into HTTP responses (one central place).

Services raise a ``DomainError``; they know nothing about HTTP. ``register_error_handlers``
maps each error to a status code and a uniform JSON body ``{"error": {"code", "message"}}``.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class DomainError(Exception):
    """Base class of every error that is part of the business rules."""

    status_code = 400
    code = "bad_request"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(DomainError):
    status_code = 404
    code = "not_found"


class ConflictError(DomainError):
    status_code = 409
    code = "conflict"


class RuleViolationError(DomainError):
    """The action is well-formed but a rule of the game forbids it (WIP limit, wrong stage...)."""

    status_code = 422
    code = "rule_violation"


class UnauthorizedError(DomainError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(DomainError):
    status_code = 403
    code = "forbidden"


def error_body(code: str, message: str, details: object | None = None) -> dict[str, object]:
    body: dict[str, object] = {"code": code, "message": message}
    if details is not None:
        body["details"] = details
    return {"error": body}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return JSONResponse(
            error_body(exc.code, exc.message), status_code=exc.status_code, headers=headers
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"field": ".".join(str(part) for part in err["loc"][1:]), "message": err["msg"]}
            for err in exc.errors()
        ]
        return JSONResponse(
            error_body("validation_error", "Invalid request", details), status_code=422
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            error_body("http_error", str(exc.detail)),
            status_code=exc.status_code,
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "unhandled error",
            exc_info=exc,
            extra={"path": request.url.path, "method": request.method},
        )
        return JSONResponse(error_body("internal_error", "Internal server error"), status_code=500)
