"""Which cylinder types a customer can order right now, at a branch.

A cylinder type is orderable only when all of these hold:

- it is active in the tenant's catalog;
- a price is in effect for the customer's type at the branch (a branch
  override, else the tenant-wide default);
- the branch still has filled cylinders of it that no open order has
  already claimed (`BranchStockReader`).

The booking forms list only what `list()` returns, and `require()` is the
server-side guard `CreateOrderUseCase` and `ConfirmOrderUseCase` run, so a
stale form, the API or the WhatsApp assistant cannot book what the forms
would hide.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, NoReturn

from lpg.application.common.errors import CylinderNotOrderableError
from lpg.domain.tenant.price_list import EffectivePriceResolver

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence
    from decimal import Decimal

    from lpg.application.order.ports import BranchStockReader
    from lpg.application.tenant.ports import CylinderTypeRepository, PriceListRepository
    from lpg.domain.tenant.cylinder_type import CylinderType
    from lpg.domain.tenant.price_list import PriceListEntry


@dataclass(frozen=True, slots=True)
class OrderableCylinderType:
    cylinder_type_id: uuid.UUID
    name: str
    weight_kg: Decimal
    unit_price: Decimal
    available_quantity: int


class OrderableCylinderTypes:
    def __init__(
        self,
        cylinder_types: CylinderTypeRepository,
        price_lists: PriceListRepository,
        stock: BranchStockReader,
    ) -> None:
        self._cylinder_types = cylinder_types
        self._price_lists = price_lists
        self._stock = stock

    async def list(
        self,
        *,
        tenant_id: uuid.UUID,
        branch_id: uuid.UUID,
        customer_type: str,
        exclude_order_id: uuid.UUID | None = None,
    ) -> list[OrderableCylinderType]:
        """Every orderable cylinder type, sorted by name."""
        cylinder_types = await self._cylinder_types.list_for_tenant(tenant_id)
        prices = await self._price_lists.list_for_tenant(tenant_id)
        stock = await self._stock.available_filled_by_cylinder_type(
            branch_id, exclude_order_id=exclude_order_id
        )
        now = datetime.now(UTC)
        orderable = []
        for cylinder_type in cylinder_types:
            price = _price(prices, cylinder_type, customer_type, branch_id, now)
            available = stock.get(cylinder_type.id, 0)
            if cylinder_type.is_active and price is not None and available > 0:
                orderable.append(
                    OrderableCylinderType(
                        cylinder_type_id=cylinder_type.id,
                        name=cylinder_type.name,
                        weight_kg=cylinder_type.weight_kg,
                        unit_price=price,
                        available_quantity=available,
                    )
                )
        return sorted(orderable, key=lambda option: option.name.lower())

    async def require(
        self,
        *,
        tenant_id: uuid.UUID,
        branch_id: uuid.UUID,
        customer_type: str,
        lines: Sequence[tuple[uuid.UUID, int]],
        exclude_order_id: uuid.UUID | None = None,
    ) -> None:
        """Raise `CylinderNotOrderableError` naming the first line that can't
        be ordered, and why. Quantities of the same type on several lines
        are added up before the stock check.

        Takes the branch's booking lock first and keeps it until the caller's
        transaction commits, so the check and the booking it allows happen
        as one step for concurrent bookings at the same branch.
        """
        requested: dict[uuid.UUID, int] = defaultdict(int)
        for cylinder_type_id, quantity in lines:
            requested[cylinder_type_id] += quantity

        await self._stock.lock_branch_for_booking(branch_id)
        prices = await self._price_lists.list_for_tenant(tenant_id)
        stock = await self._stock.available_filled_by_cylinder_type(
            branch_id, exclude_order_id=exclude_order_id
        )
        now = datetime.now(UTC)
        for cylinder_type_id, quantity in requested.items():
            cylinder_type = await self._cylinder_types.get(cylinder_type_id)
            if cylinder_type is None or not cylinder_type.is_active:
                name = cylinder_type.name if cylinder_type is not None else "This cylinder type"
                _reject(f"{name} is not available for booking.", cylinder_type_id, "inactive")
            name = cylinder_type.name
            if _price(prices, cylinder_type, customer_type, branch_id, now) is None:
                _reject(
                    f"{name} has no price set for {customer_type} customers at this "
                    "branch. Add one under Pricing.",
                    cylinder_type_id,
                    "no_price",
                )
            available = max(stock.get(cylinder_type_id, 0), 0)
            if available == 0:
                _reject(
                    f"{name} is out of stock at this branch (no filled cylinders left).",
                    cylinder_type_id,
                    "out_of_stock",
                )
            if quantity > available:
                _reject(
                    f"Only {available} filled {name} cylinder(s) are available at this "
                    f"branch; {quantity} requested.",
                    cylinder_type_id,
                    "insufficient_stock",
                )


def _price(
    prices: Sequence[PriceListEntry],
    cylinder_type: CylinderType,
    customer_type: str,
    branch_id: uuid.UUID,
    at: datetime,
) -> Decimal | None:
    resolved = EffectivePriceResolver.resolve(
        prices,
        cylinder_type_id=cylinder_type.id,
        customer_type=customer_type,
        branch_id=branch_id,
        at=at,
    )
    return resolved.price if resolved is not None else None


def _reject(message: str, cylinder_type_id: uuid.UUID, reason: str) -> NoReturn:
    raise CylinderNotOrderableError(message, cylinder_type_id=str(cylinder_type_id), reason=reason)
