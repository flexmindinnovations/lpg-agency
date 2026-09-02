"""Unit tests for the pure content/routing helpers in the notification job.

The job body itself needs a live DB + queue (covered by integration smoke
tests); these lock down the channel-routing decisions, which are just
lookups over the notification type.
"""

from lpg.infrastructure.jobs.notification_jobs import (
    _STAFF_ALERT_ROLES,
    _get_body,
    _get_title,
    _should_send_email,
    _should_send_push,
    _should_send_sms,
)


def test_push_covers_every_customer_and_driver_facing_type() -> None:
    for notification_type in (
        "order_placed",
        "booking_confirmed",
        "out_for_delivery",
        "delivery_confirmed",
        "invoice_generated",
        "route_ready",
    ):
        assert _should_send_push(notification_type) is True


def test_driver_assigned_push_and_sms_are_decided_per_instance() -> None:
    # Phase 25-B: the initial route build is covered by one `route_ready`
    # push, so `driver_assigned` is neither a blanket push nor SMS type —
    # the job only pushes it for a live mid-route addition.
    assert _should_send_push("driver_assigned") is False
    assert _should_send_sms("driver_assigned") is False


def test_route_ready_is_push_plus_in_app_only() -> None:
    assert _get_title("route_ready") == "Route Ready"
    assert _get_body("route_ready", {"stop_count": "5"}) == (
        "Your route is ready — 5 stops."
    )
    assert _get_body("route_ready", {"stop_count": "1"}) == (
        "Your route is ready — 1 stop."
    )
    assert _should_send_push("route_ready") is True
    assert _should_send_sms("route_ready") is False
    assert _should_send_email("route_ready") is False


def test_stop_cancelled_is_push_plus_in_app_only() -> None:
    assert _get_title("stop_cancelled") == "Stop Cancelled"
    body = _get_body("stop_cancelled", {"order_id": "abcd1234-0000"})
    assert "ABCD1234" in body
    assert "skip that stop" in body
    assert _should_send_push("stop_cancelled") is True
    assert _should_send_sms("stop_cancelled") is False
    assert _should_send_email("stop_cancelled") is False


def test_order_placed_acknowledges_the_customer_immediately() -> None:
    # Fires on order placement, before the agency confirms — push + in-app,
    # no email/SMS noise (same restraint as the staff alert).
    assert _get_title("order_placed") == "Order Received"
    body = _get_body("order_placed", {"order_id": "abcd1234-0000"})
    assert "ABCD1234" in body
    assert "once the agency confirms" in body
    assert _should_send_push("order_placed") is True
    assert _should_send_email("order_placed") is False
    assert _should_send_sms("order_placed") is False


def test_push_excludes_staff_only_alerts() -> None:
    # Staff work from the dashboard; the mobile apps are the only clients
    # that register device tokens.
    assert _should_send_push("delivery_failed_staff") is False
    assert _should_send_push("order_placed_staff") is False


def test_push_ignores_unknown_types() -> None:
    assert _should_send_push("something_new") is False


def test_order_placed_staff_is_in_app_only() -> None:
    # A new-order alert for branch staff — no email/SMS/push, just the
    # dashboard bell.
    assert _should_send_email("order_placed_staff") is False
    assert _should_send_sms("order_placed_staff") is False
    assert _should_send_push("order_placed_staff") is False


def test_staff_alert_roles_use_the_real_role_strings() -> None:
    # `manager`, not `branch_manager` (the old value, which no code path
    # ever produced).
    assert set(_STAFF_ALERT_ROLES) == {"agency_admin", "manager", "dispatcher"}


def test_order_placed_staff_has_title_and_body() -> None:
    assert _get_title("order_placed_staff") == "New Order"
    body = _get_body("order_placed_staff", {"order_id": "abcd1234-0000"})
    assert "ABCD1234" in body
    assert "awaiting confirmation" in body


def test_title_and_body_have_a_safe_fallback() -> None:
    assert _get_title("unmapped") == "Notification"
    assert _get_body("unmapped", {}) == "You have a new notification."


def test_cash_shortfall_staff_title_and_body() -> None:
    assert _get_title("cash_shortfall_staff") == "Cash Shortfall Declared"
    body = _get_body(
        "cash_shortfall_staff",
        {
            "route_id": "d9cfd7b3-3333-4444-5555-666677778888",
            "expected_amount": "1811.00",
            "actual_amount": "1800.00",
            "shortfall": "11.00",
        },
    )
    assert "D9CFD7B3" in body
    assert "₹11.00" in body
    assert "₹1811.00" in body
    assert "₹1800.00" in body


def test_cash_shortfall_staff_goes_to_dashboard_and_email_but_not_push() -> None:
    assert _should_send_email("cash_shortfall_staff") is True
    assert _should_send_sms("cash_shortfall_staff") is False
    assert _should_send_push("cash_shortfall_staff") is False
