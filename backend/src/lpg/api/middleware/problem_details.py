"""RFC 7807 Problem Details exception handling (ADR-021).

Every error response the API emits has this shape, served as
``application/problem+json`` and extended with a stable, machine-readable
``error_code``:

    {
      "type": "https://api.lpgplatform.com/errors/resource-not-found",
      "title": "Resource not found",
      "status": 404,
      "error_code": "RESOURCE_NOT_FOUND",
      "detail": "No customer exists with the supplied identifier.",
      "instance": "/api/v1/customers/3f2a...",
      "trace_id": "..."
    }

Field naming is ``snake_case`` throughout, consistent with the rest of the API
(``docs/data/10-api-design-guidelines.md``). The authoritative catalogue of
codes is ``docs/data/18-error-catalog.md``.

Success responses return the resource directly — there is no
``{"success": true, "data": ...}`` envelope. The HTTP status already carries
that information, and unwrapping a redundant envelope in three client
applications is pure ceremony.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from fastapi import status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from lpg.application.common.errors import ApplicationError
from lpg.config.logging import get_logger
from lpg.domain.common.base import DomainError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from fastapi import FastAPI, Request

_logger = get_logger(__name__)

PROBLEM_CONTENT_TYPE = "application/problem+json"
_ERROR_TYPE_BASE = "https://api.lpgplatform.com/errors"


def _error_type_uri(error_code: str) -> str:
    """Map an error code to its documentation URI."""
    return f"{_ERROR_TYPE_BASE}/{error_code.lower().replace('_', '-')}"


def _problem_response(
    *,
    status_code: int,
    title: str,
    error_code: str,
    detail: str,
    instance: str,
    trace_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": _error_type_uri(error_code),
        "title": title,
        "status": status_code,
        "error_code": error_code,
        "detail": detail,
        "instance": instance,
    }
    if trace_id:
        body["trace_id"] = trace_id
    if extra:
        body.update(extra)

    return JSONResponse(
        status_code=status_code,
        content=body,
        media_type=PROBLEM_CONTENT_TYPE,
    )


def _trace_id(request: Request) -> str | None:
    return getattr(request.state, "correlation_id", None)


async def domain_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Business rule or invariant violation → 409 Conflict.

    409 rather than 400: the request was well-formed and the client is not at
    fault for its shape. The operation is not permitted given current state —
    which is a different thing, and clients branch on it differently.
    """
    assert isinstance(exc, DomainError)
    _logger.warning("domain_error", error_code=exc.error_code, detail=exc.message, **exc.context)
    return _problem_response(
        status_code=status.HTTP_409_CONFLICT,
        title="Business rule violation",
        error_code=exc.error_code,
        detail=exc.message,
        instance=request.url.path,
        trace_id=_trace_id(request),
    )


async def application_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Expected application failure → its declared status and code."""
    assert isinstance(exc, ApplicationError)
    extra: dict[str, Any] = {}
    errors = getattr(exc, "errors", None)
    if errors:
        extra["errors"] = errors

    _logger.warning(
        "application_error",
        error_code=exc.error_code,
        status_code=exc.http_status,
        detail=exc.message,
        **exc.context,
    )
    return _problem_response(
        status_code=exc.http_status,
        title=exc.title,
        error_code=exc.error_code,
        detail=exc.message,
        instance=request.url.path,
        trace_id=_trace_id(request),
        extra=extra or None,
    )


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Pydantic request-model failure → 422 with field-level detail.

    Field errors populate the Problem Details ``errors`` extension, consumed
    directly by the Dashboard's form error-summary component and by the mobile
    apps' form validation.
    """
    assert isinstance(exc, RequestValidationError)
    field_errors: dict[str, list[str]] = {}
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"] if part != "body")
        field_errors.setdefault(location or "__root__", []).append(error["msg"])

    return _problem_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        title="Request validation failed",
        error_code="REQUEST_VALIDATION_FAILED",
        detail="One or more fields failed validation.",
        instance=request.url.path,
        trace_id=_trace_id(request),
        extra={"errors": field_errors},
    )


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Starlette/FastAPI HTTPException → Problem Details.

    Without this, 404s from unmatched routes and 405s from wrong methods would
    return FastAPI's default ``{"detail": ...}`` shape, and the API would have
    two error formats. One contract means one client-side error path.
    """
    assert isinstance(exc, StarletteHTTPException)
    code_by_status = {
        status.HTTP_401_UNAUTHORIZED: "AUTHENTICATION_REQUIRED",
        status.HTTP_403_FORBIDDEN: "PERMISSION_DENIED",
        status.HTTP_404_NOT_FOUND: "RESOURCE_NOT_FOUND",
        status.HTTP_405_METHOD_NOT_ALLOWED: "METHOD_NOT_ALLOWED",
        status.HTTP_429_TOO_MANY_REQUESTS: "RATE_LIMIT_EXCEEDED",
    }
    error_code = code_by_status.get(exc.status_code, "HTTP_ERROR")

    return _problem_response(
        status_code=exc.status_code,
        title=str(exc.detail) if exc.detail else "HTTP error",
        error_code=error_code,
        detail=str(exc.detail),
        instance=request.url.path,
        trace_id=_trace_id(request),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Anything unexpected → 500 with a generic message.

    Full detail goes to the logs with the correlation ID; the client receives
    nothing internal. Leaking a stack trace or a database error message tells
    an attacker about the schema, the ORM, and the file layout.
    """
    _logger.exception("unhandled_exception", exception_type=type(exc).__name__)
    return _problem_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        title="Internal server error",
        error_code="INTERNAL_SERVER_ERROR",
        detail="An unexpected error occurred. Quote the trace_id when reporting this.",
        instance=request.url.path,
        trace_id=_trace_id(request),
    )


class DatabaseErrorTranslator(Protocol):
    def __call__(self, error: BaseException) -> ApplicationError | None: ...


def database_error_handler(
    translate: DatabaseErrorTranslator,
) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
    """A database driver error -> a safe Problem Details response (DA-03).

    The translator (supplied by the composition root, since only
    infrastructure may know the driver's exception types) maps the failures a
    person can act on — a duplicate, a value that is too long, a record still
    in use — to an `ApplicationError` with a plain-language message. Anything
    else is a generic 500. Either way the raw driver message (SQL, table
    names, tenant id, bound parameters) is only logged, with the trace id;
    it never reaches the client, in any environment.
    """

    async def _handler(request: Request, exc: Exception) -> JSONResponse:
        _logger.error(
            "database_error",
            exception_type=type(exc).__name__,
            error=str(exc),
            path=request.url.path,
        )
        translated = translate(exc)
        if translated is None:
            return await unhandled_exception_handler(request, exc)
        return await application_error_handler(request, translated)

    return _handler


def register_exception_handlers(
    app: FastAPI,
    *,
    database_error_types: tuple[type[Exception], ...] = (),
    translate_database_error: DatabaseErrorTranslator | None = None,
) -> None:
    """Wire every handler onto the application."""
    if translate_database_error is not None:
        handler = database_error_handler(translate_database_error)
        for error_type in database_error_types:
            app.add_exception_handler(error_type, handler)
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(ApplicationError, application_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
