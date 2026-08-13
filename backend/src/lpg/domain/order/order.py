"""`Order` aggregate root.

Sole aggregate of the order bounded context (`01-domain-model.md` §4.3).
"Booking" is the business term for an Order prior to `confirmed` — there is
no separate Booking entity/table. `OrderLine` is an in-aggregate mutable
collection (mirrors `Customer._addresses`); `OrderStatusHistory` and
`FailedDeliveryRecord` are append-only, no-in-memory-collection entities
following the exact "pending list" pattern `InventoryLocation.
_pending_transactions`/`InventoryTransactionRecord` already established.
`CancellationRecord` is deliberately **not** modeled here — see
`application/order/ports.py`'s `CancellationRecordRepository` docstring for
why it needs a repository of its own instead.

docs/data/01-domain-model.md §4.3, docs/data/08-state-machines.md §2
"""

from __future__ import annotations

import uuid  # noqa: TC003
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from lpg.domain.common.base import AggregateRoot, DomainEvent, InvariantViolation

if TYPE_CHECKING:
    from collections.abc import Sequence

# ---------------------------------------------------------------------------
# Domain Events
#
# Canonical names/payloads match docs/data/09-domain-events.md exactly even
# where this module is a *temporary* publisher standing in for a module that
# didn't exist yet at the time it was written (Delivery — now real, Phase
# 12; Cylinder Ledger/Accounting — Phase 13/14) — so those phases can
# subscribe later without a rename. `route_stop_id` fields are populated for
# real now that `delivery.route`/`route_stop` exist.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BookingCreated(DomainEvent):
    order_id: uuid.UUID
    tenant_id: uuid.UUID
    customer_id: uuid.UUID
    booking_source: str
    requested_date: datetime


@dataclass(frozen=True, slots=True)
class BookingCancelled(DomainEvent):
    order_id: uuid.UUID
    cancelled_by: uuid.UUID
    approved_by: uuid.UUID | None
    reason: str
    cancellation_charge: Decimal | None


@dataclass(frozen=True, slots=True)
class InventoryReserved(DomainEvent):
    """Published by Order Management at assignment (`confirmed -> assigned`).

    Keyed by `order_id` + `route_stop_id` (`delivery.route`/`route_stop` are
    real as of Phase 12 — this event was keyed by `vehicle_id` in Phase 11 as
    an interim substitute; now it carries the canonical `route_stop_id`).
    Idempotency is structural, not Redis-backed: `assign()` only fires from
    `confirmed`, so a duplicate call on an already-`assigned` order fails
    `INVALID_STATE_TRANSITION` before any reservation math runs.
    """

    order_id: uuid.UUID
    tenant_id: uuid.UUID
    route_stop_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class DeliveryFailed(DomainEvent):
    """Canonical publisher is Delivery Management — Order Management
    publishes it directly since the two bounded contexts share this
    transition's triggering endpoint (`POST /orders/{id}/failed-delivery`).
    `route_stop_id` is `None` only when the order was never assigned a
    route stop (should not happen once `out_for_delivery`, kept nullable
    defensively).
    """

    order_id: uuid.UUID
    route_stop_id: uuid.UUID | None
    reason_code: str
    recorded_by: uuid.UUID


@dataclass(frozen=True, slots=True)
class CylinderDelivered(DomainEvent):
    """Canonical publisher is Delivery Management — Order Management
    publishes it directly since the two bounded contexts share this
    transition's triggering endpoint (`POST /orders/{id}/deliver`).
    Cylinder Ledger (Phase 13) and Accounting (Phase 14) will subscribe
    once they exist; until then this event has no consumers.
    """

    order_id: uuid.UUID
    tenant_id: uuid.UUID
    customer_id: uuid.UUID
    route_stop_id: uuid.UUID | None
    delivered_at: datetime


