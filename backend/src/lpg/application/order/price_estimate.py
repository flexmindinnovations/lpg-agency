"""What a not-yet-confirmed order would cost at today's prices.

An order's price is fixed when the agency confirms it, so a booked order has
none saved. This works out the same sums confirmation would, for display only:
nothing is stored and the order is not changed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from lpg.domain.order.order import OrderLine
from lpg.domain.tenant.price_list import EffectivePriceResolver

if TYPE_CHECKING:
    import uuid

    from lpg.application.order.gst_snapshot import OrderGstSnapshotter
    from lpg.application.tenant.ports import PriceListRepository
    from lpg.domain.order.order import Order

#: The statuses an order has before confirmation prices it.
_UNPRICED_STATUSES = frozenset({"draft", "booked"})


@dataclass(frozen=True, slots=True)
class OrderPriceEstimate:
    #: Line id -> unit price in effect now.
    unit_prices: dict[uuid.UUID, Decimal]
    #: Price times quantity over all lines, as `Order.total_amount` would be.
    total_amount: Decimal
    #: `None` (with `payable_amount`) while a cylinder type has no GST rate.
    tax_amount: Decimal | None
    payable_amount: Decimal | None
    prices_include_gst: bool | None


class EstimateOrderPrice:
    def __init__(
        self,
        price_lists: PriceListRepository,
        gst_snapshotter: OrderGstSnapshotter,
    ) -> None:
        self._price_lists = price_lists
        self._gst_snapshotter = gst_snapshotter

    async def execute(self, order: Order, *, customer_type: str) -> OrderPriceEstimate | None:
        """`None` when the order already has its price, or when a line has no
        price in effect (confirmation would be refused for the same reason)."""
        if order.status not in _UNPRICED_STATUSES or order.total_amount is not None:
            return None

        prices = await self._price_lists.list_for_tenant(order.tenant_id)
        now = datetime.now(UTC)
        unit_prices: dict[uuid.UUID, Decimal] = {}
        for line in order.lines:
            resolved = EffectivePriceResolver.resolve(
                prices,
                cylinder_type_id=line.cylinder_type_id,
                customer_type=customer_type,
                branch_id=order.branch_id,
                at=now,
            )
            if resolved is None:
                return None
            unit_prices[line.id] = resolved.price

        total = sum(
            (unit_prices[line.id] * line.quantity_ordered for line in order.lines),
            start=Decimal("0"),
        )
        gst = await self._gst_snapshotter.snapshot(
            tenant_id=order.tenant_id,
            cylinder_type_ids=[line.cylinder_type_id for line in order.lines],
        )
        if gst is None:
            return OrderPriceEstimate(unit_prices, total, None, None, None)

        tax = Decimal("0.00")
        payable = Decimal("0.00")
        for line in order.lines:
            # A priced copy, so the line's own sums are used and the order
            # itself stays unpriced.
            priced = OrderLine(
                line_id=line.id,
                cylinder_type_id=line.cylinder_type_id,
                quantity_ordered=line.quantity_ordered,
            )
            priced.set_unit_price(unit_prices[line.id])
            priced.set_gst_rate(gst.rates[line.cylinder_type_id])
            amounts = priced.taxed_amounts(prices_include_gst=gst.prices_include_gst)
            assert amounts is not None  # priced on the line above
            tax += amounts[0]
            payable += amounts[1]
        return OrderPriceEstimate(unit_prices, total, tax, payable, gst.prices_include_gst)
