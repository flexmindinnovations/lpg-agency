"""The full Request → TenantContext → UnitOfWork dependency chain, against a
real PostgreSQL.

``lpg.infrastructure.persistence.database``'s ``TestTenantContextSeam`` suite
already proves ``Database.open_session(tenant_id=...)`` sets
``app.current_tenant_id`` correctly. This suite proves the layers above it —
``get_tenant_context`` and ``get_unit_of_work`` — delegate there correctly, so
a router that declares ``Depends(get_unit_of_work)`` gets a Unit of Work whose
session is already scoped to whatever the resolver decided, with no chance to
forget.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from starlette.requests import Request

from lpg.api.v1.dependencies.tenant import get_tenant_context
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.application.common.errors import TenantContextMissingError
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from lpg.infrastructure.tenant.header_resolver import TENANT_HEADER

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from lpg.config.settings import Settings

pytestmark = pytest.mark.integration


def _request(headers: dict[str, str] | None = None) -> Request:
    """A real (but connection-less) Starlette ``Request``.

    Constructed from a minimal ASGI scope rather than duck-typed, so this
    satisfies ``get_tenant_context``'s real ``Request`` type under
    ``mypy --strict`` — the same object shape FastAPI hands the dependency in
    production, just without a live ASGI server behind it.
    """
    encoded = [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()]
    return Request(scope={"type": "http", "headers": encoded})


@pytest.fixture
async def app_database(
    integration_settings: Settings, postgres_available: bool
) -> AsyncIterator[Database]:
    """Populate the composition root's module state the way the real
    application lifespan does, scoped to this test only.

    ``lpg.api.app`` is imported here, inside the fixture, rather than at
    module level: the module has a top-level ``app = create_app()`` side
    effect that calls ``get_settings()`` immediately on import, before any
    pytest fixture (including the autouse dotenv guard) has run. Every other
    consumer of ``get_app_state``/``get_health_checks`` in this codebase
    defers the import for the same reason (see
    ``lpg.api.v1.routers.health.readiness``).
    """
    from lpg.api.app import get_app_state

    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable — start it with ./scripts/dev-up.sh")

    db = Database(integration_settings)
    db.connect()
    state = get_app_state()
    state.database = db
    try:
        yield db
    finally:
        state.database = None
        await db.disconnect()


class TestGetTenantContext:
    async def test_resolves_from_the_debug_header(self) -> None:
        tenant_id = uuid.uuid4()

        context = await get_tenant_context(_request({TENANT_HEADER: str(tenant_id)}))

        assert context.tenant_id == tenant_id

    async def test_raises_a_translatable_error_without_a_header(self) -> None:
        with pytest.raises(TenantContextMissingError):
            await get_tenant_context(_request())


class TestGetUnitOfWork:
    async def test_session_is_scoped_to_the_resolved_tenant(
        self,
        app_database: Database,  # noqa: ARG002 - side effect: populates app state
    ) -> None:
        tenant_id = uuid.uuid4()
        context = await get_tenant_context(_request({TENANT_HEADER: str(tenant_id)}))

        async for uow in get_unit_of_work(context):
            # get_unit_of_work's declared return type is the UnitOfWork
            # protocol, which has no .session — narrowing to the concrete
            # implementation is what this test is actually verifying: that
            # the wiring produces a real, session-backed Unit of Work.
            assert isinstance(uow, SqlAlchemyUnitOfWork)
            value = (
                await uow.session.execute(text("SELECT current_setting('app.current_tenant_id')"))
            ).scalar_one()
            assert value == str(tenant_id)

    async def test_two_requests_get_independently_scoped_units_of_work(
        self,
        app_database: Database,  # noqa: ARG002 - side effect: populates app state
    ) -> None:
        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()

        context_a = await get_tenant_context(_request({TENANT_HEADER: str(tenant_a)}))
        context_b = await get_tenant_context(_request({TENANT_HEADER: str(tenant_b)}))

        async for uow in get_unit_of_work(context_a):
            assert isinstance(uow, SqlAlchemyUnitOfWork)
            seen_a = (
                await uow.session.execute(text("SELECT current_setting('app.current_tenant_id')"))
            ).scalar_one()

        async for uow in get_unit_of_work(context_b):
            assert isinstance(uow, SqlAlchemyUnitOfWork)
            seen_b = (
                await uow.session.execute(text("SELECT current_setting('app.current_tenant_id')"))
            ).scalar_one()

        assert seen_a == str(tenant_a)
        assert seen_b == str(tenant_b)
        assert seen_a != seen_b

    async def test_raises_when_the_database_has_not_connected(self) -> None:
        """`get_app_state().database` is `None` outside the lifespan."""
        from lpg.api.app import get_app_state

        state = get_app_state()
        assert state.database is None

        context = await get_tenant_context(_request({TENANT_HEADER: str(uuid.uuid4())}))

        with pytest.raises(RuntimeError, match="not connected"):
            async for _uow in get_unit_of_work(context):
                pass
