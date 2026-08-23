"""Accounting repository ports."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import uuid
    from decimal import Decimal

    from lpg.domain.accounting.cash_handover import CashHandover
    from lpg.domain.accounting.credit_note import CreditNote
    from lpg.domain.accounting.invoice import Invoice


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
    ) -> list[Invoice]: ...

    async def count_invoices(
        self,
        customer_id: uuid.UUID | None = None,
        order_id: uuid.UUID | None = None,
        status: str | None = None,
    ) -> int: ...

    async def get_by_order_id(self, tenant_id: uuid.UUID, order_id: uuid.UUID) -> Invoice | None:
        """Load an invoice by its associated order ID.

        Args:
            tenant_id: The scoping tenant.
            order_id: The order ID to lookup.

        Returns:
            The Invoice aggregate, or None if no invoice exists for this order.
        """

    async def get_outstanding_balance(self, customer_id: uuid.UUID) -> Decimal:
        """Sum `total_amount` across this customer's `issued` (unpaid)
        invoices — same definition `rpt.vw_outstanding_balances` uses.
        Returns `Decimal("0")` if there are none.
        """


class CashHandoverRepository(Protocol):
    """Repository for the `CashHandover` aggregate."""

    def next_id(self) -> uuid.UUID: ...

    async def add(self, handover: CashHandover) -> None:
        """Add a new handover. Append-only — there is no `save`/update."""

    async def get_expected_cash_for_route(self, route_id: uuid.UUID) -> Decimal:
        """Sum `amount_collected` across this route's cash-method proof-of-
        delivery records. Returns `Decimal("0")` if there are none.
        """


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
