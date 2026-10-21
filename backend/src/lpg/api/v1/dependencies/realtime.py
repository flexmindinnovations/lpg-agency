"""Ownership lookups the WebSocket subscription gate needs.

Composition-root wiring like the other `dependencies/*.py` modules: the one
place the realtime router may reach concrete repositories. Each lookup opens
its own tenant-scoped (RLS) session — a WebSocket outlives any request
transaction, so it cannot borrow one.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, Protocol, cast

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator

    from lpg.infrastructure.persistence.database import Database
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


class SubscriptionOwnership(Protocol):
    async def driver_id_for(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> uuid.UUID | None:
        """The `Driver` record behind a driver's login."""
        ...

    async def customer_owns_order(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, order_id: uuid.UUID
    ) -> bool:
        """Whether the order belongs to the customer behind this login."""
        ...


class DatabaseSubscriptionOwnership:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def driver_id_for(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> uuid.UUID | None:
        from lpg.infrastructure.persistence.repositories.driver import (
            SqlAlchemyDriverRepository,
        )

        async with self._unit_of_work(tenant_id) as uow:
            driver = await SqlAlchemyDriverRepository(uow).get_by_identity_user_id(user_id)
            return driver.id if driver is not None else None

    async def customer_owns_order(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, order_id: uuid.UUID
    ) -> bool:
        from lpg.config.settings import get_settings
        from lpg.infrastructure.persistence.repositories.customer import (
            SqlAlchemyCustomerRepository,
        )
        from lpg.infrastructure.persistence.repositories.order import SqlAlchemyOrderRepository
        from lpg.infrastructure.security.field_encryption import FernetFieldEncryptor

        async with self._unit_of_work(tenant_id) as uow:
            customer = await SqlAlchemyCustomerRepository(
                uow, FernetFieldEncryptor(get_settings())
            ).get_by_identity_user_id(user_id)
            if customer is None:
                return False
            order = await SqlAlchemyOrderRepository(uow).get_by_id(order_id)
            return order is not None and order.customer_id == customer.id

    @asynccontextmanager
    async def _unit_of_work(self, tenant_id: uuid.UUID) -> AsyncIterator[SqlAlchemyUnitOfWork]:
        """A read-only, tenant-scoped unit of work, always rolled back."""
        from lpg.application.common.tenant import RequestTenantContext
        from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

        sessions = cast("AsyncGenerator[Any]", self._database.open_session(tenant_id=tenant_id))
        session = await anext(sessions)
        try:
            uow = SqlAlchemyUnitOfWork(session, RequestTenantContext(tenant_id=tenant_id))
            try:
                yield uow
            finally:
                await uow.rollback()
        finally:
            await sessions.aclose()


def build_subscription_ownership(database: Database | None) -> SubscriptionOwnership | None:
    return DatabaseSubscriptionOwnership(database) if database is not None else None