@dataclass(frozen=True, slots=True)
class OrderClosed(DomainEvent):
    """New in this phase — `delivered -> closed` is normally automated by
    Accounting on full invoice settlement (Phase 13, not built); until then
    it's a manual action, still worth its own event for whichever consumer
    wants to know an order's lifecycle is fully done.
    """

    order_id: uuid.UUID
    closed_by: uuid.UUID


# ---------------------------------------------------------------------------
# Domain errors
# ---------------------------------------------------------------------------


class InvalidOrderStatusTransitionError(InvariantViolation):
    """The requested order status transition is not permitted (BR-07)."""

    error_code = "INVALID_STATE_TRANSITION"


class InsufficientVehicleStockError(InvariantViolation):
    """A delivery was attempted for more than was reserved for this line (BR-09)."""

    error_code = "INSUFFICIENT_VEHICLE_STOCK"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ORDER_STATUSES: frozenset[str] = frozenset(
    {
        "draft",
        "booked",
        "confirmed",
        "assigned",
        "ready_for_dispatch",
        "out_for_delivery",
        "delivered",
        "failed_delivery",
        "cancelled",
        "closed",
    }
)

BOOKING_SOURCES: frozenset[str] = frozenset(
    {"mobile_app", "staff", "phone", "walk_in", "whatsapp", "api"}
)

PAYMENT_METHODS: frozenset[str] = frozenset({"cash", "upi", "card", "online_gateway", "credit"})

# D-12's exact 5 failed-delivery reason codes / 3 resolution actions.
FAILED_DELIVERY_REASON_CODES: frozenset[str] = frozenset(
    {"customer_unavailable", "wrong_address", "payment_refused", "vehicle_issue", "safety_issue"}
)
FAILED_DELIVERY_RESOLUTION_ACTIONS: frozenset[str] = frozenset(
    {"reschedule", "cancel", "return_stock"}
)

# D-07's 10-state machine, docs/data/08-state-machines.md §2 exactly. Every
# edge that reaches "cancelled" is present here (both free and
# approval-required paths use the same target status) — the free/approval
# split is enforced separately, by `_FREE_CANCEL_STATES`/
# `_APPROVAL_CANCEL_STATES`, since the transition graph alone can't express
# "this edge needs Manager approval first."
_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"booked"}),
    "booked": frozenset({"confirmed", "cancelled"}),
    "confirmed": frozenset({"assigned", "cancelled"}),
    "assigned": frozenset({"ready_for_dispatch", "cancelled"}),
    "ready_for_dispatch": frozenset({"out_for_delivery", "cancelled"}),
    "out_for_delivery": frozenset({"delivered", "failed_delivery", "cancelled"}),
    "failed_delivery": frozenset({"ready_for_dispatch", "cancelled"}),
    "delivered": frozenset({"closed"}),
    "cancelled": frozenset(),
    "closed": frozenset(),
}

# D-19: free cancellation before dispatch; Manager approval (+ possible fee)
# required once a vehicle has actually left with the order.
_FREE_CANCEL_STATES: frozenset[str] = frozenset(
    {"booked", "confirmed", "assigned", "ready_for_dispatch"}
)
_APPROVAL_CANCEL_STATES: frozenset[str] = frozenset({"out_for_delivery", "failed_delivery"})


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DeliveryAddress:
    """A frozen snapshot of the customer address at booking time — the
    customer's own address record may change or be deleted later without
    silently altering a past order's delivery destination.
    """

    address_line: str
    latitude: float | None = None
    longitude: float | None = None


@dataclass(frozen=True, slots=True)
class DeliveredLine:
    """One line of the `deliver()` command's input — not persisted directly;
    `Order.deliver()` applies each entry to the matching `OrderLine`.
    """

    cylinder_type_id: uuid.UUID
    quantity_delivered: int
    quantity_collected_empty: int = 0


