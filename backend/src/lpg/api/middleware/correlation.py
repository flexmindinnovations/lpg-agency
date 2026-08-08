"""Correlation ID middleware.

Accepts an inbound correlation ID or generates one, binds it to the logging
context for the life of the request, and echoes it on the response.

The value propagates from the client request through the API, into domain event
dispatch, into any enqueued background job, and onto real-time messages — so a
single business transaction stays traceable end to end even as it fans out
across several downstream effects (``12-observability.md`` §4).
"""

from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING

import structlog
from starlette.middleware.base import BaseHTTPMiddleware

from lpg.config.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.requests import Request
    from starlette.responses import Response

_logger = get_logger(__name__)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Bind a correlation ID to every request and log its outcome."""

    def __init__(self, app: object, *, header_name: str = "X-Correlation-ID") -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.header_name = header_name

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        correlation_id = request.headers.get(self.header_name) or str(uuid.uuid4())

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            correlation_id=correlation_id,
            request_path=request.url.path,
            request_method=request.method,
        )

        request.state.correlation_id = correlation_id

        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # Log and re-raise. The exception handlers own the response shape;
            # this middleware only guarantees the failure is observable with
            # its correlation ID attached.
            duration_ms = (time.perf_counter() - started) * 1000
            _logger.exception(
                "request_failed",
                duration_ms=round(duration_ms, 2),
            )
            raise

        duration_ms = (time.perf_counter() - started) * 1000
        response.headers[self.header_name] = correlation_id

        # Health probes fire constantly and would drown out real traffic.
        if not request.url.path.startswith("/health"):
            _logger.info(
                "request_completed",
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )

        return response
