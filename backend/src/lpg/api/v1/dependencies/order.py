"""FastAPI dependency providers for the order bounded context."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends

from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work, get_unit_of_work_factory
from lpg.application.common.ports import FileStorage, JobQueuePort, UnitOfWork
from lpg.application.order.ports import (
    CancellationRecordRepository,
    CreditLimitEvaluator,
    CylinderCapPolicy,
    OrderRepository,
    ProofOfDeliveryRepository,
)
from lpg.application.order.use_cases import CancelOrderUseCase
from lpg.infrastructure.idempotency.service import IdempotencyService

if TYPE_CHECKING:
    from lpg.api.app import AppState
    from lpg.config.settings import Settings


def get_order_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> OrderRepository:
    from lpg.infrastructure.persistence.repositories.order import SqlAlchemyOrderRepository

    return SqlAlchemyOrderRepository(unit_of_work)  # type: ignore[arg-type]


def get_cancellation_record_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> CancellationRecordRepository:
    from lpg.infrastructure.persistence.repositories.order import (
        SqlAlchemyCancellationRecordRepository,
    )

    return SqlAlchemyCancellationRecordRepository(unit_of_work)  # type: ignore[arg-type]


def get_proof_of_delivery_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> ProofOfDeliveryRepository:
    from lpg.infrastructure.persistence.repositories.order import (
        SqlAlchemyProofOfDeliveryRepository,
    )

    return SqlAlchemyProofOfDeliveryRepository(unit_of_work)  # type: ignore[arg-type]


def get_cylinder_cap_policy() -> CylinderCapPolicy:
    from lpg.infrastructure.order.policies import PermissiveCylinderCapPolicy

    return PermissiveCylinderCapPolicy()


def get_credit_limit_evaluator() -> CreditLimitEvaluator:
    from lpg.infrastructure.order.policies import PermissiveCreditLimitEvaluator

    return PermissiveCreditLimitEvaluator()


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


def get_file_storage() -> FileStorage:
    state, _settings = _get_app_state_and_settings()
    if state.storage is None:
        msg = "FileStorage is not configured — the application lifespan has not run."
        raise RuntimeError(msg)
    return state.storage


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
