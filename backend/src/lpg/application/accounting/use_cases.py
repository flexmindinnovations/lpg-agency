"""Accounting use cases."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Query
from lpg.config.logging import get_logger
from lpg.domain.accounting.invoice import Invoice, InvoiceLine
from lpg.domain.tenant.tenant_configuration import TenantConfigurationResolver

if TYPE_CHECKING:
    import datetime

    from lpg.application.accounting.ports import InvoiceRepository
    from lpg.application.order.ports import OrderRepository
    from lpg.application.tenant.ports import TenantConfigurationRepository

_logger = get_logger(__name__)


class GenerateInvoiceForOrderUseCase:
    """Generates an invoice for an order when it is delivered."""

    def __init__(
        self,
        invoice_repository: InvoiceRepository,
        order_repository: OrderRepository,
        tenant_config_repository: TenantConfigurationRepository,
    ) -> None:
        self._invoice_repository = invoice_repository
        self._order_repository = order_repository
        self._tenant_config_repository = tenant_config_repository

    async def execute(
        self,
        tenant_id: uuid.UUID,
        order_id: uuid.UUID,
        delivered_at: datetime.datetime,
    ) -> None:
        """Execute the use case.

        Args:
            tenant_id: The scoping tenant.
            order_id: The order that was delivered.
            delivered_at: The time the order was delivered.
        """
        existing_invoice = await self._invoice_repository.get_by_order_id(tenant_id, order_id)
        if existing_invoice is not None:
            _logger.info("invoice_already_exists", order_id=str(order_id))
            return

        order = await self._order_repository.get_by_id(order_id)
        if order is None:
            _logger.error("order_not_found_for_invoice", order_id=str(order_id))
            return

        configs = await self._tenant_config_repository.list_for_tenant_and_key(
            tenant_id, "gst_rate_percent"
        )
        gst_config = TenantConfigurationResolver.resolve(configs, "gst_rate_percent", delivered_at)

        gst_rate = gst_config.config_value if gst_config else None

        try:
            gst_rate_decimal = Decimal(gst_rate) if gst_rate else Decimal("0.0")
        except (ValueError, TypeError):
            _logger.warning("invalid_gst_rate", gst_rate=gst_rate)
            gst_rate_decimal = Decimal("0.0")

        # Generate invoice lines from order lines
        lines = []
        for line in order.lines:
            if line.quantity_delivered <= 0:
                continue

            unit_price = line.unit_price or Decimal("0.0")
            subtotal = unit_price * line.quantity_delivered
            tax_amount = (subtotal * gst_rate_decimal) / Decimal("100")
            total_amount = subtotal + tax_amount
            lines.append(
                InvoiceLine(
                    line_id=uuid.uuid4(),
                    cylinder_type_id=line.cylinder_type_id,
                    quantity=line.quantity_delivered,
                    unit_price=unit_price,
                    subtotal=subtotal,
                    tax_amount=tax_amount,
                    total_amount=total_amount,
                )
            )

        if not lines:
            _logger.info("order_had_no_delivered_lines", order_id=str(order_id))
            return

        invoice_id = uuid.uuid4()
        invoice = Invoice.generate_for_delivered_order(
            invoice_id=invoice_id,
            tenant_id=tenant_id,
            customer_id=order.customer_id,
            order_id=order.id,
            delivered_at=delivered_at,
            lines=lines,
        )
        await self._invoice_repository.add(invoice)
        _logger.info("invoice_generated", invoice_id=str(invoice.id), order_id=str(order_id))


@dataclass(frozen=True, slots=True)
class GetInvoiceQuery(Query):
    invoice_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class ListInvoicesQuery(Query):
    skip: int = 0
    limit: int = 50
    customer_id: uuid.UUID | None = None
    order_id: uuid.UUID | None = None
    status: str | None = None


class GetInvoiceUseCase:
    """Gets a specific invoice."""

    def __init__(self, repository: InvoiceRepository) -> None:
        self._repository = repository

    async def execute(self, query: GetInvoiceQuery) -> Invoice | None:
        return await self._repository.get_by_id(query.invoice_id)


class ListInvoicesUseCase:
    """Lists invoices with optional filters."""

    def __init__(self, repository: InvoiceRepository) -> None:
        self._repository = repository

    async def execute(self, query: ListInvoicesQuery) -> tuple[list[Invoice], int]:
        items = await self._repository.list_invoices(
            skip=query.skip,
            limit=query.limit,
            customer_id=query.customer_id,
            order_id=query.order_id,
            status=query.status,
        )
        total = await self._repository.count_invoices(
            customer_id=query.customer_id,
            order_id=query.order_id,
            status=query.status,
        )
        return items, total
