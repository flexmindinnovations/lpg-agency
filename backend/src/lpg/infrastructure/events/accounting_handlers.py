"""Domain-event handlers that generate invoices.

Like `cylinder_ledger_handlers`, this lives in infrastructure because it
opens its own database session and builds concrete repositories.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from lpg.config.logging import get_logger
from lpg.domain.order.order import BookingCancelled, CylinderDelivered

if TYPE_CHECKING:
    from lpg.domain.common.base import DomainEvent
    from lpg.infrastructure.events.dispatcher import DomainEventDispatcher
    from lpg.infrastructure.persistence.database import Database

_SYSTEM_ACTOR_ID = uuid.UUID(int=0)
_logger = get_logger(__name__)


def register_accounting_handlers(dispatcher: DomainEventDispatcher, database: Database) -> None:
    """Subscribe Accounting projections to domain events."""

    async def _on_cylinder_delivered(event: DomainEvent) -> None:
        assert isinstance(event, CylinderDelivered)
        await _generate_invoice_for_delivered_order(database, event)

    async def _on_booking_cancelled(event: DomainEvent) -> None:
        assert isinstance(event, BookingCancelled)
        if event.cancellation_charge is not None and event.cancellation_charge > 0:
            await _generate_invoice_for_delivered_order(database, event)

    dispatcher.register(CylinderDelivered, _on_cylinder_delivered)
    dispatcher.register(BookingCancelled, _on_booking_cancelled)


async def _generate_invoice_for_delivered_order(
    database: Database, event: CylinderDelivered | BookingCancelled
) -> None:
    """Run invoice generation in its own tenant-scoped transaction.

    A `GstNotConfiguredError` is logged, not raised: the delivery (or
    cancellation) itself already committed and must stand. The order then
    appears under "Invoices on hold" on the Invoices page, where it is
    issued once GST is configured (DA-06).
    """
    from lpg.application.accounting.gst import GstNotConfiguredError
    from lpg.application.accounting.use_cases import GenerateInvoiceForOrderUseCase
    from lpg.application.common.tenant import RequestTenantContext
    from lpg.config.settings import get_settings
    from lpg.infrastructure.persistence.repositories.accounting import (
        SqlAlchemyInvoiceRepository,
        SqlAlchemyOnlinePaymentRepository,
    )
    from lpg.infrastructure.persistence.repositories.customer import SqlAlchemyCustomerRepository
    from lpg.infrastructure.persistence.repositories.order import (
        SqlAlchemyOrderRepository,
        SqlAlchemyProofOfDeliveryRepository,
    )
    from lpg.infrastructure.persistence.repositories.reference_number import (
        SqlAlchemyReferenceNumberSequence,
    )
    from lpg.infrastructure.persistence.repositories.tenant import (
        SqlAlchemyCylinderTypeRepository,
        SqlAlchemyTenantConfigurationRepository,
        SqlAlchemyTenantRepository,
    )
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
    from lpg.infrastructure.security.field_encryption import FernetFieldEncryptor

    async for session in database.open_session(tenant_id=event.tenant_id):
        tenant_context = RequestTenantContext(tenant_id=event.tenant_id)
        async with SqlAlchemyUnitOfWork(session, tenant_context) as uow:
            field_encryptor = FernetFieldEncryptor(get_settings())
            use_case = GenerateInvoiceForOrderUseCase(
                invoice_repository=SqlAlchemyInvoiceRepository(uow),
                order_repository=SqlAlchemyOrderRepository(uow),
                customer_repository=SqlAlchemyCustomerRepository(uow, field_encryptor),
                tenant_config_repository=SqlAlchemyTenantConfigurationRepository(uow),
                invoice_number_sequence=SqlAlchemyReferenceNumberSequence(
                    uow, event.tenant_id, entity_type="invoice", prefix="INV", include_year=True
                ),
                cylinder_type_repository=SqlAlchemyCylinderTypeRepository(uow),
                tenant_repository=SqlAlchemyTenantRepository(uow),
                online_payment_repository=SqlAlchemyOnlinePaymentRepository(uow),
                proof_of_delivery_reader=SqlAlchemyProofOfDeliveryRepository(uow),
            )
            try:
                if isinstance(event, CylinderDelivered):
                    await use_case.execute(
                        tenant_id=event.tenant_id,
                        order_id=event.order_id,
                        delivered_at=event.delivered_at,
                    )
                else:
                    await use_case.execute_cancellation_charge(
                        event.tenant_id,
                        event.order_id,
                        event.cancellation_charge or Decimal("0"),
                        event.occurred_at,
                    )
            except GstNotConfiguredError as exc:
                _logger.error(
                    "invoice_held_gst_not_configured",
                    order_id=str(event.order_id),
                    tenant_id=str(event.tenant_id),
                    detail=exc.message,
                )
                return
            await uow.commit()
