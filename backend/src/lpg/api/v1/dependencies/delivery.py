"""FastAPI dependency providers for the delivery bounded context."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from lpg.api.v1.dependencies.inventory import (
    get_inventory_location_repository,
    get_reconciliation_record_repository,
)
from lpg.api.v1.dependencies.order import get_order_repository
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.application.common.ports import UnitOfWork
from lpg.application.delivery.ports import DriverRepository, RouteRepository, VehicleRepository
from lpg.application.delivery.use_cases import (
    AssignOrderToRouteUseCase,
    CompleteRouteReconciliationUseCase,
    LoadVehicleForRouteUseCase,
)
from lpg.application.inventory.ports import (
    InventoryLocationRepository,
    ReconciliationRecordRepository,
)
from lpg.application.order.ports import OrderRepository

# `Annotated[...]`-typed FastAPI dependency-provider parameters need every
# name resolvable at *runtime* (FastAPI/Pydantic inspect them to build the
# dependency graph and the OpenAPI schema) — unlike ordinary type hints,
# these imports cannot be `TYPE_CHECKING`-only, matching `dependencies/
# order.py`'s own established pattern for the identical reason.


def get_driver_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> DriverRepository:
    from lpg.infrastructure.persistence.repositories.driver import (
        SqlAlchemyDriverRepository,
    )

    return SqlAlchemyDriverRepository(unit_of_work)  # type: ignore[arg-type]


def get_vehicle_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> VehicleRepository:
    from lpg.infrastructure.persistence.repositories.vehicle import (
        SqlAlchemyVehicleRepository,
    )

    return SqlAlchemyVehicleRepository(unit_of_work)  # type: ignore[arg-type]


def get_route_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> RouteRepository:
    from lpg.infrastructure.persistence.repositories.route import (
        SqlAlchemyRouteRepository,
    )

    return SqlAlchemyRouteRepository(unit_of_work)  # type: ignore[arg-type]


def get_assign_order_to_route_use_case(
    route_repository: Annotated[RouteRepository, Depends(get_route_repository)],
    order_repository: Annotated[OrderRepository, Depends(get_order_repository)],
    inventory_location_repository: Annotated[
        InventoryLocationRepository, Depends(get_inventory_location_repository)
    ],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> AssignOrderToRouteUseCase:
    return AssignOrderToRouteUseCase(
        route_repository, order_repository, inventory_location_repository, unit_of_work
    )


def get_load_vehicle_for_route_use_case(
    route_repository: Annotated[RouteRepository, Depends(get_route_repository)],
    inventory_location_repository: Annotated[
        InventoryLocationRepository, Depends(get_inventory_location_repository)
    ],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> LoadVehicleForRouteUseCase:
    return LoadVehicleForRouteUseCase(route_repository, inventory_location_repository, unit_of_work)


def get_complete_route_reconciliation_use_case(
    route_repository: Annotated[RouteRepository, Depends(get_route_repository)],
    inventory_location_repository: Annotated[
        InventoryLocationRepository, Depends(get_inventory_location_repository)
    ],
    reconciliation_repository: Annotated[
        ReconciliationRecordRepository, Depends(get_reconciliation_record_repository)
    ],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> CompleteRouteReconciliationUseCase:
    return CompleteRouteReconciliationUseCase(
        route_repository, inventory_location_repository, reconciliation_repository, unit_of_work
    )