@dataclass(frozen=True, slots=True)
class OrderStatusHistoryEntry:
    """One append-only `order_status_history` row produced by a transition.

    Returned via `Order.pending_status_history` rather than derived from
    domain events, matching `InventoryLocation.pending_transactions`'
    reasoning exactly: events dispatch *after* commit, but this row must be
    written in the *same* database transaction as the status change it
    records.
    """

    from_status: str | None
    to_status: str
    changed_by: uuid.UUID
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class FailedDeliveryEntry:
    """One append-only `failed_delivery_record` row, produced by `fail_delivery()`."""

    reason_code: str
    resolution_action: str | None
    recorded_by: uuid.UUID


class OrderLine:
    """A single cylinder-type line within an Order.

    Mutated in place across three transitions: `confirm()` sets
    `unit_price`; `assign()` sets `is_backordered`/`quantity_pending`;
    `deliver()` sets `quantity_delivered`/`quantity_collected_empty`. Owned
    exclusively by `Order` — never loaded or persisted independently.
    """

    def __init__(
        self,
        line_id: uuid.UUID,
        cylinder_type_id: uuid.UUID,
        quantity_ordered: int,
        unit_price: Decimal | None = None,
        quantity_delivered: int = 0,
        quantity_pending: int = 0,
        quantity_collected_empty: int = 0,
        is_backordered: bool = False,
    ) -> None:
        if quantity_ordered < 1:
            msg = f"Quantity ordered must be at least 1, got {quantity_ordered}."
            raise InvariantViolation(msg)
        if quantity_delivered + quantity_pending > quantity_ordered:
            msg = "Delivered quantity plus pending quantity cannot exceed quantity ordered."
            raise InvariantViolation(msg)

        self.id = line_id
        self.cylinder_type_id = cylinder_type_id
        self.quantity_ordered = quantity_ordered
        self.unit_price = unit_price
        self.quantity_delivered = quantity_delivered
        self.quantity_pending = quantity_pending
        self.quantity_collected_empty = quantity_collected_empty
        self.is_backordered = is_backordered

    def set_unit_price(self, price: Decimal) -> None:
        if price <= 0:
            msg = f"Unit price must be greater than zero, got {price}."
            raise InvariantViolation(msg)
        self.unit_price = price

    def allocate(self, reserved: int, pending: int) -> None:
        """Set at `assign()` — `reserved` is fulfillable now, `pending` is
        backordered (D-08). The two must always account for the full
        quantity ordered.
        """
        if reserved < 0 or pending < 0:
            msg = "Reserved/pending quantities cannot be negative."
            raise InvariantViolation(msg)
        if reserved + pending != self.quantity_ordered:
            msg = (
                f"Reserved ({reserved}) + pending ({pending}) must equal "
                f"quantity ordered ({self.quantity_ordered})."
            )
            raise InvariantViolation(msg)
        self.quantity_pending = pending
        self.is_backordered = pending > 0

    def record_delivery(self, quantity_delivered: int, quantity_collected_empty: int) -> None:
        if quantity_delivered < 0 or quantity_collected_empty < 0:
            msg = "Delivered/collected quantities cannot be negative."
            raise InvariantViolation(msg)
        reserved = self.quantity_ordered - self.quantity_pending
        if quantity_delivered > reserved:
            msg = (
                f"Cannot deliver {quantity_delivered} for cylinder type "
                f"{self.cylinder_type_id} — only {reserved} was reserved."
            )
            raise InsufficientVehicleStockError(
                msg,
                cylinder_type_id=str(self.cylinder_type_id),
                requested=quantity_delivered,
                available=reserved,
            )
        self.quantity_delivered = quantity_delivered
        self.quantity_collected_empty = quantity_collected_empty


# ---------------------------------------------------------------------------
# Aggregate root
# ---------------------------------------------------------------------------


