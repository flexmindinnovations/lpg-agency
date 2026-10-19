"""Builds the `WhatsAppScope`s the assistant works through: one fresh,
tenant-scoped session and `UnitOfWork` per scope, with every repository the
assistant's tools need bound to it.

The background job is the composition root here (there is no request and no
FastAPI `Depends()`), the same role `bulk_cancel_orders` and the refill cron
play for their own repositories.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from lpg.application.common.tenant import RequestTenantContext
from lpg.application.whatsapp.ports import WhatsAppScope
from lpg.infrastructure.persistence.repositories.ai import SqlAlchemyAssistantRunRepository
from lpg.infrastructure.persistence.repositories.complaint import SqlAlchemyComplaintRepository
from lpg.infrastructure.persistence.repositories.customer import SqlAlchemyCustomerRepository
from lpg.infrastructure.persistence.repositories.driver import SqlAlchemyDriverRepository
from lpg.infrastructure.persistence.repositories.employee import SqlAlchemyEmployeeRepository
from lpg.infrastructure.persistence.repositories.inventory import (
    SqlAlchemyInventoryLocationRepository,
)
from lpg.infrastructure.persistence.repositories.order import (
    SqlAlchemyBranchStockReader,
    SqlAlchemyCancellationRecordRepository,
    SqlAlchemyOrderRepository,
)
from lpg.infrastructure.persistence.repositories.reference_number import (
    SqlAlchemyReferenceNumberSequence,
)
from lpg.infrastructure.persistence.repositories.route import SqlAlchemyRouteRepository
from lpg.infrastructure.persistence.repositories.tenant import (
    SqlAlchemyCylinderTypeRepository,
    SqlAlchemyPriceListRepository,
    SqlAlchemyTenantConfigurationRepository,
)
from lpg.infrastructure.persistence.repositories.vehicle import SqlAlchemyVehicleRepository
from lpg.infrastructure.persistence.repositories.whatsapp import (
    SqlAlchemyWhatsAppConversationRepository,
)
from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

if TYPE_CHECKING:
    import uuid
    from collections.abc import AsyncIterator, Callable, Sequence
    from contextlib import AbstractAsyncContextManager

    from lpg.application.customer.ports import FieldEncryptor
    from lpg.domain.common.base import DomainEvent
    from lpg.infrastructure.events.dispatcher import DomainEventDispatcher
    from lpg.infrastructure.persistence.database import Database


class _ComplaintUnitOfWork:
    """`ComplaintUnitOfWork` over the scope's own `SqlAlchemyUnitOfWork`, the
    same adapter `api/v1/dependencies/complaint.py` gives the complaints
    router."""

    def __init__(self, uow: SqlAlchemyUnitOfWork) -> None:
        self._uow = uow

    @property
    def complaints(self) -> SqlAlchemyComplaintRepository:
        return SqlAlchemyComplaintRepository(self._uow)

    async def __aenter__(self) -> _ComplaintUnitOfWork:
        await self._uow.__aenter__()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self._uow.__aexit__(*exc_info)

    async def commit(self) -> None:
        await self._uow.commit()

    async def rollback(self) -> None:
        await self._uow.rollback()

    def collect_events(self) -> Sequence[DomainEvent]:
        return self._uow.collect_events()


def build_scope_factory(
    *,
    database: Database,
    tenant_id: uuid.UUID,
    field_encryptor: FieldEncryptor,
    event_dispatcher: DomainEventDispatcher | None,
    actor_id: uuid.UUID | None = None,
) -> Callable[[], AbstractAsyncContextManager[WhatsAppScope]]:
    """A factory of scopes for `tenant_id`. `actor_id` is stamped on audit
    rows; the job sets it once it knows which customer is writing."""
    tenant_context = RequestTenantContext(
        tenant_id=tenant_id, user_id=actor_id, user_display_name="WhatsApp assistant"
    )

    @asynccontextmanager
    async def open_scope() -> AsyncIterator[WhatsAppScope]:
        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(
                session, tenant_context, event_dispatcher=event_dispatcher
            ) as uow:
                yield WhatsAppScope(
                    unit_of_work=uow,
                    conversations=SqlAlchemyWhatsAppConversationRepository(uow),
                    customers=SqlAlchemyCustomerRepository(uow, field_encryptor),
                    orders=SqlAlchemyOrderRepository(uow),
                    order_numbers=SqlAlchemyReferenceNumberSequence(
                        uow, tenant_id, entity_type="order", prefix="ORD"
                    ),
                    cancellations=SqlAlchemyCancellationRecordRepository(uow),
                    cylinder_types=SqlAlchemyCylinderTypeRepository(uow),
                    price_lists=SqlAlchemyPriceListRepository(uow),
                    tenant_configuration=SqlAlchemyTenantConfigurationRepository(uow),
                    routes=SqlAlchemyRouteRepository(uow),
                    drivers=SqlAlchemyDriverRepository(uow),
                    vehicles=SqlAlchemyVehicleRepository(uow),
                    employees=SqlAlchemyEmployeeRepository(uow),
                    inventory=SqlAlchemyInventoryLocationRepository(uow),
                    branch_stock=SqlAlchemyBranchStockReader(uow),
                    complaints=_ComplaintUnitOfWork(uow),
                    complaint_numbers=SqlAlchemyReferenceNumberSequence(
                        uow, tenant_id, entity_type="complaint", prefix="CMP"
                    ),
                    assistant_runs=SqlAlchemyAssistantRunRepository(uow),
                )

    return open_scope
