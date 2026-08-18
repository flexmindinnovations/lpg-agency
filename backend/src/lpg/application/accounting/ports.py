"""Accounting repository ports."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import uuid

    from lpg.domain.accounting.invoice import Invoice


class InvoiceRepository(Protocol):
    """Repository for the `Invoice` aggregate."""

    async def add(self, invoice: Invoice) -> None:
        """Add a new invoice.

        Args:
            invoice: The aggregate to save.
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
