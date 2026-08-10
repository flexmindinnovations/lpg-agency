"""Tenant context binds into structured logging (`03-backend-architecture.md`
§10: "every log entry carries... correlation_id, tenant_id, user_id").

Correlation ID's binding is already exercised by
`CorrelationIdMiddleware` (wired in `lpg.api.app`, covered by the existing
health/problem-details test suites hitting real requests). This file covers
the piece `get_tenant_context` adds: binding `tenant_id`/`user_id` once a
tenant is resolved from a verified JWT (Phase 6, ADR-035), using the same
`structlog.contextvars` mechanism Phase 2's interim header-based resolver
originally proved.
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
from lpg.config.settings import Settings
from lpg.infrastructure.identity.jwt_signer import PyJwtSigner

if TYPE_CHECKING:
    from collections.abc import Iterator


def _bearer_request(token: str) -> Request:
    """A real (but connection-less) Starlette ``Request`` carrying an
    ``Authorization: Bearer`` header — the same construction pattern
    ``tests/integration/test_tenant_dependency_chain.py`` uses."""
    encoded = [(b"authorization", f"Bearer {token}".encode())]
    return Request(scope={"type": "http", "headers": encoded})


@pytest.fixture
def signer() -> Iterator[PyJwtSigner]:
    """`get_tenant_context` pulls `JwtSigner` from `AppState` — populate it
    for this test module only, the same scoped-fixture pattern
    `test_tenant_dependency_chain.py`'s `app_database` fixture uses for
    `AppState.database`.

    Each `Settings()` call generates a fresh, random ephemeral RS256
    keypair (`model_post_init`) — this fixture is the *one* signer for the
    whole test, shared between the code that issues a token and the code
    that later verifies it, so they always agree on the same key.
    """
    from lpg.api.app import get_app_state

    instance = PyJwtSigner(Settings(environment="local"))
    state = get_app_state()
    state.jwt_signer = instance
    try:
        yield instance
    finally:
        state.jwt_signer = None


def _issue_token(signer: PyJwtSigner, *, tenant_id: uuid.UUID, user_id: uuid.UUID | None) -> str:
    return signer.issue_access_token(
        {
            "sub": str(user_id) if user_id else str(uuid.uuid4()),
            "tenant_id": str(tenant_id),
            "role": "manager",
            "scope": "",
        }
    )


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
        self, signer: PyJwtSigner, captured_logs: StringIO
    ) -> None:
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        request = _bearer_request(_issue_token(signer, tenant_id=tenant_id, user_id=user_id))

        await get_tenant_context(request)
        get_logger("test").info("some_downstream_event")

        payload = json.loads(captured_logs.getvalue().strip())
        assert payload["tenant_id"] == str(tenant_id)

    async def test_user_id_appears_when_present(
        self, signer: PyJwtSigner, captured_logs: StringIO
    ) -> None:
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        request = _bearer_request(_issue_token(signer, tenant_id=tenant_id, user_id=user_id))

        await get_tenant_context(request)
        get_logger("test").info("some_downstream_event")

        payload = json.loads(captured_logs.getvalue().strip())
        assert payload["user_id"] == str(user_id)
