"""Translate database driver errors into safe, user-facing application errors.

A constraint violation that reaches the API used to be turned into a 500 whose
`detail` was the raw SQLAlchemy message: SQL text, schema, table and column
names, the tenant id and every bound parameter, shown word for word in the
Dashboard's error toast (QA finding DA-03). This module is the one place that
looks inside a `DBAPIError`:

* the few failures a person can act on (a duplicate, a value that is too long or
  not allowed, a record still in use, a concurrent edit) become an
  `ApplicationError` with a plain-language message and a stable `error_code`;
* anything else is reported as `None`, so the caller falls back to the generic
  500 ("quote the trace_id") without echoing the driver message.

The full driver message is only ever logged server-side, with the request's
correlation id, by whoever calls `translate_database_error`.

Lives in infrastructure because it must know SQLAlchemy and the PostgreSQL
SQLSTATE codes exist; the API composition root (`lpg.api.app`) registers it.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.exc import DBAPIError

from lpg.application.common.errors import ApplicationError, ConflictError, ValidationError

#: The exception types the composition root should route through
#: `translate_database_error`.
DATABASE_ERROR_TYPES: tuple[type[Exception], ...] = (DBAPIError,)


class DuplicateRecordError(ConflictError):
    error_code = "DUPLICATE_RECORD"
    title = "This record already exists"


class RecordInUseError(ConflictError):
    error_code = "RELATED_RECORD_CONFLICT"
    title = "A related record is missing or still in use"


class ConcurrentUpdateError(ConflictError):
    error_code = "CONCURRENT_UPDATE"
    title = "Someone else changed this at the same time"


class InvalidValueError(ValidationError):
    error_code = "INVALID_VALUE"
    title = "A value was not accepted"


# SQLSTATE -> (error class, message). Messages never name a table, column,
# constraint or value: those are internal and may belong to another tenant.
_TRANSLATIONS: dict[str, tuple[type[ApplicationError], str]] = {
    "23505": (
        DuplicateRecordError,
        "A record with the same details already exists. Use a different name or number.",
    ),
    "23503": (
        RecordInUseError,
        "This refers to a record that no longer exists, or is still used elsewhere.",
    ),
    "23514": (InvalidValueError, "One or more values are not allowed. Check the form and retry."),
    "23502": (InvalidValueError, "A required value is missing. Check the form and retry."),
    "22001": (InvalidValueError, "One or more values are too long. Shorten them and retry."),
    "22003": (InvalidValueError, "A number is outside the allowed range."),
    "22P02": (InvalidValueError, "One or more values are in the wrong format."),
    "22007": (InvalidValueError, "A date or time is in the wrong format."),
    "22008": (InvalidValueError, "A date or time is out of range."),
    "40001": (ConcurrentUpdateError, "Someone else changed this at the same time. Please retry."),
    "40P01": (ConcurrentUpdateError, "Someone else changed this at the same time. Please retry."),
}


def sqlstate_of(error: BaseException) -> str | None:
    """The PostgreSQL SQLSTATE behind a `DBAPIError`, if the driver exposes it.

    asyncpg exceptions carry `sqlstate`; SQLAlchemy's asyncpg adapter wraps
    them and exposes the same value as `pgcode` on its own wrapper.
    """
    original: Any = getattr(error, "orig", None)
    for candidate in (original, getattr(original, "__cause__", None)):
        if candidate is None:
            continue
        code = getattr(candidate, "sqlstate", None) or getattr(candidate, "pgcode", None)
        if isinstance(code, str):
            return code
    return None


def translate_database_error(error: BaseException) -> ApplicationError | None:
    """A safe `ApplicationError` for a known database failure, else `None`."""
    if not isinstance(error, DBAPIError):
        return None
    sqlstate = sqlstate_of(error)
    if sqlstate is None or sqlstate not in _TRANSLATIONS:
        return None
    error_class, message = _TRANSLATIONS[sqlstate]
    return error_class(message, sqlstate=sqlstate)
