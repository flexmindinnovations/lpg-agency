"""New-agency setup checklist (QA finding DA-32).

A freshly provisioned agency used to land on empty pages with nothing saying
what to do first, or that customers cannot order until prices and stock exist
and invoices carry 0% GST until a rate is set. This reports, per setup step,
whether the agency has done it, so Home can show a checklist that links to each
page and ticks itself off.

Read-only and tenant-scoped: every repository here is the request's own
RLS-scoped one, so the answer can only ever describe the caller's agency.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.application.accounting.payment_profile import GetPaymentProfileUseCase
from lpg.application.common.cqrs import Query

if TYPE_CHECKING:
    import uuid

    from lpg.application.delivery.ports import DriverRepository, VehicleRepository
    from lpg.application.identity.ports import StaffUserRepository
    from lpg.application.tenant.ports import (
        BranchRepository,
        CylinderTypeRepository,
        PriceListRepository,
        TenantConfigurationRepository,
        WarehouseRepository,
    )

#: Step keys, in the order an agency should do them. Each one becomes true
#: once the agency has at least one active record of that kind.
SETUP_STEPS = (
    "branch",
    "warehouse",
    "cylinder_types",
    "prices",
    "gst",
    "payments",
    "staff",
    "drivers",
    "vehicles",
)


@dataclass(frozen=True, slots=True)
class SetupProgress:
    done: dict[str, bool]

    @property
    def complete(self) -> bool:
        return all(self.done.values())


@dataclass(frozen=True, slots=True)
class GetSetupProgressQuery(Query):
    tenant_id: uuid.UUID


class GetSetupProgressUseCase:
    def __init__(
        self,
        *,
        branches: BranchRepository,
        warehouses: WarehouseRepository,
        cylinder_types: CylinderTypeRepository,
        prices: PriceListRepository,
        configuration: TenantConfigurationRepository,
        staff: StaffUserRepository,
        drivers: DriverRepository,
        vehicles: VehicleRepository,
    ) -> None:
        self._branches = branches
        self._warehouses = warehouses
        self._cylinder_types = cylinder_types
        self._prices = prices
        self._configuration = configuration
        self._staff = staff
        self._drivers = drivers
        self._vehicles = vehicles

    async def execute(self, query: GetSetupProgressQuery) -> SetupProgress:
        tenant_id = query.tenant_id
        branches = await self._branches.list_for_tenant(tenant_id)
        warehouses = await self._warehouses.list_for_tenant(tenant_id)
        cylinder_types = await self._cylinder_types.list_for_tenant(tenant_id)
        gst = await self._configuration.list_for_tenant_and_key(tenant_id, "gst_rate_percent")
        payment_profile = await GetPaymentProfileUseCase(self._configuration).execute(tenant_id)
        # The agency's first admin always exists; staff means anyone else.
        staff = await self._staff.list_for_tenant(
            tenant_id, exclude_roles=frozenset({"customer", "driver"})
        )
        done = {
            "branch": any(b.is_active for b in branches),
            "warehouse": any(w.is_active for w in warehouses),
            "cylinder_types": any(c.is_active for c in cylinder_types),
            "prices": bool(await self._prices.list_for_tenant(tenant_id)),
            "gst": bool(gst),
            # Customers need to know how to pay: a UPI ID or a bank account is enough.
            "payments": payment_profile.has_upi or payment_profile.has_bank_details,
            "staff": sum(1 for u in staff if u.is_active) > 1,
            "drivers": await self._drivers.count_drivers() > 0,
            "vehicles": await self._vehicles.count_vehicles() > 0,
        }
        return SetupProgress(done={step: done[step] for step in SETUP_STEPS})
