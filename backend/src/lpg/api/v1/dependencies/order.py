"""FastAPI dependency providers for the order bounded context."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends

from lpg.api.v1.dependencies.accounting import get_invoice_repository
from lpg.api.v1.dependencies.admin import (
    get_cylinder_type_repository,
    get_price_list_repository,
    get_tenant_configuration_repository,
)
from lpg.api.v1.dependencies.cylinder_ledger import get_cylinder_ledger_repository
from lpg.api.v1.dependencies.identity import get_current_principal
from lpg.api.v1.dependencies.tenant import get_tenant_context
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work, get_unit_of_work_factory
from lpg.application.accounting.ports import InvoiceRepository
from lpg.application.common.ports import FileStorage, JobQueuePort, TenantContext, UnitOfWork
from lpg.application.cylinder_ledger.ports import CylinderLedgerRepository
from lpg.application.identity.ports import AuthenticatedPrincipal
from lpg.application.order.booking_policies import (
    LedgerCylinderCapPolicy,
    OutstandingBalanceCreditLimitEvaluator,
)
from lpg.application.order.gst_snapshot import OrderGstSnapshotter
from lpg.application.order.orderable import OrderableCylinderTypes
from lpg.application.order.ports import (
    BranchStockReader,
    CancellationRecordRepository,
    CreditLimitEvaluator,
    CustomerOpenOrderReader,
    CylinderCapPolicy,
    DeliveryCodeStore,
    OrderCustomerDirectory,
    OrderNumberSequence,
    OrderRepository,
    ProofOfDeliveryRepository,
)
from lpg.application.order.reminders import Notifier, OrderReminderRepository
from lpg.application.order.use_cases import CancelOrderUseCase
from lpg.application.tenant.ports import (
    CylinderTypeRepository,
    PriceListRepository,
    TenantConfigurationRepository,
)
from lpg.infrastructure.idempotency.service import IdempotencyService

if TYPE_CHECKING:
    from lpg.api.app import AppState
    from lpg.config.settings import Settings


def get_order_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> OrderRepository:
    from lpg.infrastructure.persistence.repositories.order import SqlAlchemyOrderRepository

    return SqlAlchemyOrderRepository(unit_of_work)  # type: ignore[arg-type]


def get_order_number_sequence(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> OrderNumberSequence:
    from lpg.infrastructure.persistence.repositories.reference_number import (
        SqlAlchemyReferenceNumberSequence,
    )

    return SqlAlchemyReferenceNumberSequence(
        unit_of_work,  # type: ignore[arg-type]
        principal.tenant_id,
        entity_type="order",
        prefix="ORD",
    )


def get_cancellation_record_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> CancellationRecordRepository:
    from lpg.infrastructure.persistence.repositories.order import (
        SqlAlchemyCancellationRecordRepository,
    )

    return SqlAlchemyCancellationRecordRepository(unit_of_work)  # type: ignore[arg-type]


def get_order_customer_directory(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> OrderCustomerDirectory:
    from lpg.infrastructure.persistence.repositories.order import (
        SqlAlchemyOrderCustomerDirectory,
    )

    return SqlAlchemyOrderCustomerDirectory(unit_of_work)  # type: ignore[arg-type]


def get_proof_of_delivery_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> ProofOfDeliveryRepository:
    from lpg.infrastructure.persistence.repositories.order import (
        SqlAlchemyProofOfDeliveryRepository,
    )

    return SqlAlchemyProofOfDeliveryRepository(unit_of_work)  # type: ignore[arg-type]


def get_branch_stock_reader(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> BranchStockReader:
    from lpg.infrastructure.persistence.repositories.order import SqlAlchemyBranchStockReader

    return SqlAlchemyBranchStockReader(unit_of_work)  # type: ignore[arg-type]


def get_orderable_cylinder_types(
    cylinder_types: Annotated[CylinderTypeRepository, Depends(get_cylinder_type_repository)],
    price_lists: Annotated[PriceListRepository, Depends(get_price_list_repository)],
    stock: Annotated[BranchStockReader, Depends(get_branch_stock_reader)],
) -> OrderableCylinderTypes:
    return OrderableCylinderTypes(cylinder_types, price_lists, stock)


def get_order_gst_snapshotter(
    cylinder_types: Annotated[CylinderTypeRepository, Depends(get_cylinder_type_repository)],
    configuration: Annotated[
        TenantConfigurationRepository, Depends(get_tenant_configuration_repository)
    ],
) -> OrderGstSnapshotter:
    return OrderGstSnapshotter(cylinder_types, configuration)


def get_customer_open_order_reader(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> CustomerOpenOrderReader:
    from lpg.infrastructure.persistence.repositories.order import (
        SqlAlchemyCustomerOpenOrderReader,
    )

    return SqlAlchemyCustomerOpenOrderReader(unit_of_work)  # type: ignore[arg-type]


def get_cylinder_cap_policy(
    configuration: Annotated[
        TenantConfigurationRepository, Depends(get_tenant_configuration_repository)
    ],
    ledger_repository: Annotated[CylinderLedgerRepository, Depends(get_cylinder_ledger_repository)],
    open_orders: Annotated[CustomerOpenOrderReader, Depends(get_customer_open_order_reader)],
) -> CylinderCapPolicy:
    return LedgerCylinderCapPolicy(configuration, ledger_repository, open_orders)


def get_credit_limit_evaluator(
    configuration: Annotated[
        TenantConfigurationRepository, Depends(get_tenant_configuration_repository)
    ],
    invoice_repository: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
) -> CreditLimitEvaluator:
    return OutstandingBalanceCreditLimitEvaluator(configuration, invoice_repository)


def _get_app_state_and_settings() -> tuple[AppState, Settings]:
    """Deferred import, same reason as `dependencies/identity.py`'s
    identical helper: `lpg.api.app` has a module-level `app = create_app()`
    side effect that must not run at import time here.
    """
    from lpg.api.app import get_app_state
    from lpg.config.settings import get_settings

    return get_app_state(), get_settings()


def get_job_queue() -> JobQueuePort:
    from lpg.infrastructure.order.job_queue_adapter import OrderJobQueueAdapter

    state, _settings = _get_app_state_and_settings()
    if state.job_queue is None:
        msg = "JobQueue is not configured — the application lifespan has not run."
        raise RuntimeError(msg)
    return OrderJobQueueAdapter(state.job_queue)


def get_idempotency_service() -> IdempotencyService:
    """Mirrors `dependencies/identity.py::get_otp_store()`'s shape — the
    concrete storage/coordination primitive built fresh per request from
    `AppState.redis`.
    """
    state, _settings = _get_app_state_and_settings()
    if state.redis is None:
        msg = "RedisClient is not configured — the application lifespan has not run."
        raise RuntimeError(msg)
    return IdempotencyService(state.redis)


def get_delivery_code_store() -> DeliveryCodeStore:
    """The customer-readable copy of each pending delivery code, in Redis."""
    from lpg.infrastructure.order.delivery_code_store import RedisDeliveryCodeStore

    state, _settings = _get_app_state_and_settings()
    if state.redis is None:
        msg = "RedisClient is not configured — the application lifespan has not run."
        raise RuntimeError(msg)
    return RedisDeliveryCodeStore(state.redis)


def get_file_storage(
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> FileStorage:
    """Storage limited to the caller's own `tenant/{id}/` prefix, so a
    client-supplied blob reference can never reach another agency's files."""
    from lpg.infrastructure.storage.scoped import TenantScopedFileStorage

    state, _settings = _get_app_state_and_settings()
    if state.storage is None:
        msg = "FileStorage is not configured — the application lifespan has not run."
        raise RuntimeError(msg)
    return TenantScopedFileStorage(state.storage, tenant_context.tenant_id)


