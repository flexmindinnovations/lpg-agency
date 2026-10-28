"""Accounting repository ports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import uuid
    from datetime import datetime
    from decimal import Decimal

    from lpg.application.order.ports import ProofOfDeliveryEntry
    from lpg.domain.accounting.cash_handover import CashHandover, CashHandoverReview
    from lpg.domain.accounting.credit_note import CreditNote
    from lpg.domain.accounting.invoice import Invoice
    from lpg.domain.accounting.online_payment import OnlinePayment


class InvoiceNumberSequence(Protocol):
    """Generates the next tenant-scoped, human-readable invoice number
    (`INV-2026-000001`). Backed by the shared
    `SqlAlchemyReferenceNumberSequence` — see that class for the upsert
    mechanic. Unlike `ConsumerNumberSequence`, invoice numbers are never
    manually overridden, so no collision-check is needed by the caller;
    the sequence's own atomic upsert is sufficient.
    """

    async def next(self) -> str: ...


class CreditNoteNumberSequence(Protocol):
    """Generates the next tenant-scoped credit note number (`CRN-2026-000001`)."""

    async def next(self) -> str: ...


class CashHandoverNumberSequence(Protocol):
    """Generates the next tenant-scoped cash handover number (`CSH000001`)."""

    async def next(self) -> str: ...


class InvoiceRepository(Protocol):
    """Repository for the `Invoice` aggregate."""

    async def add(self, invoice: Invoice) -> None:
        """Add a new invoice.

        Args:
            invoice: The aggregate to save.
        """

    async def save(self, invoice: Invoice) -> None:
        """Persist changes to an existing invoice — `status` and any newly
        recorded `payments` (R10). Never used for the initial creation.
        """

    async def get_by_id(self, invoice_id: uuid.UUID) -> Invoice | None: ...

    async def list_invoices(
        self,
        skip: int = 0,
        limit: int = 50,
        customer_id: uuid.UUID | None = None,
        order_id: uuid.UUID | None = None,
        status: str | None = None,
        issued_from: datetime | None = None,
        issued_to: datetime | None = None,
        search: str | None = None,
    ) -> list[Invoice]:
        """Newest first. `search` matches invoice, order and consumer
        numbers and the customer's name; `issued_to` is exclusive.
        """

    async def count_invoices(
        self,
        customer_id: uuid.UUID | None = None,
        order_id: uuid.UUID | None = None,
        status: str | None = None,
        issued_from: datetime | None = None,
        issued_to: datetime | None = None,
        search: str | None = None,
    ) -> int: ...

    async def customer_names(self, customer_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
        """Display names for the invoices' customers, for list and print
        views — one query instead of a customer lookup per row.
        """

    async def get_by_order_id(self, tenant_id: uuid.UUID, order_id: uuid.UUID) -> Invoice | None:
        """Load an invoice by its associated order ID.

        Args:
            tenant_id: The scoping tenant.
            order_id: The order ID to lookup.

        Returns:
            The Invoice aggregate, or None if no invoice exists for this order.
        """

    async def get_outstanding_balance(self, customer_id: uuid.UUID) -> Decimal:
        """What this customer still owes across `issued` and
        `partially_paid` invoices (total less payments). Returns
        `Decimal("0")` if there are none.
        """


@dataclass(frozen=True, slots=True)
class UninvoicedOrder:
    """A delivered order with no invoice, or an approved cancellation whose
    charge was never billed — almost always because GST was not configured
    when it happened (DA-06, DO-14).
    """

    order_id: uuid.UUID
    order_number: str | None
    customer_id: uuid.UUID
    customer_name: str
    status: str
    occurred_at: datetime
    order_total: Decimal | None
    cancellation_charge: Decimal | None


class UninvoicedOrderReader(Protocol):
    """Read side over Order Management for billing gaps."""

    async def list_uninvoiced(self, *, limit: int = 100) -> list[UninvoicedOrder]: ...

    async def get_uninvoiced(self, order_id: uuid.UUID) -> UninvoicedOrder | None: ...


@dataclass(frozen=True, slots=True)
class CashHandoverRegisterEntry:
    """One row of the accountant's cash-handover register (DA-33)."""

    handover: CashHandover
    driver_name: str
    vehicle_registration: str | None
    route_date: datetime
    cash_stop_count: int
    review: CashHandoverReview | None
    reviewer_name: str | None


@dataclass(frozen=True, slots=True)
class DriverCashInHand:
    """Cash (and UPI) a driver collected on routes that have no handover
    declared yet — what they are carrying.
    """

    driver_id: uuid.UUID
    driver_name: str
    route_count: int
    stop_count: int
    cash_amount: Decimal
    upi_amount: Decimal
    oldest_route_date: datetime


