"""Repository (and policy) ports for the order bounded context.

`OrderRepository` is the sole aggregate repository. `CancellationRecord` and
`ProofOfDelivery` are entities of the Order aggregate conceptually but are
recorded-once-per-request(-pair) records with no in-memory collection to
load-and-mutate through `Order` itself — the same reasoning
`application/inventory/ports.py` already documents for GRN/
ReconciliationRecord, so their repositories are thin insert/get ports
returning plain read-model dataclasses, not domain objects.

`CylinderCapPolicy`/`CreditLimitEvaluator` are the two BR-04/BR-19 checks
`ConfirmOrderUseCase` runs before `Order.confirm()` — real ports, but their
only implementation this phase (`infrastructure/order/policies.py`) is a
permissive no-op, since both checks genuinely depend on modules that don't
exist yet (Cylinder Ledger — Phase 12; Accounting — Phase 13). See those
classes' own docstrings.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence
    from datetime import datetime
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
    signature_blob_ref: str
    photo_blob_ref: str
    gps_lat: Decimal
    gps_lng: Decimal
    payment_method: str
    amount_collected: Decimal
    recorded_by: uuid.UUID
    recorded_at: datetime


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
    ) -> list[Order]: ...

    async def count_orders(
        self,
        status: str | None = None,
        branch_id: uuid.UUID | None = None,
        customer_id: uuid.UUID | None = None,
        driver_id: uuid.UUID | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> int: ...

    async def list_status_history(self, order_id: uuid.UUID) -> list[OrderStatusHistoryEntry]: ...


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
        """The at-most-one row with `approved_by IS NULL` for this order
        (enforced by a DB partial unique index — see the migration).
        """
        ...

    async def approve(
        self, record_id: uuid.UUID, *, approved_by: uuid.UUID, cancellation_charge: Decimal
    ) -> CancellationRecordEntry: ...


class ProofOfDeliveryRepository(Protocol):
    def next_id(self) -> uuid.UUID: ...

    async def create(
        self,
        *,
        pod_id: uuid.UUID,
        tenant_id: uuid.UUID,
        order_id: uuid.UUID,
        otp_verified_at: datetime,
        signature_blob_ref: str,
        photo_blob_ref: str,
        gps_lat: Decimal,
        gps_lng: Decimal,
        payment_method: str,
        amount_collected: Decimal,
        recorded_by: uuid.UUID,
    ) -> ProofOfDeliveryEntry: ...


class CylinderCapPolicy(Protocol):
    async def evaluate(
        self,
        *,
        tenant_id: uuid.UUID,
        customer_id: uuid.UUID,
        customer_type: str,
        requested_lines: Sequence[tuple[uuid.UUID, int]],
    ) -> None:
        """Raise `CylinderCapExceededError` if this booking would exceed the
        tenant-configured, customer-type-parameterized cylinder holding cap
        (BR-04). Depends on Cylinder Ledger (Phase 12, not built) for the
        customer's current holding count.
        """
        ...


class CreditLimitEvaluator(Protocol):
    async def evaluate(
        self, *, tenant_id: uuid.UUID, customer_id: uuid.UUID, order_total: Decimal
    ) -> None:
        """Raise `CreditLimitExceededError` if outstanding balance +
        `order_total` exceeds the tenant-configured credit limit (BR-19).
        Depends on Accounting (Phase 13, not built) for outstanding balance.
        """
        ...
