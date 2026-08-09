"""Tenant context binds into structured logging (`03-backend-architecture.md`
§10: "every log entry carries... correlation_id, tenant_id, user_id").

Correlation ID's binding is already exercised by
`CorrelationIdMiddleware` (wired in `lpg.api.app`, covered by the existing
health/problem-details test suites hitting real requests). This file covers
the piece Phase 2 adds: `get_tenant_context` binding `tenant_id`/`user_id`
once a tenant is resolved, using the same `structlog.contextvars` mechanism.
"""

from __future__ import annotations

import json
import uuid
from io import StringIO
from typing import TYPE_CHECKING

import pytest
import structlog
from starlette.requests import Request

from lpg.api.v1.dependencies.tenant import get_tenant_context
from lpg.config.logging import configure_logging, get_logger
from lpg.infrastructure.tenant.header_resolver import TENANT_HEADER, USER_HEADER

if TYPE_CHECKING:
    from collections.abc import Iterator


def _request(headers: dict[str, str]) -> Request:
    """A real (but connection-less) Starlette ``Request`` — see the
    identical helper and rationale in
    ``tests/integration/test_tenant_dependency_chain.py``."""
    encoded = [(key.lower().encode(), value.encode()) for key, value in headers.items()]
    return Request(scope={"type": "http", "headers": encoded})


@pytest.fixture
def captured_logs() -> Iterator[StringIO]:
    """Capture structlog JSON output into a buffer — same pattern as
    `test_logging.py`, duplicated rather than imported since it is a fixture,
    not a reusable helper, and cross-test-module fixture imports are more
    confusing than the few duplicated lines."""
    buffer = StringIO()
    configure_logging(level="DEBUG", json_output=True)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(file=buffer),
        cache_logger_on_first_use=False,
    )
    structlog.contextvars.clear_contextvars()
    yield buffer
    structlog.contextvars.clear_contextvars()
    structlog.reset_defaults()


class TestTenantContextLogBinding:
    async def test_tenant_id_appears_on_logs_emitted_after_resolution(
        self, captured_logs: StringIO
    ) -> None:
        tenant_id = uuid.uuid4()
        request = _request({TENANT_HEADER: str(tenant_id)})

        await get_tenant_context(request)
        get_logger("test").info("some_downstream_event")

        payload = json.loads(captured_logs.getvalue().strip())
        assert payload["tenant_id"] == str(tenant_id)

    async def test_user_id_appears_when_present(self, captured_logs: StringIO) -> None:
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        request = _request({TENANT_HEADER: str(tenant_id), USER_HEADER: str(user_id)})

        await get_tenant_context(request)
        get_logger("test").info("some_downstream_event")

        payload = json.loads(captured_logs.getvalue().strip())
        assert payload["user_id"] == str(user_id)

    async def test_user_id_is_absent_rather_than_the_string_none(
        self, captured_logs: StringIO
    ) -> None:
        """No authenticated user yet (Phase 2 has no JWT) must not render as
        the literal string "None" in a structured log — that is worse than
        omitting the field, since a log consumer might match on it."""
        tenant_id = uuid.uuid4()
        request = _request({TENANT_HEADER: str(tenant_id)})

        await get_tenant_context(request)
        get_logger("test").info("some_downstream_event")

        payload = json.loads(captured_logs.getvalue().strip())
        assert payload["user_id"] is None
