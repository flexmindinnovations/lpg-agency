"""Structured logging foundation.

JSON logs via ``structlog``, with every entry carrying the correlation ID and
(once authentication exists) the tenant and user identifiers.

Redaction is implemented as a processor in the logging pipeline rather than as
a rule developers are expected to remember at each call site. That distinction
matters: a convention that depends on vigilance eventually leaks a token into
a log aggregator, and the failure is silent.
"""

from __future__ import annotations

import logging
import re
import sys
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from structlog.types import EventDict, Processor

# Field names whose values are never emitted. Matched case-insensitively on a
# substring basis, so "password", "user_password", and "passwordHash" are all
# caught without needing to enumerate every variant.
_REDACTED_SUBSTRINGS: tuple[str, ...] = (
    "password",
    "passwd",
    "secret",
    "token",
    "authorization",
    "api_key",
    "apikey",
    "otp",
    "pin",
    "credential",
    "private_key",
    "session_id",
    "cookie",
)

_REDACTED_PLACEHOLDER = "[REDACTED]"


def _redact_sensitive(_logger: object, _method_name: str, event_dict: EventDict) -> EventDict:
    """Replace values of sensitive-looking keys before they reach any sink."""
    for key in list(event_dict.keys()):
        lowered = key.lower()
        if any(marker in lowered for marker in _REDACTED_SUBSTRINGS):
            event_dict[key] = _REDACTED_PLACEHOLDER
    return event_dict


#: Credentials that can ride in a URL query string. Matched as
#: `name=value` so the value (up to `&`, whitespace or a quote) is replaced.
_QUERY_SECRET = re.compile(
    r"(?P<key>[?&](?:access_token|refresh_token|token|ticket|otp|code)=)[^&\s\"']+",
    re.IGNORECASE,
)

#: Server loggers that print request lines with the raw query string —
#: uvicorn's access log, its WebSocket handshake lines (logged on
#: `uvicorn.error`: `"WebSocket /api/v1/ws?token=..." [accepted]`), and
#: gunicorn's own access log.
_REQUEST_LINE_LOGGERS = ("uvicorn.access", "uvicorn.error", "gunicorn.access", "gunicorn.error")


def redact_query_secrets(text: str) -> str:
    """`/api/v1/ws?token=eyJ...` -> `/api/v1/ws?token=[REDACTED]`."""
    return _QUERY_SECRET.sub(rf"\g<key>{_REDACTED_PLACEHOLDER}", text)


class QuerySecretRedactingFilter(logging.Filter):
    """Rewrites a record's message so no token in a URL reaches a sink
    (DO-38 / CA-18). A filter, not a structlog processor, because these
    records come from uvicorn/gunicorn's own stdlib loggers."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001 - a malformed record is passed through untouched
            return True
        redacted = redact_query_secrets(message)
        if redacted != message:
            record.msg = redacted
            record.args = None
        return True


def install_query_secret_redaction() -> None:
    """Attach the filter to the server loggers. Idempotent."""
    for name in _REQUEST_LINE_LOGGERS:
        logger = logging.getLogger(name)
        if not any(isinstance(f, QuerySecretRedactingFilter) for f in logger.filters):
            logger.addFilter(QuerySecretRedactingFilter())


def _add_log_level_name(_logger: object, method_name: str, event_dict: EventDict) -> EventDict:
    """Normalise the level field name to ``level`` in upper case."""
    event_dict["level"] = method_name.upper()
    return event_dict


def configure_logging(*, level: str = "INFO", json_output: bool = True) -> None:
    """Configure ``structlog`` and route the stdlib logger through it.

    Logs go to stdout only. Nothing is written to local files, keeping the
    application stateless and container-native — the platform collects stdout.
    """
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        _add_log_level_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        # Redaction runs last among the enrichers, so it also covers fields
        # added by earlier processors and by bound context.
        _redact_sensitive,
    ]

    renderer: Processor = (
        structlog.processors.JSONRenderer()
        if json_output
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Quieten access logs — the correlation-ID middleware emits a richer,
    # structured equivalent, and two log lines per request is noise.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    install_query_secret_redaction()


def get_logger(name: str | None = None) -> Any:
    """Return a bound structlog logger."""
    return structlog.get_logger(name)
