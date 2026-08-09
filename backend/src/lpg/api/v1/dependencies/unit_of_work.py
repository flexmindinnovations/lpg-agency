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
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import Depends

from lpg.api.v1.dependencies.tenant import get_tenant_context

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

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
