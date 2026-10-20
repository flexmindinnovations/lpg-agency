"""Unit tests for the notification catalogue: wording, audience, RBAC
permission and channel routing per type (`infrastructure/notification/
catalog.py`). Pure lookups and string formatting — no I/O."""

from __future__ import annotations

import pytest

from lpg.application.notification.ports import SmsTemplate
from lpg.infrastructure.notification.catalog import (
    SPECS,
    Audience,
    format_rupees,
    sms_variables,
    spec_for,
)


def _body(notification_type: str, **facts: str) -> str:
    spec = spec_for(notification_type)
    assert spec is not None
    return spec.body(facts)


def test_every_staff_type_names_the_permission_that_selects_recipients() -> None:
    for name, spec in SPECS.items():
        if spec.audience is Audience.STAFF:
            assert spec.permission, name
        else:
            assert spec.permission is None, name


@pytest.mark.parametrize(
    ("notification_type", "permission"),
    [
        ("order_placed_staff", "orders:confirm"),
        ("cancellation_requested_staff", "orders:cancel_approve"),
        ("complaint_raised_staff", "complaints.manage"),
        ("delivery_failed_staff", "orders:dispatch"),
        ("payment_received_staff", "invoices:record_payment"),
        ("cash_shortfall_staff", "invoices:record_payment"),
        ("inventory_low_stock_staff", "inventory:adjust"),
    ],
)
def test_staff_alerts_go_to_the_people_who_act_on_them(
    notification_type: str, permission: str
) -> None:
    spec = spec_for(notification_type)
    assert spec is not None
    assert spec.audience is Audience.STAFF
    assert spec.permission == permission


def test_staff_alerts_are_in_app_only_unless_money_or_stock() -> None:
    # Staff work from the dashboard; the apps are the only clients with
    # push tokens. A money discrepancy or a reorder wants an email trail.
    for name, spec in SPECS.items():
        if spec.audience is not Audience.STAFF:
            continue
        assert spec.push is False, name
        assert spec.sms is None, name
    assert SPECS["cash_shortfall_staff"].email is True
    assert SPECS["inventory_low_stock_staff"].email is True
    assert SPECS["order_placed_staff"].has_external_channel is False


def test_customer_lifecycle_types_push_and_sms_where_registered() -> None:
    for name in (
        "order_placed",
        "booking_confirmed",
        "out_for_delivery",
        "delivery_confirmed",
        "delivery_failed_customer",
        "order_cancelled_customer",
        "payment_received_customer",
    ):
        spec = spec_for(name)
        assert spec is not None
        assert spec.audience is Audience.CUSTOMER
        assert spec.push is True, name
    assert SPECS["booking_confirmed"].sms is SmsTemplate.BOOKING_CONFIRMED
    assert SPECS["out_for_delivery"].sms is SmsTemplate.OUT_FOR_DELIVERY
    assert SPECS["delivery_confirmed"].sms is SmsTemplate.DELIVERY_CONFIRMED


def test_driver_assigned_push_is_decided_per_instance() -> None:
    spec = spec_for("driver_assigned")
    assert spec is not None
    assert spec.audience is Audience.DRIVER
    assert spec.push is False
    assert spec.sms is None


def test_bodies_name_the_order_number_and_the_customer() -> None:
    body = _body("order_placed_staff", order_ref="ORD000022", customer_name="Ravi Kumar")
    assert body == "ORD000022 for Ravi Kumar was just placed and is waiting for confirmation."
    assert "ORD000022" in _body("booking_confirmed", order_ref="ORD000022")


def test_cancellation_request_body_quotes_the_reason() -> None:
    body = _body(
        "cancellation_requested_staff",
        order_ref="ORD000009",
        customer_name="Meena Iyer",
        reason="Booked twice",
    )
    assert body.startswith("ORD000009 for Meena Iyer: cancellation requested")
    assert body.endswith("Reason: Booked twice.")


def test_failed_delivery_bodies_for_staff_and_customer() -> None:
    staff = _body(
        "delivery_failed_staff",
        order_ref="ORD000013",
        customer_name="Ravi",
        reason="customer not available",
    )
    assert staff == "ORD000013 for Ravi could not be delivered. Reason: customer not available."
    customer = _body("delivery_failed_customer", order_ref="ORD000013")
    assert "couldn't deliver ORD000013" in customer


def test_route_bodies_name_the_driver_and_van_not_a_uuid() -> None:
    body = _body("route_started_staff", driver_name="Ravi", vehicle_ref="TS09AB1234")
    assert body == "Ravi's trip (TS09AB1234) has left the depot."
    assert _body("route_ready", stop_count="1") == "Your trip is ready — 1 stop."
    assert _body("route_ready", stop_count="5") == "Your trip is ready — 5 stops."


def test_amounts_are_grouped_the_indian_way() -> None:
    assert format_rupees("1811") == "₹1,811.00"
    assert format_rupees("123456.5") == "₹1,23,456.50"
    assert format_rupees("50") == "₹50.00"
    assert format_rupees(None) == "the amount"
    body = _body(
        "cash_shortfall_staff",
        driver_name="Ravi",
        expected_amount="1811.00",
        actual_amount="1800.00",
        shortfall="11.00",
    )
    assert "₹1,800.00 of ₹1,811.00" in body
    assert "short by ₹11.00" in body


def test_missing_facts_fall_back_to_plain_words() -> None:
    assert _body("booking_confirmed").startswith("Your order is confirmed")
    assert _body("route_started_staff") == "A trip has left the depot."


def test_sms_variables_carry_the_order_number() -> None:
    assert sms_variables({"order_ref": "ORD000001"}) == {"order_ref": "ORD000001"}


def test_unknown_type_has_no_spec() -> None:
    assert spec_for("something_new") is None
