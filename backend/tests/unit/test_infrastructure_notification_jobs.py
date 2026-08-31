"""Unit tests for the pure content/routing helpers in the notification job.

The job body itself needs a live DB + queue (covered by integration smoke
tests); these lock down the channel-routing decisions, which are just
lookups over the notification type.
"""

from lpg.infrastructure.jobs.notification_jobs import (
    _get_body,
    _get_title,
    _should_send_push,
)


def test_push_covers_every_customer_and_driver_facing_type() -> None:
    for notification_type in (
        "booking_confirmed",
        "driver_assigned",
        "out_for_delivery",
        "delivery_confirmed",
        "invoice_generated",
    ):
        assert _should_send_push(notification_type) is True


def test_push_excludes_staff_only_alerts() -> None:
    # Staff work from the dashboard; the mobile apps are the only clients
    # that register device tokens.
    assert _should_send_push("delivery_failed_staff") is False


def test_push_ignores_unknown_types() -> None:
    assert _should_send_push("something_new") is False


def test_title_and_body_have_a_safe_fallback() -> None:
    assert _get_title("unmapped") == "Notification"
    assert _get_body("unmapped", {}) == "You have a new notification."
