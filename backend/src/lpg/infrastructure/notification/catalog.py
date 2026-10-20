"""What each notification type says, who it is for and which channels it uses.

Pure data and string formatting — no I/O — so the wording and the channel
routing are unit-testable on their own. The recipient and the facts a
message quotes (order number, customer name, amounts) are resolved by
`recipients.py`; this module only turns those facts into text.

Every message names the thing it is about the way people in the office and
at the door know it — the order number (ORD000022), the customer's name,
the driver and van — never a UUID.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from lpg.application.notification.ports import SmsTemplate


class Audience(StrEnum):
    """Who a notification type is resolved to."""

    #: The order's customer (their identity user).
    CUSTOMER = "customer"
    #: The driver of the route the order / event belongs to.
    DRIVER = "driver"
    #: Staff holding the type's permission, scoped to the event's branch.
    STAFF = "staff"
    #: One named staff member (the complaint's assignee).
    ASSIGNEE = "assignee"


Facts = Mapping[str, str]
_BodyFn = Callable[[Facts], str]


@dataclass(frozen=True, slots=True)
class NotificationSpec:
    title: str
    body: _BodyFn
    audience: Audience
    #: Staff types only: the permission that makes someone a recipient —
    #: so a tenant's own permission edits decide who hears what (RBAC).
    permission: str | None = None
    #: Where a click on the notification goes (`order`, `route`, ...).
    reference_type: str = "order"
    email: bool = False
    sms: SmsTemplate | None = None
    push: bool = False

    @property
    def has_external_channel(self) -> bool:
        return self.email or self.sms is not None or self.push


def _order(f: Facts) -> str:
    return f.get("order_ref") or "your order"


def _order_cap(f: Facts) -> str:
    """`_order` at the start of a sentence."""
    return f.get("order_ref") or "Your order"


def _order_for(f: Facts) -> str:
    """`ORD000022 for Ravi Kumar` — the staff-facing order label."""
    ref = f.get("order_ref") or "An order"
    name = f.get("customer_name")
    return f"{ref} for {name}" if name else ref


def _route(f: Facts) -> str:
    """`Ravi's trip (TS09AB1234)` — routes have no number of their own."""
    driver = f.get("driver_name")
    vehicle = f.get("vehicle_ref")
    if driver and vehicle:
        return f"{driver}'s trip ({vehicle})"
    if driver:
        return f"{driver}'s trip"
    return "A trip"


def _stops(f: Facts) -> str:
    count = f.get("stop_count")
    if not count:
        return "Your trip is ready."
    return f"Your trip is ready — {count} stop{'' if count == '1' else 's'}."


def format_rupees(value: str | None) -> str:
    """`1811.5` -> `₹1,811.50`, grouped the Indian way (`₹1,23,456.00`)."""
    if not value:
        return "the amount"
    try:
        amount = Decimal(value).quantize(Decimal("0.01"))
    except InvalidOperation:
        return f"₹{value}"
    sign = "-" if amount < 0 else ""
    whole, _, paise = f"{abs(amount):.2f}".partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups: list[str] = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join([*groups, tail])
    return f"{sign}₹{whole}.{paise}"


_rupees = format_rupees


def _with_reason(text: str, f: Facts) -> str:
    reason = f.get("reason")
    return f"{text} Reason: {reason}." if reason else text


#: Failed-delivery reason codes (D-12) as a person would say them.
FAILED_DELIVERY_REASON_LABELS: dict[str, str] = {
    "customer_unavailable": "customer not available",
    "wrong_address": "wrong or incomplete address",
    "payment_refused": "payment refused",
    "vehicle_issue": "vehicle problem",
    "safety_issue": "safety concern",
}


SPECS: dict[str, NotificationSpec] = {
    # ----- Customer --------------------------------------------------------
    "order_placed": NotificationSpec(
        title="Order received",
        body=lambda f: (
            f"We've received {_order(f)}. We'll let you know as soon as the agency confirms it."
        ),
        audience=Audience.CUSTOMER,
        push=True,
    ),
    "booking_confirmed": NotificationSpec(
        title="Order confirmed",
        body=lambda f: f"{_order_cap(f)} is confirmed and will be scheduled for delivery.",
        audience=Audience.CUSTOMER,
        email=True,
        sms=SmsTemplate.BOOKING_CONFIRMED,
        push=True,
    ),
    "out_for_delivery": NotificationSpec(
        title="Out for delivery",
        body=lambda f: (
            f"{_order_cap(f)} is on its way"
            + (f" with {f['driver_name']}" if f.get("driver_name") else "")
            + ". Keep your delivery code ready."
        ),
        audience=Audience.CUSTOMER,
        sms=SmsTemplate.OUT_FOR_DELIVERY,
        push=True,
    ),
    "delivery_confirmed": NotificationSpec(
        title="Delivered",
        body=lambda f: f"{_order_cap(f)} has been delivered. Thank you!",
        audience=Audience.CUSTOMER,
        email=True,
        sms=SmsTemplate.DELIVERY_CONFIRMED,
        push=True,
    ),
    "delivery_failed_customer": NotificationSpec(
        title="Delivery attempt failed",
        body=lambda f: _with_reason(
            f"We couldn't deliver {_order(f)} today. The agency will contact you to "
            "arrange another attempt.",
            f,
        ),
        audience=Audience.CUSTOMER,
        push=True,
    ),
    "order_cancelled_customer": NotificationSpec(
        title="Order cancelled",
        body=lambda f: (
            f"{_order_cap(f)} has been cancelled"
            + (
                f". A cancellation charge of {_rupees(f['cancellation_charge'])} applies."
                if f.get("cancellation_charge")
                else "."
            )
        ),
        audience=Audience.CUSTOMER,
        push=True,
    ),
    "invoice_generated": NotificationSpec(
        title="Invoice ready",
        body=lambda f: (
            f"Your invoice{(' ' + f['invoice_ref']) if f.get('invoice_ref') else ''} "
            f"for {_order(f)} is ready."
        ),
        audience=Audience.CUSTOMER,
        email=True,
        push=True,
    ),
    "payment_received_customer": NotificationSpec(
        title="Payment received",
        body=lambda f: (
            f"We've received your payment of {_rupees(f.get('amount'))}"
            + (f" for {f['order_ref']}" if f.get("order_ref") else "")
            + ". Thank you!"
        ),
        audience=Audience.CUSTOMER,
        push=True,
    ),
    "refill_due_customer": NotificationSpec(
        title="Time for a refill?",
        body=lambda f: (
            f"Your cylinder is expected to run low around {f.get('refill_due_date') or 'soon'}. "
            "Book a refill anytime."
        ),
        audience=Audience.CUSTOMER,
        reference_type="customer",
        push=True,
    ),
    # ----- Driver ----------------------------------------------------------
    "route_ready": NotificationSpec(
        title="New trip",
        body=_stops,
        audience=Audience.DRIVER,
        reference_type="route",
        push=True,
    ),
    "driver_assigned": NotificationSpec(
        title="Stop added to your trip",
        body=lambda f: (
            f"{_order_for(f)} was added to your trip"
            + (f" — {f['address']}" if f.get("address") else "")
            + "."
        ),
        audience=Audience.DRIVER,
        reference_type="route",
        # Decided per instance: only a stop added after the trip went out.
        push=False,
    ),
    "stop_cancelled": NotificationSpec(
        title="Stop cancelled",
        body=lambda f: f"{_order_for(f)} was cancelled — skip that stop.",
        audience=Audience.DRIVER,
        reference_type="route",
        push=True,
    ),
    "route_resequenced": NotificationSpec(
        title="Stop order changed",
        body=lambda _f: "The office changed the order of your stops. Check your trip.",
        audience=Audience.DRIVER,
        reference_type="route",
        push=True,
    ),
    "route_cancelled_driver": NotificationSpec(
        title="Trip cancelled",
        body=lambda f: (
            "Your trip"
            + (f" in {f['vehicle_ref']}" if f.get("vehicle_ref") else "")
            + " was cancelled by the office."
        ),
        audience=Audience.DRIVER,
        reference_type="route",
        push=True,
    ),
    # ----- Staff -----------------------------------------------------------
    "order_placed_staff": NotificationSpec(
        title="New order",
        body=lambda f: f"{_order_for(f)} was just placed and is waiting for confirmation.",
        audience=Audience.STAFF,
        permission="orders:confirm",
    ),
    "cancellation_requested_staff": NotificationSpec(
        title="Cancellation waiting for approval",
        body=lambda f: _with_reason(
            f"{_order_for(f)}: cancellation requested — approve or decline it.", f
        ),
        audience=Audience.STAFF,
        permission="orders:cancel_approve",
    ),
    "complaint_raised_staff": NotificationSpec(
        title="New complaint",
        body=lambda f: (
            f"{f.get('complaint_ref') or 'A complaint'}"
            + (f" from {f['customer_name']}" if f.get("customer_name") else "")
            + f": {f.get('category') or 'other'}, {f.get('priority') or 'normal'} priority."
        ),
        audience=Audience.STAFF,
        permission="complaints.manage",
        reference_type="complaint",
    ),
    "complaint_assigned": NotificationSpec(
        title="Complaint assigned to you",
        body=lambda f: (
            f"{f.get('complaint_ref') or 'A complaint'}"
            + (f" from {f['customer_name']}" if f.get("customer_name") else "")
            + f" ({f.get('category') or 'other'}) is now yours to handle."
        ),
        audience=Audience.ASSIGNEE,
        reference_type="complaint",
    ),
    "delivery_failed_staff": NotificationSpec(
        title="Delivery failed",
        body=lambda f: _with_reason(f"{_order_for(f)} could not be delivered.", f),
        audience=Audience.STAFF,
        permission="orders:dispatch",
    ),
    "order_delivered_staff": NotificationSpec(
        title="Order delivered",
        body=lambda f: f"{_order_for(f)} has been delivered.",
        audience=Audience.STAFF,
        permission="orders:dispatch",
    ),
    "order_unassignable_staff": NotificationSpec(
        title="Order needs a trip",
        body=lambda f: (
            f"{_order_for(f)} has no free driver or van in its branch — add it to a trip."
        ),
        audience=Audience.STAFF,
        permission="orders:dispatch",
    ),
    "order_stale_unassigned_staff": NotificationSpec(
        title="Order still waiting for a trip",
        body=lambda f: f"{_order_for(f)} is confirmed but still not on a trip.",
        audience=Audience.STAFF,
        permission="orders:dispatch",
    ),
    "route_started_staff": NotificationSpec(
        title="Trip started",
        body=lambda f: f"{_route(f)} has left the depot.",
        audience=Audience.STAFF,
        permission="orders:dispatch",
        reference_type="route",
    ),
    "route_load_confirmed_staff": NotificationSpec(
        title="Van load checked",
        body=lambda f: f"{_route(f)}: the driver checked the van against the load sheet.",
        audience=Audience.STAFF,
        permission="orders:dispatch",
        reference_type="route",
    ),
    "cash_shortfall_staff": NotificationSpec(
        title="Cash shortfall",
        body=lambda f: (
            f"{_route(f)}: driver handed over {_rupees(f.get('actual_amount'))} of "
            f"{_rupees(f.get('expected_amount'))} — short by {_rupees(f.get('shortfall'))}."
        ),
        audience=Audience.STAFF,
        permission="invoices:record_payment",
        reference_type="cash_handover",
        email=True,
    ),
    "payment_received_staff": NotificationSpec(
        title="Online payment received",
        body=lambda f: (
            f"{_rupees(f.get('amount'))} received online"
            + (f" for {_order_for(f)}" if f.get("order_ref") else "")
            + "."
        ),
        audience=Audience.STAFF,
        permission="invoices:record_payment",
    ),
    "inventory_low_stock_staff": NotificationSpec(
        title="Low stock",
        body=lambda f: (
            f"{f.get('cylinder_name') or 'Filled stock'}"
            + (f" at {f['location_name']}" if f.get("location_name") else "")
            + f" is down to {f.get('on_hand', '?')} (reorder point "
            f"{f.get('reorder_point', '?')}). Time to reorder."
        ),
        audience=Audience.STAFF,
        permission="inventory:adjust",
        reference_type="inventory_location",
        email=True,
    ),
    "compliance_document_expiring_staff": NotificationSpec(
        title="Document expiring",
        body=lambda f: (
            f"A {f.get('owner_type') or 'record'}'s "
            f"{str(f.get('doc_type') or 'document').replace('_', ' ')} expires on "
            f"{f.get('expiry_date') or 'soon'}. Arrange a renewal and upload the replacement."
        ),
        audience=Audience.STAFF,
        permission="compliance:manage",
        reference_type="compliance_document",
    ),
    "lpg_rate_review_staff": NotificationSpec(
        title="New LPG rates to review",
        body=lambda f: (
            f"{f.get('proposal_count') or 'New'} LPG rate proposal"
            f"{'' if f.get('proposal_count') == '1' else 's'} for next month are ready for "
            "review on the Price List page."
        ),
        audience=Audience.STAFF,
        permission="tenant:configure",
        reference_type="price_list_proposal",
        email=True,
    ),
}


def spec_for(notification_type: str) -> NotificationSpec | None:
    return SPECS.get(notification_type)


def sms_variables(facts: Facts) -> dict[str, str]:
    """Values for the DLT template placeholders. Every order SMS template
    takes the same one: the order number also shown in the body."""
    return {"order_ref": facts.get("order_ref") or "your order"}
