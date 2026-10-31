"""The amount a customer pays for an order: price plus GST when prices are
GST-exclusive, worked out the way the invoice works it out."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from lpg.domain.order.order import DeliveryAddress, Order, OrderLine

DOMESTIC = uuid.uuid4()
COMMERCIAL = uuid.uuid4()


def _order(*quantities: tuple[uuid.UUID, int]) -> Order:
    return Order(
        order_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        address_id=uuid.uuid4(),
        delivery_address=DeliveryAddress(address_line="1 Main St"),
        booking_source="staff",
        requested_date=datetime.now(UTC),
        lines=[
            OrderLine(line_id=uuid.uuid4(), cylinder_type_id=c, quantity_ordered=q)
            for c, q in quantities
        ],
        status="booked",
    )


def _confirm(
    order: Order,
    prices: dict[uuid.UUID, str],
    rates: dict[uuid.UUID, str] | None,
    *,
    inclusive: bool | None,
) -> None:
    order.confirm(
        unit_prices={k: Decimal(v) for k, v in prices.items()},
        changed_by=uuid.uuid4(),
        gst_rates={k: Decimal(v) for k, v in rates.items()} if rates else None,
        prices_include_gst=inclusive,
    )


def test_exclusive_price_gets_gst_on_top_as_the_invoice_does() -> None:
    order = _order((DOMESTIC, 1))
    _confirm(order, {DOMESTIC: "905.50"}, {DOMESTIC: "5"}, inclusive=False)

    # The figures from the first end-to-end run: Rs 905.50 + 5% = Rs 950.78.
    assert order.total_amount == Decimal("905.50")
    assert order.tax_amount == Decimal("45.28")
    assert order.payable_amount == Decimal("950.78")


def test_tax_is_rounded_per_line_like_the_invoice() -> None:
    order = _order((DOMESTIC, 3), (COMMERCIAL, 1))
    _confirm(
        order,
        {DOMESTIC: "905.50", COMMERCIAL: "1755.00"},
        {DOMESTIC: "5", COMMERCIAL: "18"},
        inclusive=False,
    )

    # 3 x 905.50 = 2716.50 -> 5% = 135.825 -> 135.83; 1755.00 -> 18% = 315.90.
    assert order.tax_amount == Decimal("135.83") + Decimal("315.90")
    assert order.payable_amount == Decimal("2716.50") + Decimal("135.83") + Decimal(
        "1755.00"
    ) + Decimal("315.90")


def test_inclusive_price_is_what_the_customer_pays_with_the_tax_inside() -> None:
    order = _order((DOMESTIC, 1))
    _confirm(order, {DOMESTIC: "905.50"}, {DOMESTIC: "5"}, inclusive=True)

    assert order.payable_amount == Decimal("905.50")
    assert order.tax_amount == Decimal("43.12")  # 905.50 - 862.38


def test_an_order_priced_before_gst_was_snapshotted_is_unchanged() -> None:
    order = _order((DOMESTIC, 2))
    _confirm(order, {DOMESTIC: "905.50"}, None, inclusive=None)

    assert order.total_amount == Decimal("1811.00")
    assert order.tax_amount is None
    assert order.payable_amount == Decimal("1811.00")


def test_an_unpriced_order_has_no_amount() -> None:
    order = _order((DOMESTIC, 1))
    assert order.total_amount is None
    assert order.tax_amount is None
    assert order.payable_amount is None


def test_the_rate_is_kept_with_the_price_for_later() -> None:
    order = _order((DOMESTIC, 1))
    _confirm(order, {DOMESTIC: "905.50"}, {DOMESTIC: "5"}, inclusive=False)

    assert order.lines[0].gst_rate_percent == Decimal("5")
    assert order.prices_include_gst is False