@dataclass(frozen=True, slots=True)
class CashBookCollection:
    method: str
    payment_count: int
    amount: Decimal


@dataclass(frozen=True, slots=True)
class CashBook:
    """One day's money in by mode, and what became of the cash (ADR-066)."""

    collections: list[CashBookCollection]
    handover_count: int
    expected_total: Decimal
    handed_over_total: Decimal
    shortfall_total: Decimal
    excess_total: Decimal
    accepted_total: Decimal
    disputed_total: Decimal
    pending_total: Decimal
    pending_count: int


class CashHandoverRepository(Protocol):
    """Repository for the `CashHandover` aggregate."""

    def next_id(self) -> uuid.UUID: ...

    async def add(self, handover: CashHandover) -> None:
        """Add a new handover. Append-only — there is no `save`/update."""

    async def get_expected_cash_for_route(self, route_id: uuid.UUID) -> Decimal:
        """Sum `amount_collected` across this route's cash-method proof-of-
        delivery records. Returns `Decimal("0")` if there are none.
        """

    async def count_cash_stops_for_route(self, route_id: uuid.UUID) -> int:
        """How many of this route's stops were paid in cash — the count that
        pairs with `get_expected_cash_for_route`, so the driver can sanity-
        check the total against the number of collections.
        """

    async def get_by_route(self, route_id: uuid.UUID) -> CashHandover | None:
        """The declared handover for a route, or `None`. At most one per
        route (BR-32) — the caller relies on that.
        """

    async def get_by_id(self, cash_handover_id: uuid.UUID) -> CashHandover | None: ...

    async def list_register(
        self,
        *,
        declared_from: datetime | None = None,
        declared_to: datetime | None = None,
        driver_id: uuid.UUID | None = None,
        review_status: str | None = None,
        limit: int = 200,
    ) -> list[CashHandoverRegisterEntry]:
        """Newest first. `review_status` is `pending`, `accepted` or
        `disputed`; `declared_to` is exclusive.
        """

    async def add_review(self, review: CashHandoverReview) -> None: ...

    async def get_review(self, cash_handover_id: uuid.UUID) -> CashHandoverReview | None: ...

    async def get_expected_upi_for_route(self, route_id: uuid.UUID) -> Decimal:
        """UPI collected at the doorstep on this route (informational)."""

    async def list_cash_in_hand(
        self, *, driver_id: uuid.UUID | None = None
    ) -> list[DriverCashInHand]:
        """Per driver, cash collected on routes with no handover yet. Drivers
        with nothing in hand are left out. Largest first.
        """

    async def cash_book(self, *, day_from: datetime, day_to: datetime) -> CashBook:
        """Collections and handovers between `day_from` (inclusive) and
        `day_to` (exclusive).
        """

    async def cash_awaiting_handover(self) -> Decimal:
        """Cash drivers collected on routes with no handover declared yet."""


class CreditNoteRepository(Protocol):
    """Repository for the `CreditNote` aggregate."""

    def next_id(self) -> uuid.UUID: ...

    async def add(self, credit_note: CreditNote) -> None:
        """Add a newly-requested credit note."""

    async def save(self, credit_note: CreditNote) -> None:
        """Persist the approval — `approved_by`/`approved_at`. The only
        mutation this aggregate ever undergoes.
        """

    async def get_by_id(self, credit_note_id: uuid.UUID) -> CreditNote | None: ...

    async def list_for_invoice(self, invoice_id: uuid.UUID) -> list[CreditNote]:
        """Oldest first."""


class OnlinePaymentRepository(Protocol):
    """Repository for the `OnlinePayment` aggregate (ADR-053)."""

    def next_id(self) -> uuid.UUID: ...

    async def add(self, payment: OnlinePayment) -> None: ...

    async def save(self, payment: OnlinePayment) -> None:
        """Persist a status change or invoice application."""

    async def get_by_id(self, online_payment_id: uuid.UUID) -> OnlinePayment | None: ...

    async def get_by_provider_link_id(self, provider_link_id: str) -> OnlinePayment | None: ...

    async def list_for_order(self, order_id: uuid.UUID) -> list[OnlinePayment]:
        """Every attempt for one order, newest first."""


class ProofOfDeliveryReader(Protocol):
    """Read side of the order context's proof of delivery, which holds what
    the driver collected at the door (`payment-flow.md` Path B).
    """

    async def get_by_order_id(self, order_id: uuid.UUID) -> ProofOfDeliveryEntry | None: ...
