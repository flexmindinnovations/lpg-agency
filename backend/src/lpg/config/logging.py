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


def get_logger(name: str | None = None) -> Any:
    """Return a bound structlog logger."""
    return structlog.get_logger(name)
