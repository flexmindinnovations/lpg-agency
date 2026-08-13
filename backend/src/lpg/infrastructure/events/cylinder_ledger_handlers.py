"""Domain-event handlers that project deliveries onto the Cylinder Ledger.

Lives in infrastructure, not application, because a handler is an *adapter*:
it opens its own database session and builds concrete repositories. The
application layer may only depend on the domain (enforced by import-linter),
so it cannot legally reach either — the same reasoning that puts
`infrastructure/jobs/worker.py`'s job bodies here rather than beside their
use cases.

The `Database` arrives as an argument from the composition root
(`api/app.py`) rather than being pulled from app state, keeping this module
free of any import back into the api layer.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from lpg.domain.order.order import CylinderDelivered

if TYPE_CHECKING:
    from lpg.domain.common.base import DomainEvent
    from lpg.infrastructure.events.dispatcher import DomainEventDispatcher
    from lpg.infrastructure.persistence.database import Database

#: Ledger rows are written by a background reaction, not a signed-in user, so
#: `performed_by` records the nil UUID rather than inventing an actor.
_SYSTEM_ACTOR_ID = uuid.UUID(int=0)


def register_cylinder_ledger_handlers(
    dispatcher: DomainEventDispatcher, database: Database
) -> None:
    """Subscribe the ledger projection to `CylinderDelivered`.

    Deliberately **only** `CylinderDelivered`, not also Delivery's
    `OrderDelivered`. `DeliverOrderUseCase` mutates the Order *and* the Route
    in one unit of work, so a single delivery emits both events and the
    dispatcher would invoke a handler registered for both of them twice —
    appending every delivered and collected cylinder to the customer's ledger
    two times over. `CylinderDelivered` is the right one of the pair: it is
    the Order aggregate's own event and fires whether or not the order was
    ever attached to a route.
    """

    async def _on_cylinder_delivered(event: DomainEvent) -> None:
        # Registration is exact-type (see `DomainEventDispatcher.register`),
        # so this is the only event that reaches this handler.
        assert isinstance(event, CylinderDelivered)
        await _append_ledger_transactions(database, event)

    dispatcher.register(CylinderDelivered, _on_cylinder_delivered)


async def _append_ledger_transactions(database: Database, event: CylinderDelivered) -> None:
    """Run the ledger projection in its own tenant-scoped transaction.

    Dispatch happens *after* the triggering request's commit, so that
    transaction is already closed and this needs a session of its own —
    opened tenant-scoped, so RLS applies exactly as it does on a request path
    (ADR-017; nothing ever runs unscoped).
    """
    from lpg.application.common.tenant import RequestTenantContext
    from lpg.application.cylinder_ledger.use_cases import (
        AppendLedgerTransactionsFromOrderUseCase,
    )
    from lpg.infrastructure.persistence.repositories.cylinder_ledger import (
        SqlAlchemyCylinderLedgerRepository,
    )
    from lpg.infrastructure.persistence.repositories.order import SqlAlchemyOrderRepository
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

    async for session in database.open_session(tenant_id=event.tenant_id):
        tenant_context = RequestTenantContext(tenant_id=event.tenant_id)
        # No dispatcher: events raised while projecting must not re-enter
        # dispatch from inside a handler that dispatch itself invoked.
        async with SqlAlchemyUnitOfWork(session, tenant_context) as uow:
            use_case = AppendLedgerTransactionsFromOrderUseCase(
                SqlAlchemyCylinderLedgerRepository(uow),
                SqlAlchemyOrderRepository(uow),
            )
            await use_case.execute(
                tenant_id=event.tenant_id,
                order_id=event.order_id,
                performed_by=_SYSTEM_ACTOR_ID,
            )
            await uow.commit()
