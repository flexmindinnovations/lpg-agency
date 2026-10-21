"""DO-13: editing a booking and rescheduling a failed delivery to a date."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from lpg.domain.common.base import InvariantViolation
from lpg.domain.order.order import (
    BookingAmended,
    DeliveryAddress,
    InvalidOrderStatusTransitionError,
    Order,
    OrderLine,
)

CYL = uuid.uuid4()


def _order(status: str, **kwargs: object) -> Order:
    fields: dict[str, object] = {
        "order_id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "branch_id": uuid.uuid4(),
        "customer_id": uuid.uuid4(),
        "address_id": uuid.uuid4(),
        "delivery_address": DeliveryAddress(address_line="1 Main St"),
        "booking_source": "staff",
        "requested_date": datetime.now(UTC),
        "lines": [OrderLine(line_id=uuid.uuid4(), cylinder_type_id=CYL, quantity_ordered=1)],
        "status": status,
    }
    fields.update(kwargs)
    return Order(**fields)  # type: ignore[arg-type]


def _amend(order: Order, quantity: int, **kwargs: object) -> None:
    order.amend(
        lines=[OrderLine(line_id=uuid.uuid4(), cylinder_type_id=CYL, quantity_ordered=quantity)],
        requested_date=kwargs.pop("requested_date", order.requested_date),  # type: ignore[arg-type]
        address_id=order.address_id,
        delivery_address=order.delivery_address,
        payment_method_preference=None,
        changed_by=uuid.uuid4(),
        **kwargs,  # type: ignore[arg-type]
    )


def test_a_booked_order_can_be_edited_and_stays_unpriced() -> None:
    order = _order("booked")
    _amend(order, 3)
    assert order.lines[0].quantity_ordered == 3
    assert order.total_amount is None
    assert any(isinstance(e, BookingAmended) for e in order.events)


def test_a_confirmed_order_is_repriced() -> None:
    order = _order("confirmed")
    _amend(order, 2, unit_prices={CYL: Decimal("950.00")})
    assert order.total_amount == Decimal("1900.00")


def test_an_order_on_a_trip_cannot_be_edited() -> None:
    with pytest.raises(InvalidOrderStatusTransitionError):
        _amend(_order("assigned"), 2)


def test_a_past_date_is_refused() -> None:
    with pytest.raises(InvariantViolation, match="past"):
        _amend(_order("booked"), 1, requested_date=datetime.now(UTC) - timedelta(days=2))


def test_reschedule_to_a_date_leaves_the_trip() -> None:
    order = _order("failed_delivery", route_stop_id=uuid.uuid4())
    tomorrow = datetime.now(UTC) + timedelta(days=1)
    order.reschedule_to(requested_date=tomorrow, changed_by=uuid.uuid4())
    assert order.status == "confirmed"
    assert order.route_stop_id is None
    assert order.requested_date == tomorrow
    assert order.pending_status_history[-1].reason == f"Rescheduled to {tomorrow.date()}"
