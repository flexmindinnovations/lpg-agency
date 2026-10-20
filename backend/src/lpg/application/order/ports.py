"""Repository (and policy) ports for the order bounded context.

`OrderRepository` is the sole aggregate repository. `CancellationRecord` and
`ProofOfDelivery` are entities of the Order aggregate conceptually but are
recorded-once-per-request(-pair) records with no in-memory collection to
load-and-mutate through `Order` itself — the same reasoning
`application/inventory/ports.py` already documents for GRN/
ReconciliationRecord, so their repositories are thin insert/get ports
returning plain read-model dataclasses, not domain objects.

`CylinderCapPolicy`/`CreditLimitEvaluator` are the BR-04/BR-19 checks run
when an order is booked, edited and confirmed; their implementation is
`application/order/booking_policies.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence
    from datetime import datetime, timedelta
    from decimal import Decimal

    from lpg.domain.order.order import Order


@dataclass(frozen=True, slots=True)
class CancellationRecordEntry:
    id: uuid.UUID
    tenant_id: uuid.UUID
    order_id: uuid.UUID
    cancelled_by: uuid.UUID
    approved_by: uuid.UUID | None
    cancellation_charge: Decimal | None
    reason: str
    requested_at: datetime
    approved_at: datetime | None
    rejected_by: uuid.UUID | None = None
    rejected_at: datetime | None = None
    rejection_reason: str | None = None

    @property
    def status(self) -> str:
        """`pending` until a Manager approves or rejects it (DO-14)."""
        if self.approved_by is not None:
            return "approved"
        if self.rejected_by is not None:
            return "rejected"
        return "pending"


@dataclass(frozen=True, slots=True)
class OrderCustomerSummary:
    """Who an order is for, as the order screens show it (DO-12)."""

    customer_id: uuid.UUID
    full_name: str
    phone_number: str
    consumer_number: str | None
    customer_type: str


@dataclass(frozen=True, slots=True)
class OrderStatusHistoryEntry:
    id: uuid.UUID
    order_id: uuid.UUID
    from_status: str | None
    to_status: str
    changed_by: uuid.UUID
    changed_at: datetime
    reason: str | None


@dataclass(frozen=True, slots=True)
class ProofOfDeliveryEntry:
    id: uuid.UUID
    tenant_id: uuid.UUID
    order_id: uuid.UUID
    otp_verified_at: datetime
    signature_blob_ref: str | None
    photo_blob_ref: str | None
    gps_lat: Decimal
    gps_lng: Decimal
    payment_method: str
    amount_collected: Decimal
    recorded_by: uuid.UUID
    recorded_at: datetime
    # Delivery Authentication Code (Phase 20 subsystem 4) — the OMC's own
    # separate 6-digit code, distinct from `otp_verified_at`'s internal OTP.
    # Optional and never gates delivery — see `domain/order/order.py`'s own
    # note that POD completeness is a use-case concern, not a domain one.
    dac_code: str | None = None


class OrderNumberSequence(Protocol):
    """Generates the next tenant-scoped, human-readable order number
    (`ORD000001`). Backed by the shared `SqlAlchemyReferenceNumberSequence`
    (see `infrastructure/persistence/repositories/reference_number.py`) —
    never manually overridden, so no collision-check is needed by the
    caller.
    """

    async def next(self) -> str: ...


class OrderRepository(Protocol):
    def next_id(self) -> uuid.UUID: ...

    async def save(self, order: Order) -> None: ...

    async def get_by_id(self, order_id: uuid.UUID) -> Order | None: ...

    async def list_orders(
        self,
        skip: int = 0,
        limit: int = 50,
        status: str | None = None,
        branch_id: uuid.UUID | None = None,
        customer_id: uuid.UUID | None = None,
        driver_id: uuid.UUID | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        search: str | None = None,
    ) -> list[Order]: ...

    async def count_orders(
        self,
        status: str | None = None,
        branch_id: uuid.UUID | None = None,
        customer_id: uuid.UUID | None = None,
        driver_id: uuid.UUID | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        search: str | None = None,
    ) -> int: ...

    async def list_status_history(self, order_id: uuid.UUID) -> list[OrderStatusHistoryEntry]: ...

    async def list_stale_unassigned(self, stale_after: timedelta) -> list[Order]:
        """Orders still `confirmed` (unassigned, by construction --
        `route_stop_id` is only ever set by `assign()`) whose `confirmed`
        transition happened before `stale_after` ago, and which haven't
        already been notified within that same window
        (`last_stale_notified_at`) -- the stale-unassigned-order alert
        cron's (`infrastructure/jobs/stale_order_jobs.py`) work list.
        """
        ...

    async def mark_stale_notified(self, order_id: uuid.UUID) -> None: ...


class CancellationRecordRepository(Protocol):
    def next_id(self) -> uuid.UUID: ...

    async def create(
        self,
        *,
        record_id: uuid.UUID,
        tenant_id: uuid.UUID,
        order_id: uuid.UUID,
        cancelled_by: uuid.UUID,
        reason: str,
    ) -> CancellationRecordEntry: ...

    async def get_pending_by_order_id(self, order_id: uuid.UUID) -> CancellationRecordEntry | None:
        """The at-most-one row neither approved nor rejected for this order
        (enforced by a DB partial unique index — see the migrations).
        """
        ...

    async def get_latest_by_order_id(self, order_id: uuid.UUID) -> CancellationRecordEntry | None:
        """The most recent request for this order, whatever its outcome."""
        ...

    async def pending_order_ids(self, order_ids: Sequence[uuid.UUID]) -> set[uuid.UUID]:
        """Which of `order_ids` have a request waiting for a decision."""
        ...

    async def approve(
        self, record_id: uuid.UUID, *, approved_by: uuid.UUID, cancellation_charge: Decimal
    ) -> CancellationRecordEntry: ...

    async def reject(
        self, record_id: uuid.UUID, *, rejected_by: uuid.UUID, reason: str
    ) -> CancellationRecordEntry: ...


class OrderCustomerDirectory(Protocol):
    async def summaries(
        self, customer_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, OrderCustomerSummary]:
        """Name, phone and consumer number for each visible customer."""
        ...


class ProofOfDeliveryRepository(Protocol):
    def next_id(self) -> uuid.UUID: ...

    async def create(
        self,
        *,
        pod_id: uuid.UUID,
        tenant_id: uuid.UUID,
        order_id: uuid.UUID,
        otp_verified_at: datetime,
        signature_blob_ref: str | None,
        photo_blob_ref: str | None,
        gps_lat: Decimal,
        gps_lng: Decimal,
        payment_method: str,
        amount_collected: Decimal,
        recorded_by: uuid.UUID,
        dac_code: str | None = None,
    ) -> ProofOfDeliveryEntry: ...

    async def get_by_order_id(self, order_id: uuid.UUID) -> ProofOfDeliveryEntry | None: ...


class CylinderCapPolicy(Protocol):
    async def evaluate(
        self,
        *,
        tenant_id: uuid.UUID,
        customer_id: uuid.UUID,
        customer_type: str,
        requested_lines: Sequence[tuple[uuid.UUID, int]],
        exclude_order_id: uuid.UUID | None = None,
    ) -> None:
        """Raise `CylinderCapExceededError` if this booking would exceed the
        tenant-configured, customer-type-parameterized cylinder holding cap
        (BR-04). `exclude_order_id` leaves an existing order's own lines out
        of the customer's open orders when that order is confirmed or edited.
        """
        ...


class CreditLimitEvaluator(Protocol):
    async def evaluate(
        self,
        *,
        tenant_id: uuid.UUID,
        customer_id: uuid.UUID,
        customer_type: str,
        order_total: Decimal,
    ) -> None:
        """Raise `CreditLimitExceededError` if outstanding balance +
        `order_total` exceeds the tenant-configured credit limit for the
        customer's type (BR-19, D-11).
        """
        ...


class CustomerOpenOrderReader(Protocol):
    async def open_quantities(
        self, customer_id: uuid.UUID, *, exclude_order_id: uuid.UUID | None = None
    ) -> dict[uuid.UUID, int]:
        """Cylinders per type the customer's open orders (booked up to out for
        delivery, and failed deliveries awaiting a retry) will still deliver.
        """
        ...


class BranchStockReader(Protocol):
    async def lock_branch_for_booking(self, branch_id: uuid.UUID) -> None:
        """Hold the branch's booking lock until the current transaction ends.

        Every booking or confirmation at the branch takes it before reading
        the available stock, so two of them cannot both see the last
        cylinders as free and both commit: the second waits until the first
        has committed its order (or rolled back), then reads the stock again.
        """
        ...

    async def available_filled_by_cylinder_type(
        self, branch_id: uuid.UUID, *, exclude_order_id: uuid.UUID | None = None
    ) -> dict[uuid.UUID, int]:
        """Filled cylinders a new booking at `branch_id` can still claim, per
        cylinder type: filled stock in the branch's active warehouses and on
        its vehicles (vehicle stock is already net of reservations made at
        assignment), minus what open orders at the branch have booked but not
        yet reserved. `exclude_order_id` leaves one order's own demand out,
        so confirming an order is not blocked by its own booking. A type
        with no stock may be missing from the result or be zero or less.
        """
        ...
