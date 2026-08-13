"""`GetDashboardSummaryUseCase` — a single consolidated read for the
Dashboard's KPI cards, fleet/inventory charts, price cards, and recent
activity feed.

This is a read-model composition, not an aggregate operation: it has no
domain invariants of its own, so it directly composes the existing
repository ports of the bounded contexts it reports on (customer, delivery,
tenant, inventory, audit) rather than owning a new aggregate — the same
"read model without an aggregate" reasoning `application/audit/ports.py`
documents. Composing ports from multiple bounded contexts in one
application-layer use case is architecturally permitted here: the
`import-linter` contracts in this codebase enforce layer-to-layer direction
(`api -> application -> domain`), not context-to-context isolation within a
layer (ADR-014's "CQRS in-process via explicit application services").
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from lpg.domain.tenant.price_list import EffectivePriceResolver

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence
    from decimal import Decimal

    from lpg.application.audit.ports import AuditLogPage, AuditLogRepository
    from lpg.application.customer.ports import CustomerRepository
    from lpg.application.delivery.ports import DriverRepository, VehicleRepository
    from lpg.application.inventory.ports import InventoryLocationRepository
    from lpg.application.tenant.ports import (
        CylinderTypeRepository,
        PriceListRepository,
        WarehouseRepository,
    )
    from lpg.domain.tenant.cylinder_type import CylinderType

#: Price cards report the domestic tariff — the default customer type a
#: walk-in/phone booking uses when none is specified, and the only one with
#: guaranteed tenant-wide coverage (commercial/industrial/government pricing
#: is frequently branch- or contract-specific and may have no tenant-wide
#: default entry at all).
_PRICE_CARD_CUSTOMER_TYPE = "domestic"


@dataclass(frozen=True, slots=True)
class CylinderTypePriceCard:
    cylinder_type_id: uuid.UUID
    name: str
    weight_kg: Decimal
    customer_type: str
    #: `None` when no price list entry has been configured yet for this
    #: cylinder type/customer type — a gap to surface, not an error.
    price: Decimal | None


@dataclass(frozen=True, slots=True)
class DashboardSummary:
    customer_count: int
    driver_count: int
    vehicle_count: int
    vehicles_by_status: dict[str, int]
    warehouse_count: int
    cylinder_type_count: int
    inventory_by_status: dict[str, int]
    price_cards: Sequence[CylinderTypePriceCard]
    recent_activity: AuditLogPage


@dataclass(frozen=True, slots=True)
class GetDashboardSummaryQuery:
    tenant_id: uuid.UUID
    recent_activity_limit: int = 8


class GetDashboardSummaryUseCase:
    def __init__(
        self,
        customer_repository: CustomerRepository,
        driver_repository: DriverRepository,
        vehicle_repository: VehicleRepository,
        warehouse_repository: WarehouseRepository,
        cylinder_type_repository: CylinderTypeRepository,
        inventory_location_repository: InventoryLocationRepository,
        price_list_repository: PriceListRepository,
        audit_log_repository: AuditLogRepository,
    ) -> None:
        self._customer_repository = customer_repository
        self._driver_repository = driver_repository
        self._vehicle_repository = vehicle_repository
        self._warehouse_repository = warehouse_repository
        self._cylinder_type_repository = cylinder_type_repository
        self._inventory_location_repository = inventory_location_repository
        self._price_list_repository = price_list_repository
        self._audit_log_repository = audit_log_repository

    async def execute(self, query: GetDashboardSummaryQuery) -> DashboardSummary:
        customer_count = await self._customer_repository.count_customers()
        driver_count = await self._driver_repository.count_drivers()
        vehicle_count = await self._vehicle_repository.count_vehicles()
        vehicles_by_status = await self._vehicle_repository.count_by_status()
        warehouses = await self._warehouse_repository.list_for_tenant(query.tenant_id)
        cylinder_types = await self._cylinder_type_repository.list_for_tenant(query.tenant_id)
        inventory_by_status = await self._inventory_location_repository.get_balance_summary()
        price_cards = await self._build_price_cards(query.tenant_id, cylinder_types)
        recent_activity = await self._audit_log_repository.get_page(
            query.tenant_id, limit=query.recent_activity_limit
        )

        return DashboardSummary(
            customer_count=customer_count,
            driver_count=driver_count,
            vehicle_count=vehicle_count,
            vehicles_by_status=vehicles_by_status,
            warehouse_count=len(warehouses),
            cylinder_type_count=len(cylinder_types),
            inventory_by_status=inventory_by_status,
            price_cards=price_cards,
            recent_activity=recent_activity,
        )

    async def _build_price_cards(
        self, tenant_id: uuid.UUID, cylinder_types: Sequence[CylinderType]
    ) -> list[CylinderTypePriceCard]:
        now = datetime.now(UTC)
        cards: list[CylinderTypePriceCard] = []
        for cylinder_type in cylinder_types:
            if not cylinder_type.is_active:
                continue
            entries = await self._price_list_repository.list_for_tenant_and_cylinder_type(
                tenant_id, cylinder_type.id, _PRICE_CARD_CUSTOMER_TYPE
            )
            effective = EffectivePriceResolver.resolve(
                entries,
                cylinder_type_id=cylinder_type.id,
                customer_type=_PRICE_CARD_CUSTOMER_TYPE,
                branch_id=None,
                at=now,
            )
            cards.append(
                CylinderTypePriceCard(
                    cylinder_type_id=cylinder_type.id,
                    name=cylinder_type.name,
                    weight_kg=cylinder_type.weight_kg,
                    customer_type=_PRICE_CARD_CUSTOMER_TYPE,
                    price=effective.price if effective is not None else None,
                )
            )
        return cards
