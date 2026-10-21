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

from lpg.api.v1.dependencies.accounting import (
    get_cash_handover_repository,
    get_uninvoiced_order_reader,
)
from lpg.api.v1.dependencies.admin import (
    get_audit_log_repository,
    get_cylinder_type_repository,
    get_price_list_repository,
    get_tenant_configuration_repository,
    get_warehouse_repository,
)
from lpg.api.v1.dependencies.customer import get_customer_repository
from lpg.api.v1.dependencies.delivery import get_driver_repository, get_vehicle_repository
from lpg.api.v1.dependencies.inventory import (
    get_inventory_location_repository,
    get_reorder_policy_repository,
)
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.application.accounting.ports import CashHandoverRepository, UninvoicedOrderReader
from lpg.application.audit.ports import AuditLogRepository
from lpg.application.common.ports import UnitOfWork
from lpg.application.customer.ports import CustomerRepository
from lpg.application.dashboard.get_dashboard_summary import GetDashboardSummaryUseCase
from lpg.application.dashboard.get_operations_snapshot import GetOperationsSnapshotUseCase
from lpg.application.delivery.ports import DriverRepository, VehicleRepository
from lpg.application.inventory.ports import InventoryLocationRepository, ReorderPolicyRepository
from lpg.application.tenant.ports import (
    CylinderTypeRepository,
    PriceListRepository,
    TenantConfigurationRepository,
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


def get_operations_snapshot_use_case(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    tenant_config_repository: Annotated[
        TenantConfigurationRepository, Depends(get_tenant_configuration_repository)
    ],
    reorder_policy_repository: Annotated[
        ReorderPolicyRepository, Depends(get_reorder_policy_repository)
    ],
    cash_handover_repository: Annotated[
        CashHandoverRepository, Depends(get_cash_handover_repository)
    ],
    uninvoiced_order_reader: Annotated[UninvoicedOrderReader, Depends(get_uninvoiced_order_reader)],
) -> GetOperationsSnapshotUseCase:
    import typing

    from lpg.infrastructure.persistence.repositories.dashboard import SqlAlchemyOperationsReader
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

    reader = SqlAlchemyOperationsReader(
        typing.cast("SqlAlchemyUnitOfWork", unit_of_work),
        reorder_policy_repository=reorder_policy_repository,
        cash_handover_repository=cash_handover_repository,
        uninvoiced_order_reader=uninvoiced_order_reader,
    )
    return GetOperationsSnapshotUseCase(reader, tenant_config_repository)
