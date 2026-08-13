"""FastAPI dependency providers for the dashboard read model.

`GetDashboardSummaryUseCase` composes repository ports from several bounded
contexts (see its own module docstring for why that's architecturally
permitted here). This module wires each of those repositories the same way
their own context's dependency module does, then assembles the use case —
no new repository implementation is introduced.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from lpg.api.v1.dependencies.admin import (
    get_audit_log_repository,
    get_cylinder_type_repository,
    get_price_list_repository,
    get_warehouse_repository,
)
from lpg.api.v1.dependencies.customer import get_customer_repository
from lpg.api.v1.dependencies.delivery import get_driver_repository, get_vehicle_repository
from lpg.api.v1.dependencies.inventory import get_inventory_location_repository
from lpg.application.audit.ports import AuditLogRepository
from lpg.application.customer.ports import CustomerRepository
from lpg.application.dashboard.get_dashboard_summary import GetDashboardSummaryUseCase
from lpg.application.delivery.ports import DriverRepository, VehicleRepository
from lpg.application.inventory.ports import InventoryLocationRepository
from lpg.application.tenant.ports import (
    CylinderTypeRepository,
    PriceListRepository,
    WarehouseRepository,
)


def get_dashboard_summary_use_case(
    customer_repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
    driver_repository: Annotated[DriverRepository, Depends(get_driver_repository)],
    vehicle_repository: Annotated[VehicleRepository, Depends(get_vehicle_repository)],
    warehouse_repository: Annotated[WarehouseRepository, Depends(get_warehouse_repository)],
    cylinder_type_repository: Annotated[
        CylinderTypeRepository, Depends(get_cylinder_type_repository)
    ],
    inventory_location_repository: Annotated[
        InventoryLocationRepository, Depends(get_inventory_location_repository)
    ],
    price_list_repository: Annotated[PriceListRepository, Depends(get_price_list_repository)],
    audit_log_repository: Annotated[AuditLogRepository, Depends(get_audit_log_repository)],
) -> GetDashboardSummaryUseCase:
    return GetDashboardSummaryUseCase(
        customer_repository=customer_repository,
        driver_repository=driver_repository,
        vehicle_repository=vehicle_repository,
        warehouse_repository=warehouse_repository,
        cylinder_type_repository=cylinder_type_repository,
        inventory_location_repository=inventory_location_repository,
        price_list_repository=price_list_repository,
        audit_log_repository=audit_log_repository,
    )