def get_cancel_order_use_case_factory(
    unit_of_work_factory: Annotated[
        Callable[[], AbstractAsyncContextManager[UnitOfWork]], Depends(get_unit_of_work_factory)
    ],
) -> Callable[[], AbstractAsyncContextManager[CancelOrderUseCase]]:
    """For `BulkCancelOrdersUseCase`'s synchronous path only — every other
    endpoint should keep depending on `get_order_repository` +
    `get_unit_of_work` directly. See `get_unit_of_work_factory`'s docstring
    for why bulk-cancel specifically needs a fresh transaction per order.
    """

    @asynccontextmanager
    async def _factory() -> AsyncIterator[CancelOrderUseCase]:
        from lpg.infrastructure.persistence.repositories.inventory import (
            SqlAlchemyInventoryLocationRepository,
        )
        from lpg.infrastructure.persistence.repositories.order import (
            SqlAlchemyCancellationRecordRepository,
            SqlAlchemyOrderRepository,
        )
        from lpg.infrastructure.persistence.repositories.route import SqlAlchemyRouteRepository

        async with unit_of_work_factory() as uow:
            order_repository = SqlAlchemyOrderRepository(uow)  # type: ignore[arg-type]
            route_repository = SqlAlchemyRouteRepository(uow)  # type: ignore[arg-type]
            inventory_repository = SqlAlchemyInventoryLocationRepository(
                uow  # type: ignore[arg-type]
            )
            cancellation_repository = SqlAlchemyCancellationRecordRepository(
                uow  # type: ignore[arg-type]
            )
            yield CancelOrderUseCase(
                order_repository,
                route_repository,
                inventory_repository,
                cancellation_repository,
                uow,
            )

    return _factory


def get_order_reminder_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> OrderReminderRepository:
    from lpg.infrastructure.persistence.repositories.order_reminder import (
        SqlAlchemyOrderReminderRepository,
    )

    return SqlAlchemyOrderReminderRepository(unit_of_work)  # type: ignore[arg-type]


def get_reminder_notifier() -> Notifier | None:
    """The notifier that delivers a staff reminder to the customer's app, or
    `None` before the app has started (tests)."""
    from lpg.api.app import get_app_state
    from lpg.infrastructure.notification.delivery import InAppFirstNotifier

    state = get_app_state()
    if state.database is None:
        return None
    return InAppFirstNotifier(state.database, state.event_dispatcher, state.job_queue)
