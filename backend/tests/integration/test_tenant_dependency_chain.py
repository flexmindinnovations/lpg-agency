"""The full Request → TenantContext → UnitOfWork dependency chain, against a
real PostgreSQL.

``lpg.infrastructure.persistence.database``'s ``TestTenantContextSeam`` suite
already proves ``Database.open_session(tenant_id=...)`` sets
``app.current_tenant_id`` correctly. This suite proves the layers above it —
``get_tenant_context`` and ``get_unit_of_work`` — delegate there correctly, so
a router that declares ``Depends(get_unit_of_work)`` gets a Unit of Work whose
session is already scoped to whatever the resolver decided, with no chance to
forget.

Tenant context is resolved from a real, signed JWT (Phase 6, ADR-035) rather
than the debug header Phase 2 used — ``get_tenant_context`` now delegates to
``JwtTenantResolver``, which this suite exercises through the same
public dependency function, not by constructing the resolver directly.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from starlette.requests import Request

from lpg.api.v1.dependencies.tenant import get_tenant_context
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.application.common.errors import TokenInvalidError
from lpg.config.settings import Settings
from lpg.domain.license.license import LicenseLifecycleState
from lpg.infrastructure.identity.jwt_signer import PyJwtSigner
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.integration


class _AlwaysActiveLicenseStatusChecker:
    """Stub `LicenseStatusChecker` — this module's own concern is the
    `TenantContext`/`UnitOfWork` delegation chain, not license enforcement
    (that has its own dedicated tests), so `get_tenant_context`'s license
    check is stubbed out here rather than standing up a real Redis
    connection just to satisfy it. Same pattern as
    `test_observability_seam.py`'s identically-named stub."""

    async def get_status(self, tenant_id: uuid.UUID) -> LicenseLifecycleState:
        del tenant_id
        return LicenseLifecycleState.ACTIVE

    async def invalidate(self, tenant_id: uuid.UUID) -> None:
        del tenant_id


@pytest.fixture(autouse=True)
def _stub_license_status_checker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "lpg.api.v1.dependencies.license.get_license_status_checker",
        lambda: _AlwaysActiveLicenseStatusChecker(),
    )


class _AlwaysActiveTenantStatusChecker:
    """Stub `TenantStatusChecker` — same reasoning as
    `_AlwaysActiveLicenseStatusChecker` above, for `get_tenant_context`'s
    independent tenant-suspension check."""

    async def get_status(self, tenant_id: uuid.UUID) -> str:
        del tenant_id
        return "active"

    async def invalidate(self, tenant_id: uuid.UUID) -> None:
        del tenant_id


@pytest.fixture(autouse=True)
def _stub_tenant_status_checker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "lpg.api.v1.dependencies.tenant.get_tenant_status_checker",
        lambda: _AlwaysActiveTenantStatusChecker(),
    )

# Built lazily on first use, not at module level: a module-level `Settings()`
# call runs at collection time, before the autouse `_no_real_dotenv` fixture
# (`conftest.py`) has disabled `.env` loading for the test — and the `.env`
# on a given machine may be pointed at a real environment (e.g. production,
# per this project's earlier known-issue note) with fields this constructor
# doesn't supply, like `LPG_REDIS_URL`.
_signer_cache: PyJwtSigner | None = None


def _signer() -> PyJwtSigner:
    global _signer_cache
    if _signer_cache is None:
        _signer_cache = PyJwtSigner(Settings(environment="local"))
    return _signer_cache


def _bearer_request(token: str | None = None) -> Request:
    """A real (but connection-less) Starlette ``Request``.

    Constructed from a minimal ASGI scope rather than duck-typed, so this
    satisfies ``get_tenant_context``'s real ``Request`` type under
    ``mypy --strict`` — the same object shape FastAPI hands the dependency in
    production, just without a live ASGI server behind it.
    """
    headers = [(b"authorization", f"Bearer {token}".encode())] if token else []
    return Request(scope={"type": "http", "headers": headers})


def _issue_token(tenant_id: uuid.UUID) -> str:
    return _signer().issue_access_token(
        {"sub": str(uuid.uuid4()), "tenant_id": str(tenant_id), "role": "manager", "scope": ""}
    )


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

    Also populates ``AppState.jwt_signer`` — ``get_tenant_context`` now
    needs it to construct ``JwtTenantResolver``, the same way this fixture
    already populates ``AppState.database`` for ``get_unit_of_work``.
    """
    from lpg.api.app import get_app_state

    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable — start it with ./scripts/dev-up.sh")

    db = Database(integration_settings)
    db.connect()
    state = get_app_state()
    state.database = db
    state.jwt_signer = _signer()
    try:
        yield db
    finally:
        state.database = None
        state.jwt_signer = None
        await db.disconnect()


class TestGetTenantContext:
    async def test_resolves_from_a_verified_jwt(
        self,
        app_database: Database,  # noqa: ARG002 - side effect: populates app state
    ) -> None:
        tenant_id = uuid.uuid4()

        context = await get_tenant_context(_bearer_request(_issue_token(tenant_id)))

        assert context.tenant_id == tenant_id

    async def test_raises_a_translatable_error_without_a_bearer_token(
        self,
        app_database: Database,  # noqa: ARG002 - side effect: populates app state
    ) -> None:
        from lpg.application.common.errors import TenantContextMissingError

        with pytest.raises(TenantContextMissingError):
            await get_tenant_context(_bearer_request())

    async def test_raises_for_an_invalid_token(
        self,
        app_database: Database,  # noqa: ARG002 - side effect: populates app state
    ) -> None:
        with pytest.raises(TokenInvalidError):
            await get_tenant_context(_bearer_request("not-a-real-jwt"))


class TestGetUnitOfWork:
    async def test_session_is_scoped_to_the_resolved_tenant(
        self,
        app_database: Database,  # noqa: ARG002 - side effect: populates app state
    ) -> None:
        tenant_id = uuid.uuid4()
        context = await get_tenant_context(_bearer_request(_issue_token(tenant_id)))

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

        context_a = await get_tenant_context(_bearer_request(_issue_token(tenant_a)))
        context_b = await get_tenant_context(_bearer_request(_issue_token(tenant_b)))

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
        """`get_app_state().database` is `None` outside the lifespan.

        Only `jwt_signer` is populated here (needed to resolve tenant
        context at all) — `database` is deliberately left unset, to exercise
        the "lifespan hasn't run" path `get_unit_of_work` guards against.
        """
        from lpg.api.app import get_app_state

        state = get_app_state()
        state.jwt_signer = _signer()
        assert state.database is None
        try:
            context = await get_tenant_context(_bearer_request(_issue_token(uuid.uuid4())))

            with pytest.raises(RuntimeError, match="not connected"):
                async for _uow in get_unit_of_work(context):
                    pass
        finally:
            state.jwt_signer = None
