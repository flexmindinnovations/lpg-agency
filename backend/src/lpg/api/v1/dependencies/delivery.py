"""FastAPI dependency providers for the delivery bounded context."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from lpg.api.v1.dependencies.admin import get_tenant_configuration_repository
from lpg.api.v1.dependencies.compliance import get_weighment_record_repository
from lpg.api.v1.dependencies.inventory import (
    get_inventory_location_repository,
    get_reconciliation_record_repository,
)
from lpg.api.v1.dependencies.order import get_order_repository
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.application.common.ports import UnitOfWork
from lpg.application.compliance.ports import WeighmentRecordRepository
from lpg.application.delivery.ports import (
    ComplianceDocumentRepository,
    DriverRepository,
    RouteRepository,
    VehicleRepository,
)
from lpg.application.delivery.use_cases import (
    AssignOrderToRouteUseCase,
    CompleteRouteReconciliationUseCase,
    ConfirmRouteLoadUseCase,
    LoadVehicleForRouteUseCase,
)
from lpg.application.inventory.ports import (
    InventoryLocationRepository,
    ReconciliationRecordRepository,
)
from lpg.application.order.ports import OrderRepository
from lpg.application.tenant.ports import TenantConfigurationRepository

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


def get_compliance_document_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> ComplianceDocumentRepository:
    from lpg.infrastructure.persistence.repositories.compliance_document import (
        SqlAlchemyComplianceDocumentRepository,
    )

    return SqlAlchemyComplianceDocumentRepository(unit_of_work)  # type: ignore[arg-type]


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
    weighment_record_repository: Annotated[
        WeighmentRecordRepository, Depends(get_weighment_record_repository)
    ],
    tenant_config_repository: Annotated[
        TenantConfigurationRepository, Depends(get_tenant_configuration_repository)
    ],
) -> LoadVehicleForRouteUseCase:
    # Both repositories are always passed here — the real app always has
    # Weighment Part 3's opt-in gate wired and *able* to activate, even
    # though it stays a no-op for every tenant that hasn't set
    # `weighment_gate_enabled` (see the use case's own docstring). Optional
    # on the use case's own constructor only so tests that predate this
    # gate don't all need updating.
    return LoadVehicleForRouteUseCase(
        route_repository,
        inventory_location_repository,
        unit_of_work,
        weighment_record_repository,
        tenant_config_repository,
    )


def get_confirm_route_load_use_case(
    route_repository: Annotated[RouteRepository, Depends(get_route_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> ConfirmRouteLoadUseCase:
    return ConfirmRouteLoadUseCase(route_repository, unit_of_work)


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
