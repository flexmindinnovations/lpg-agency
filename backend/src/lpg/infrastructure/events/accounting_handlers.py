"""Domain-event handlers that generate invoices.

Like `cylinder_ledger_handlers`, this lives in infrastructure because it
opens its own database session and builds concrete repositories.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from lpg.domain.order.order import CylinderDelivered

if TYPE_CHECKING:
    from lpg.domain.common.base import DomainEvent
    from lpg.infrastructure.events.dispatcher import DomainEventDispatcher
    from lpg.infrastructure.persistence.database import Database

_SYSTEM_ACTOR_ID = uuid.UUID(int=0)


def register_accounting_handlers(dispatcher: DomainEventDispatcher, database: Database) -> None:
    """Subscribe Accounting projections to domain events."""

    async def _on_cylinder_delivered(event: DomainEvent) -> None:
        assert isinstance(event, CylinderDelivered)
        await _generate_invoice_for_delivered_order(database, event)

    dispatcher.register(CylinderDelivered, _on_cylinder_delivered)


async def _generate_invoice_for_delivered_order(
    database: Database, event: CylinderDelivered
) -> None:
    """Run invoice generation in its own tenant-scoped transaction."""
    from lpg.application.accounting.use_cases import GenerateInvoiceForOrderUseCase
    from lpg.application.common.tenant import RequestTenantContext
    from lpg.infrastructure.persistence.repositories.accounting import (
        SqlAlchemyInvoiceRepository,
    )
    from lpg.infrastructure.persistence.repositories.order import SqlAlchemyOrderRepository
    from lpg.infrastructure.persistence.repositories.tenant import (
        SqlAlchemyTenantConfigurationRepository,
    )
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

    async for session in database.open_session(tenant_id=event.tenant_id):
        tenant_context = RequestTenantContext(tenant_id=event.tenant_id)
        async with SqlAlchemyUnitOfWork(session, tenant_context) as uow:
            use_case = GenerateInvoiceForOrderUseCase(
                invoice_repository=SqlAlchemyInvoiceRepository(uow),
                order_repository=SqlAlchemyOrderRepository(uow),
                tenant_config_repository=SqlAlchemyTenantConfigurationRepository(uow),
            )
            await use_case.execute(
                tenant_id=event.tenant_id,
                order_id=event.order_id,
                delivered_at=event.delivered_at,
            )
            await uow.commit()
