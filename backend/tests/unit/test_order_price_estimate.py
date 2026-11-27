"""`EstimateOrderPrice`: what a booked order would cost, shown before the
agency confirms it. It must agree with what confirmation then charges."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from lpg.application.order.gst_snapshot import GstSnapshot
from lpg.application.order.price_estimate import EstimateOrderPrice
from lpg.domain.order.order import DeliveryAddress, Order, OrderLine
from lpg.domain.tenant.price_list import PriceListEntry

TENANT_ID = uuid.uuid4()
BRANCH_ID = uuid.uuid4()
STAFF_ID = uuid.uuid4()
COMMERCIAL_19 = uuid.uuid4()
COMMERCIAL_47 = uuid.uuid4()


@dataclass
class FakePriceLists:
    entries: list[PriceListEntry]

    async def list_for_tenant(self, tenant_id: uuid.UUID) -> list[PriceListEntry]:  # noqa: ARG002
        return self.entries


@dataclass
class FakeGst:
    result: GstSnapshot | None

    async def snapshot(self, **_: object) -> GstSnapshot | None:
        return self.result


def _price(
    cylinder_type_id: uuid.UUID,
    amount: str,
    *,
    customer_type: str = "commercial",
    branch_id: uuid.UUID | None = None,
    starts_in: timedelta = timedelta(days=-1),
) -> PriceListEntry:
    return PriceListEntry(
        uuid.uuid4(),
        TENANT_ID,
        cylinder_type_id,
        customer_type,
        Decimal(amount),
        datetime.now(UTC) + starts_in,
        branch_id=branch_id,
    )


def _gst(*, inclusive: bool = False) -> GstSnapshot:
    return GstSnapshot(
        rates={COMMERCIAL_19: Decimal("18"), COMMERCIAL_47: Decimal("18")},
        prices_include_gst=inclusive,
    )


def _booked_order(lines: list[tuple[uuid.UUID, int]]) -> Order:
    order = Order(
        order_id=uuid.uuid4(),
        tenant_id=TENANT_ID,
        branch_id=BRANCH_ID,
        customer_id=uuid.uuid4(),
        address_id=uuid.uuid4(),
        order_number="ORD000001",
        delivery_address=DeliveryAddress(address_line="1 Depot Road"),
        booking_source="staff",
        requested_date=datetime.now(UTC),
        lines=[
            OrderLine(line_id=uuid.uuid4(), cylinder_type_id=type_id, quantity_ordered=quantity)
            for type_id, quantity in lines
        ],
    )
    order.submit(changed_by=STAFF_ID)
    return order


async def _estimate(order: Order, prices: list[PriceListEntry], gst: GstSnapshot | None):  # type: ignore[no-untyped-def]
    use_case = EstimateOrderPrice(FakePriceLists(prices), FakeGst(gst))  # type: ignore[arg-type]
    return await use_case.execute(order, customer_type="commercial")


@pytest.mark.parametrize("inclusive", [False, True])
async def test_matches_what_confirming_then_charges(inclusive: bool) -> None:
    order = _booked_order([(COMMERCIAL_19, 3), (COMMERCIAL_47, 1)])
    prices = [_price(COMMERCIAL_19, "2100.00"), _price(COMMERCIAL_47, "5233.33")]
    gst = _gst(inclusive=inclusive)

    estimate = await _estimate(order, prices, gst)

    assert estimate is not None
    order.confirm(
        unit_prices={COMMERCIAL_19: Decimal("2100.00"), COMMERCIAL_47: Decimal("5233.33")},
        changed_by=STAFF_ID,
        gst_rates=gst.rates,
        prices_include_gst=inclusive,
    )
    assert estimate.total_amount == order.total_amount
    assert estimate.tax_amount == order.tax_amount
    assert estimate.payable_amount == order.payable_amount
    assert estimate.unit_prices == {line.id: line.unit_price for line in order.lines}
    assert estimate.prices_include_gst is inclusive


async def test_leaves_the_order_unpriced() -> None:
    order = _booked_order([(COMMERCIAL_19, 2)])

    await _estimate(order, [_price(COMMERCIAL_19, "2100.00")], _gst())

    assert order.total_amount is None
    assert all(line.unit_price is None for line in order.lines)
    assert all(line.gst_rate_percent is None for line in order.lines)
    assert order.status == "booked"


async def test_uses_the_branch_price_over_the_default() -> None:
    order = _booked_order([(COMMERCIAL_19, 1)])
    prices = [
        _price(COMMERCIAL_19, "2100.00"),
        _price(COMMERCIAL_19, "2050.00", branch_id=BRANCH_ID),
        _price(COMMERCIAL_19, "1.00", customer_type="domestic"),
        _price(COMMERCIAL_19, "9999.00", starts_in=timedelta(days=5)),
    ]

    estimate = await _estimate(order, prices, _gst())

    assert estimate is not None
    assert estimate.total_amount == Decimal("2050.00")


async def test_no_estimate_when_a_line_has_no_price() -> None:
    order = _booked_order([(COMMERCIAL_19, 1), (COMMERCIAL_47, 1)])

    assert await _estimate(order, [_price(COMMERCIAL_19, "2100.00")], _gst()) is None


async def test_price_without_gst_set_up_gives_no_tax_or_total_to_pay() -> None:
    order = _booked_order([(COMMERCIAL_19, 2)])

    estimate = await _estimate(order, [_price(COMMERCIAL_19, "2100.00")], None)

    assert estimate is not None
    assert estimate.total_amount == Decimal("4200.00")
    assert estimate.tax_amount is None
    assert estimate.payable_amount is None


async def test_no_estimate_once_the_order_has_its_price() -> None:
    order = _booked_order([(COMMERCIAL_19, 1)])
    order.confirm(unit_prices={COMMERCIAL_19: Decimal("2000.00")}, changed_by=STAFF_ID)

    assert await _estimate(order, [_price(COMMERCIAL_19, "2100.00")], _gst()) is None
