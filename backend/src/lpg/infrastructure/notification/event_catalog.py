"""The events an agency can tune (ADR-068): the catalogue's specs plus the
plain-language description, grouping and "critical" flag the settings page
needs. Every type in `SPECS` must have an entry here (unit-tested)."""

from __future__ import annotations

from typing import NamedTuple

from lpg.application.notification.preferences import EventDefinition
from lpg.infrastructure.notification.catalog import SPECS


class _Meta(NamedTuple):
    group: str
    description: str
    critical: bool = False


_META: dict[str, _Meta] = {
    # Customer
    "order_placed": _Meta("Orders", "Tells the customer their order was received."),
    "booking_confirmed": _Meta("Orders", "The agency confirmed the customer's order."),
    "out_for_delivery": _Meta("Deliveries", "The driver is on the way to the customer."),
    "order_reminder": _Meta("Orders", "A message staff send by hand from the order page."),
    "delivery_confirmed": _Meta("Deliveries", "The order was delivered."),
    "delivery_failed_customer": _Meta(
        "Deliveries", "A delivery attempt failed; the agency will rearrange.", critical=True
    ),
    "order_cancelled_customer": _Meta(
        "Orders", "The order was cancelled, with any cancellation charge.", critical=True
    ),
    "invoice_generated": _Meta("Payments and invoices", "An invoice is ready for the order."),
    "invoice_sent": _Meta("Payments and invoices", "Staff sent the invoice to the customer."),
    "payment_received_customer": _Meta(
        "Payments and invoices",
        "A payment was recorded against the customer's order.",
        critical=True,
    ),
    "refill_due_customer": _Meta(
        "Orders", "A nudge when the customer's cylinder is likely to run low."
    ),
    # Driver
    "route_ready": _Meta("Deliveries", "A new trip is ready for the driver."),
    "order_reminder_driver": _Meta("Deliveries", "A message staff send by hand to the driver."),
    "driver_assigned": _Meta("Deliveries", "A stop was added to a trip already under way."),
    "stop_cancelled": _Meta("Deliveries", "A stop on the driver's trip was cancelled."),
    "route_resequenced": _Meta("Deliveries", "The office changed the order of the driver's stops."),
    "route_cancelled_driver": _Meta("Deliveries", "The driver's trip was cancelled."),
    # Staff
    "order_placed_staff": _Meta("Orders", "A new order is waiting to be confirmed."),
    "cancellation_requested_staff": _Meta(
        "Orders", "A cancellation is waiting for approval.", critical=True
    ),
    "complaint_raised_staff": _Meta("Complaints", "A customer raised a complaint."),
    "complaint_assigned": _Meta("Complaints", "A complaint was assigned to a staff member."),
    "device_blocked_user": _Meta(
        "Phones and access",
        "The agency blocked or removed the phone someone was signed in on.",
        critical=True,
    ),
    "device_pending_staff": _Meta(
        "Phones and access", "A phone signed in to the Driver or Admin app and needs approval."
    ),
    "delivery_failed_staff": _Meta(
        "Deliveries", "A delivery could not be completed.", critical=True
    ),
    "order_delivered_staff": _Meta("Deliveries", "An order was delivered."),
    "order_unassignable_staff": _Meta(
        "Deliveries", "No free driver or van could be found for an order."
    ),
    "order_stale_unassigned_staff": _Meta(
        "Deliveries", "A confirmed order is still not on a trip."
    ),
    "route_started_staff": _Meta("Deliveries", "A trip left the depot."),
    "route_load_confirmed_staff": _Meta(
        "Deliveries", "A driver checked the van against the load sheet."
    ),
    "cash_shortfall_staff": _Meta(
        "Payments and invoices", "A driver handed over less cash than expected.", critical=True
    ),
    "payment_received_staff": _Meta("Payments and invoices", "A customer paid online."),
    "inventory_low_stock_staff": _Meta(
        "Stock and compliance", "Filled stock fell to its reorder point."
    ),
    "compliance_document_expiring_staff": _Meta(
        "Stock and compliance", "A licence or certificate is about to expire.", critical=True
    ),
    "lpg_rate_review_staff": _Meta("Pricing", "New monthly LPG rates are ready to review."),
}


def build_event_catalog() -> list[EventDefinition]:
    """One definition per catalogue type, grouped, customer events first."""
    order = {"customer": 0, "driver": 1, "staff": 2}
    definitions: list[EventDefinition] = []
    for notification_type, spec in SPECS.items():
        meta = _META[notification_type]
        audience = "staff" if spec.audience.value in ("staff", "assignee", "user") else spec.audience.value
        definitions.append(
            EventDefinition(
                notification_type=notification_type,
                title=spec.title,
                description=meta.description,
                audience=audience,
                group=meta.group,
                default_in_app=True,
                default_push=spec.push,
                default_sms=spec.sms is not None,
                default_email=spec.email,
                supports_sms=spec.sms is not None,
                supports_email=spec.email,
                critical=meta.critical,
            )
        )
    definitions.sort(key=lambda d: (order[d.audience], d.group, d.title))
    return definitions


def meta_types() -> set[str]:
    return set(_META)


_DEFINITIONS: dict[str, EventDefinition] = {d.notification_type: d for d in build_event_catalog()}


def definition_for(notification_type: str) -> EventDefinition | None:
    return _DEFINITIONS.get(notification_type)
