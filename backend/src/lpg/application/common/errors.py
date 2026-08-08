"""Application layer errors.

Distinct from domain errors (a business rule was violated) and from
infrastructure failures (something broke). Each maps to a specific HTTP status
and a stable ``error_code`` in the RFC 7807 response (ADR-021).

The authoritative catalogue of codes is ``docs/data/18-error-catalog.md``.
"""

from __future__ import annotations

from typing import Any


class ApplicationError(Exception):
    """Base class for expected, handleable application failures."""

    error_code: str = "APPLICATION_ERROR"
    http_status: int = 400
    title: str = "Application error"

    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(message)
        self.message = message
        self.context = context


class NotFoundError(ApplicationError):
    """The requested resource does not exist, or is not visible to this tenant.

    The two cases are deliberately indistinguishable to the client. Returning
    403 for "exists but belongs to another tenant" and 404 for "does not exist"
    would leak the existence of other tenants' records — a cross-tenant
    information disclosure through status codes alone.
    """

    error_code = "RESOURCE_NOT_FOUND"
    http_status = 404
    title = "Resource not found"


class PermissionDeniedError(ApplicationError):
    """The authenticated principal lacks the required permission."""

    error_code = "PERMISSION_DENIED"
    http_status = 403
    title = "Permission denied"


class AuthenticationError(ApplicationError):
    """No valid credentials were supplied."""

    error_code = "AUTHENTICATION_REQUIRED"
    http_status = 401
    title = "Authentication required"


class ConflictError(ApplicationError):
    """The request conflicts with current state."""

    error_code = "CONFLICT"
    http_status = 409
    title = "Conflict"


class ConcurrencyConflictError(ConflictError):
    """The resource was modified by someone else since it was read.

    Surfaced from the optimistic-concurrency version check. Expected in normal
    operation for the offline-first Driver App, where a device may hold a stale
    copy — the client resolves and retries rather than treating it as an error.
    """

    error_code = "CONCURRENCY_CONFLICT"
    title = "Resource was modified concurrently"


class ValidationError(ApplicationError):
    """Input failed validation beyond what request-shape checking catches.

    Shape, type and format are handled by Pydantic before a use case runs.
    This covers cross-entity preconditions that require a lookup.
    """

    error_code = "VALIDATION_FAILED"
    http_status = 422
    title = "Validation failed"

    def __init__(
        self, message: str, *, errors: dict[str, list[str]] | None = None, **context: Any
    ) -> None:
        super().__init__(message, **context)
        self.errors = errors or {}


class ServiceUnavailableError(ApplicationError):
    """A required downstream dependency is unavailable."""

    error_code = "SERVICE_UNAVAILABLE"
    http_status = 503
    title = "Service temporarily unavailable"
