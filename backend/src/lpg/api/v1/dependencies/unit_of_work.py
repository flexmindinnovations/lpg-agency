"""The tenant-scoped Unit of Work dependency.

Per ``03-backend-architecture.md`` §3.2's illustrative shape: resolve the
tenant, open a session scoped to it, wrap the session in a
``UnitOfWork`` — never hand a router or use case a raw ``AsyncSession``
directly. The return type here is the *application-layer* ``UnitOfWork``
protocol, not the SQLAlchemy type, so nothing above this module ever needs to
know SQLAlchemy exists.

This module is a deliberate, narrow exception to "SQLAlchemy stays inside
infrastructure" — the same role ``lpg.api.app`` already plays for the
database and Redis connections. Dependency-wiring modules under
``api/v1/dependencies/`` are where the API layer is allowed to know
concrete infrastructure types exist, precisely so that routers and use cases
never have to (see the ``ignore_imports`` entries in ``pyproject.toml``).

``TenantContext``/``UnitOfWork``/``AsyncIterator`` are real imports, not
``TYPE_CHECKING``-guarded — ``get_unit_of_work`` is itself passed to
``Depends()`` at every call site, and with ``from __future__ import
annotations``, FastAPI resolves its signature via
``typing.get_type_hints()`` at request time. See
``api/v1/routers/auth.py``'s module docstring for the full failure mode
this avoids (found by a failing Phase 6 end-to-end test — this exact bug
was latent here too, just never triggered, since no router had used this
dependency yet).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Annotated

from fastapi import Depends

from lpg.api.v1.dependencies.tenant import get_tenant_context
from lpg.application.common.ports import TenantContext, UnitOfWork


async def get_unit_of_work(
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> AsyncIterator[UnitOfWork]:
    """Yield a ``UnitOfWork`` scoped to the resolved request's tenant.

    Commits on clean exit, rolls back on exception — see
    ``SqlAlchemyUnitOfWork.__aexit__``. Imports are deferred to function scope
    for the same reason as ``lpg.api.v1.routers.health``: ``lpg.api.app`` has
    a module-level ``app = create_app()`` side effect that must not run at
    import time here.
    """
    from lpg.api.app import get_app_state
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

    state = get_app_state()
    database = state.database
    if database is None:
        msg = "Database is not connected — the application lifespan has not run."
        raise RuntimeError(msg)

    async for session in database.open_session(tenant_id=tenant_context.tenant_id):
        uow = SqlAlchemyUnitOfWork(session, tenant_context, event_dispatcher=state.event_dispatcher)
        async with uow:
            yield uow


def get_unit_of_work_factory(
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> Callable[[], AbstractAsyncContextManager[UnitOfWork]]:
    """A factory minting a **fresh** ``UnitOfWork`` — its own session, its
    own transaction — on every call, for the rare endpoint that must commit
    more than once in a single request (e.g. bulk-cancel processing N
    orders one at a time).

    Reusing a single ``UnitOfWork`` across multiple ``.commit()`` calls is
    broken two ways: ``Database._apply_tenant_context()`` sets the RLS
    tenant GUC via ``set_config(..., is_local => true)``
    (``SET LOCAL`` semantics), which resets the moment the first commit ends
    that transaction — every read after that silently sees zero rows, not
    an error. And ``SqlAlchemyUnitOfWork`` marks itself finished after its
    first commit, so every later ``.commit()`` on the same instance is a
    silent no-op — nothing after the first order would ever actually
    persist. ``get_unit_of_work`` (singular, request-scoped) remains correct
    for every ordinary endpoint and should stay the default; reach for this
    only when a request's own logic needs several independent transactions.
    """
    from lpg.api.app import get_app_state
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

    state = get_app_state()
    database = state.database
    if database is None:
        msg = "Database is not connected — the application lifespan has not run."
        raise RuntimeError(msg)

    @asynccontextmanager
    async def _factory() -> AsyncIterator[UnitOfWork]:
        async for session in database.open_session(tenant_id=tenant_context.tenant_id):
            uow = SqlAlchemyUnitOfWork(
                session, tenant_context, event_dispatcher=state.event_dispatcher
            )
            async with uow:
                yield uow

    return _factory