class Order(AggregateRoot):
    """A customer's cylinder booking, tracked through the D-07 10-state
    lifecycle.

    Business invariants:
    - Status only moves along `_TRANSITIONS` edges — every other request is
      rejected with `InvalidOrderStatusTransitionError` (BR-07).
    - Cancellation from `_APPROVAL_CANCEL_STATES` (post-dispatch) must go
      through `request_cancellation_approval()`/`approve_cancellation()`,
      never `cancel_free()` (D-19).
    - `deliver()` never lets a line's delivered quantity exceed what was
      actually reserved for it at assignment (BR-09).
    """

    __slots__ = (
        "_address_id",
        "_booking_source",
        "_branch_id",
        "_customer_id",
        "_delivery_address",
        "_lines",
        "_metadata",
        "_payment_method_preference",
        "_pending_failed_delivery_entries",
        "_pending_status_history",
        "_requested_date",
        "_route_stop_id",
        "_status",
        "_tenant_id",
        "_total_amount",
    )

    def __init__(
        self,
        *,
        order_id: uuid.UUID,
        tenant_id: uuid.UUID,
        branch_id: uuid.UUID,
        customer_id: uuid.UUID,
        address_id: uuid.UUID,
        delivery_address: DeliveryAddress,
        booking_source: str,
        requested_date: datetime,
        lines: Sequence[OrderLine],
        payment_method_preference: str | None = None,
        metadata: dict[str, Any] | None = None,
        status: str = "draft",
        route_stop_id: uuid.UUID | None = None,
        total_amount: Decimal | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(order_id, version=version)

        self._validate_booking_source(booking_source)
        if status not in ORDER_STATUSES:
            msg = f"Invalid order status: {status}"
            raise InvariantViolation(msg, order_id=str(order_id))
        _valid_payment_method = (
            payment_method_preference is None or payment_method_preference in PAYMENT_METHODS
        )
        if not _valid_payment_method:
            msg = f"Invalid payment method: {payment_method_preference}"
            raise InvariantViolation(msg, order_id=str(order_id))
        if not lines:
            msg = "An order must have at least one line."
            raise InvariantViolation(msg, order_id=str(order_id))
        cylinder_type_ids = [line.cylinder_type_id for line in lines]
        if len(cylinder_type_ids) != len(set(cylinder_type_ids)):
            # `assign()`/`VehicleCapacityChecker.allocate()` key reservations
            # by cylinder_type_id — a second line for the same type would
            # silently collide with the first rather than getting its own
            # share. A real duplicate need should increase the one line's
            # quantity instead.
            msg = "An order cannot have two lines for the same cylinder type."
            raise InvariantViolation(msg, order_id=str(order_id))

        self._tenant_id = tenant_id
        self._branch_id = branch_id
        self._customer_id = customer_id
        self._address_id = address_id
        self._delivery_address = delivery_address
        self._booking_source = booking_source
        self._payment_method_preference = payment_method_preference
        self._requested_date = requested_date
        self._metadata = dict(metadata or {})
        self._status = status
        self._route_stop_id = route_stop_id
        self._total_amount = total_amount
        self._lines = list(lines)
        self._pending_status_history: list[OrderStatusHistoryEntry] = []
        self._pending_failed_delivery_entries: list[FailedDeliveryEntry] = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def tenant_id(self) -> uuid.UUID:
        return self._tenant_id

    @property
    def branch_id(self) -> uuid.UUID:
        return self._branch_id

    @property
    def customer_id(self) -> uuid.UUID:
        return self._customer_id

    @property
    def address_id(self) -> uuid.UUID:
        return self._address_id

    @property
    def delivery_address(self) -> DeliveryAddress:
        return self._delivery_address

    @property
    def status(self) -> str:
        return self._status

    @property
    def booking_source(self) -> str:
        return self._booking_source

    @property
    def payment_method_preference(self) -> str | None:
        return self._payment_method_preference

    @property
    def requested_date(self) -> datetime:
        return self._requested_date

    @property
    def metadata(self) -> dict[str, Any]:
        return dict(self._metadata)

    @property
    def route_stop_id(self) -> uuid.UUID | None:
        return self._route_stop_id

    @property
    def total_amount(self) -> Decimal | None:
        return self._total_amount

    @property
    def lines(self) -> list[OrderLine]:
        return list(self._lines)

    @property
    def pending_status_history(self) -> tuple[OrderStatusHistoryEntry, ...]:
        """Rows produced since the last `clear_pending_status_history()`."""
        return tuple(self._pending_status_history)

    @property
    def pending_failed_delivery_entries(self) -> tuple[FailedDeliveryEntry, ...]:
        """Rows produced since the last `clear_pending_failed_delivery_entries()`."""
        return tuple(self._pending_failed_delivery_entries)

    def clear_pending_status_history(self) -> None:
        """Called by the repository once history rows have been persisted."""
        self._pending_status_history.clear()

    def clear_pending_failed_delivery_entries(self) -> None:
        """Called by the repository once failed-delivery rows have been persisted."""
        self._pending_failed_delivery_entries.clear()

    @property
    def can_cancel_free(self) -> bool:
        """Whether `cancel_free()` would succeed from the current status —
        lets a use case pick the free-vs-approval cancellation path without
        reaching into `_TRANSITIONS`/`_FREE_CANCEL_STATES` directly.
        """
        return self._status in _FREE_CANCEL_STATES

    @property
    def requires_cancellation_approval(self) -> bool:
        """Whether cancelling now must go through `request_cancellation_approval()`/
        `approve_cancellation()` instead of `cancel_free()` (D-19).
        """
        return self._status in _APPROVAL_CANCEL_STATES

    def line_for(self, cylinder_type_id: uuid.UUID) -> OrderLine:
        for line in self._lines:
            if line.cylinder_type_id == cylinder_type_id:
                return line
        msg = f"Order {self.id} has no line for cylinder type {cylinder_type_id}."
        raise InvariantViolation(msg, order_id=str(self.id), cylinder_type_id=str(cylinder_type_id))

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def submit(self, *, changed_by: uuid.UUID) -> None:
        """`draft -> booked`."""
        self._transition("booked", changed_by=changed_by)
        self.record_event(
            BookingCreated(
                order_id=self.id,
                tenant_id=self._tenant_id,
                customer_id=self._customer_id,
                booking_source=self._booking_source,
                requested_date=self._requested_date,
            )
        )

    def confirm(self, *, unit_prices: dict[uuid.UUID, Decimal], changed_by: uuid.UUID) -> None:
        """`booked -> confirmed`. Snapshots each line's price — never
        re-resolved retroactively — and computes `total_amount`. BR-04
        (cylinder cap) / BR-19 (credit limit) are checked by the use case
        before this is called; they depend on modules that don't exist yet
        (see `application/order/ports.py`'s `CylinderCapPolicy`/
        `CreditLimitEvaluator`).
        """
        self._ensure_transition_allowed("confirmed")

        total = Decimal("0")
        for line in self._lines:
            price = unit_prices.get(line.cylinder_type_id)
            if price is None:
                msg = f"No price configured for cylinder type {line.cylinder_type_id}."
                raise InvariantViolation(
                    msg, order_id=str(self.id), cylinder_type_id=str(line.cylinder_type_id)
                )
            line.set_unit_price(price)
            total += price * line.quantity_ordered
        self._total_amount = total

        self._apply_transition("confirmed", changed_by=changed_by)

    def assign(
        self,
        *,
        route_stop_id: uuid.UUID,
        reservations: dict[uuid.UUID, int],
        backorders: dict[uuid.UUID, int],
        changed_by: uuid.UUID,
    ) -> None:
        """`confirmed -> assigned`. `reservations`/`backorders` come from
        `VehicleCapacityChecker.allocate()` — the use case is responsible
        for actually debiting the vehicle's `InventoryLocation` in the same
        atomic operation (this method only updates the Order's own state).
        `route_stop_id` identifies the `delivery.route_stop` the use case
        created/attached for this order — Order stores the FK, RouteStop
        (owned by the `Route` aggregate) is the source of truth for which
        driver/vehicle/route this order rides on.
        """
        self._ensure_transition_allowed("assigned")

        for line in self._lines:
            reserved = reservations.get(line.cylinder_type_id, 0)
            pending = backorders.get(line.cylinder_type_id, 0)
            line.allocate(reserved, pending)

        self._route_stop_id = route_stop_id
        self._apply_transition("assigned", changed_by=changed_by)
        self.record_event(
            InventoryReserved(
                order_id=self.id, tenant_id=self._tenant_id, route_stop_id=route_stop_id
            )
        )

    def dispatch(self, *, changed_by: uuid.UUID) -> None:
        """`assigned -> ready_for_dispatch` ("vehicle loaded")."""
        self._transition("ready_for_dispatch", changed_by=changed_by)

    def depart(self, *, changed_by: uuid.UUID) -> None:
        """`ready_for_dispatch -> out_for_delivery` ("driver departs")."""
        self._transition("out_for_delivery", changed_by=changed_by)

    def deliver(self, *, lines: Sequence[DeliveredLine], changed_by: uuid.UUID) -> None:
        """`out_for_delivery -> delivered`. POD completeness (OTP,
        signature, photo, GPS) is validated by the use case, not here — see
        `domain/order/order.py`'s module docstring / the plan's layering
        note on why that split exists (`problem_details` maps every
        `DomainError` to 409, but BR-08 documents a 400 for incomplete POD).
        """
        self._ensure_transition_allowed("delivered")

        for delivered in lines:
            line = self.line_for(delivered.cylinder_type_id)
            line.record_delivery(delivered.quantity_delivered, delivered.quantity_collected_empty)

        self._apply_transition("delivered", changed_by=changed_by)
        self.record_event(
            CylinderDelivered(
                order_id=self.id,
                tenant_id=self._tenant_id,
                customer_id=self._customer_id,
                route_stop_id=self._route_stop_id,
                delivered_at=datetime.now(UTC),
            )
        )

    def fail_delivery(
        self, *, reason_code: str, resolution_action: str | None, recorded_by: uuid.UUID
    ) -> None:
        """`out_for_delivery -> failed_delivery` (D-12)."""
        self._ensure_transition_allowed("failed_delivery")
        self._validate_failed_delivery_reason_code(reason_code)
        if resolution_action is not None:
            self._validate_resolution_action(resolution_action)

        self._pending_failed_delivery_entries.append(
            FailedDeliveryEntry(
                reason_code=reason_code,
                resolution_action=resolution_action,
                recorded_by=recorded_by,
            )
        )
        self._apply_transition("failed_delivery", changed_by=recorded_by)
        self.record_event(
            DeliveryFailed(
                order_id=self.id,
                route_stop_id=self._route_stop_id,
                reason_code=reason_code,
                recorded_by=recorded_by,
            )
        )

    def reschedule(self, *, changed_by: uuid.UUID) -> None:
        """`failed_delivery -> ready_for_dispatch`."""
        self._transition("ready_for_dispatch", changed_by=changed_by)

    def cancel_free(self, *, cancelled_by: uuid.UUID, reason: str) -> None:
        """Free cancellation — only from `_FREE_CANCEL_STATES` (D-19)."""
        if self._status not in _FREE_CANCEL_STATES:
            msg = f"Order cannot be freely cancelled from status '{self._status}'."
            raise InvalidOrderStatusTransitionError(
                msg, order_id=str(self.id), from_status=self._status, to_status="cancelled"
            )
        self._transition("cancelled", changed_by=cancelled_by, reason=reason)
        self.record_event(
            BookingCancelled(
                order_id=self.id,
                cancelled_by=cancelled_by,
                approved_by=None,
                reason=reason,
                cancellation_charge=None,
            )
        )

    def request_cancellation_approval(self, *, reason: str) -> None:
        """Pure guard — only from `_APPROVAL_CANCEL_STATES` (D-19). Status
        is unchanged; the use case creates the pending `CancellationRecord`.
        """
        if self._status not in _APPROVAL_CANCEL_STATES:
            msg = (
                f"Order cancellation from status '{self._status}' does not "
                "require Manager approval — use cancel_free() instead."
            )
            raise InvariantViolation(msg, order_id=str(self.id), status=self._status)
        if not reason.strip():
            msg = "Cancellation reason cannot be empty."
            raise InvariantViolation(msg, order_id=str(self.id))

    def approve_cancellation(
        self, *, approved_by: uuid.UUID, cancellation_charge: Decimal, reason: str
    ) -> None:
        """Resolves a pending approval-required cancellation (D-19)."""
        if self._status not in _APPROVAL_CANCEL_STATES:
            msg = f"Order cannot be cancelled-with-approval from status '{self._status}'."
            raise InvalidOrderStatusTransitionError(
                msg, order_id=str(self.id), from_status=self._status, to_status="cancelled"
            )
        if cancellation_charge < 0:
            msg = f"Cancellation charge cannot be negative, got {cancellation_charge}."
            raise InvariantViolation(msg, order_id=str(self.id))

        self._transition("cancelled", changed_by=approved_by, reason=reason)
        self.record_event(
            BookingCancelled(
                order_id=self.id,
                cancelled_by=approved_by,
                approved_by=approved_by,
                reason=reason,
                cancellation_charge=cancellation_charge,
            )
        )

    def close(self, *, closed_by: uuid.UUID) -> None:
        """`delivered -> closed` — manual interim action pending Phase 13's
        automatic invoice-settlement trigger.
        """
        self._transition("closed", changed_by=closed_by)
        self.record_event(OrderClosed(order_id=self.id, closed_by=closed_by))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _transition(
        self, to_status: str, *, changed_by: uuid.UUID, reason: str | None = None
    ) -> None:
        """Validates *and* performs — for the transition methods that don't
        mutate any other aggregate state first (`submit`/`dispatch`/
        `depart`/`reschedule`/`cancel_free`/`approve_cancellation`/`close`).
        Methods that also mutate line data (`confirm`/`assign`/
        `fail_delivery`/`deliver`) call `_ensure_transition_allowed()` up
        front instead, so an illegal transition is rejected with
        `INVALID_STATE_TRANSITION` before any line is touched, then
        `_apply_transition()` once their own mutation has succeeded.
        """
        self._ensure_transition_allowed(to_status)
        self._apply_transition(to_status, changed_by=changed_by, reason=reason)

    def _ensure_transition_allowed(self, to_status: str) -> None:
        allowed = _TRANSITIONS.get(self._status, frozenset())
        if to_status not in allowed:
            msg = f"Cannot transition order from '{self._status}' to '{to_status}'."
            raise InvalidOrderStatusTransitionError(
                msg, order_id=str(self.id), from_status=self._status, to_status=to_status
            )

    def _apply_transition(
        self, to_status: str, *, changed_by: uuid.UUID, reason: str | None = None
    ) -> None:
        from_status = self._status
        self._status = to_status
        self._pending_status_history.append(
            OrderStatusHistoryEntry(
                from_status=from_status, to_status=to_status, changed_by=changed_by, reason=reason
            )
        )

    @staticmethod
    def _validate_booking_source(value: str) -> None:
        if value not in BOOKING_SOURCES:
            msg = (
                f"Invalid booking source '{value}'. "
                f"Must be one of: {', '.join(sorted(BOOKING_SOURCES))}."
            )
            raise InvariantViolation(msg)

    @staticmethod
    def _validate_failed_delivery_reason_code(value: str) -> None:
        if value not in FAILED_DELIVERY_REASON_CODES:
            msg = (
                f"Invalid failed-delivery reason code '{value}'. "
                f"Must be one of: {', '.join(sorted(FAILED_DELIVERY_REASON_CODES))}."
            )
            raise InvariantViolation(msg)

    @staticmethod
    def _validate_resolution_action(value: str) -> None:
        if value not in FAILED_DELIVERY_RESOLUTION_ACTIONS:
            msg = (
                f"Invalid failed-delivery resolution action '{value}'. "
                f"Must be one of: {', '.join(sorted(FAILED_DELIVERY_RESOLUTION_ACTIONS))}."
            )
            raise InvariantViolation(msg)
