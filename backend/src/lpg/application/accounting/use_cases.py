"""Accounting use cases."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command, Query
from lpg.application.common.errors import ConflictError, NotFoundError, ValidationError
from lpg.config.logging import get_logger
from lpg.domain.accounting.cash_handover import CashHandover
from lpg.domain.accounting.credit_note import CreditNote
from lpg.domain.accounting.invoice import Invoice, InvoiceLine
from lpg.domain.tenant.tenant_configuration import TenantConfigurationResolver

if TYPE_CHECKING:
    import datetime

    from lpg.application.accounting.ports import (
        CashHandoverNumberSequence,
        CashHandoverRepository,
        CreditNoteNumberSequence,
        CreditNoteRepository,
        InvoiceNumberSequence,
        InvoiceRepository,
    )
    from lpg.application.common.ports import UnitOfWork
    from lpg.application.customer.ports import CustomerRepository
    from lpg.application.delivery.ports import RouteRepository
    from lpg.application.order.ports import OrderRepository
    from lpg.application.tenant.ports import TenantConfigurationRepository

_logger = get_logger(__name__)


class GenerateInvoiceForOrderUseCase:
    """Generates an invoice for an order when it is delivered."""

    def __init__(
        self,
        invoice_repository: InvoiceRepository,
        order_repository: OrderRepository,
        customer_repository: CustomerRepository,
        tenant_config_repository: TenantConfigurationRepository,
        invoice_number_sequence: InvoiceNumberSequence,
    ) -> None:
        self._invoice_repository = invoice_repository
        self._order_repository = order_repository
        self._customer_repository = customer_repository
        self._tenant_config_repository = tenant_config_repository
        self._invoice_number_sequence = invoice_number_sequence

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

        customer = await self._customer_repository.get_by_id(order.customer_id)

        invoice_id = uuid.uuid4()
        invoice_number = await self._invoice_number_sequence.next()
        invoice = Invoice.generate_for_delivered_order(
            invoice_id=invoice_id,
            tenant_id=tenant_id,
            invoice_number=invoice_number,
            customer_id=order.customer_id,
            order_id=order.id,
            delivered_at=delivered_at,
            lines=lines,
            order_number=order.order_number,
            customer_consumer_number=customer.consumer_number if customer else None,
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


@dataclass(frozen=True, slots=True)
class RecordPaymentCommand(Command):
    invoice_id: uuid.UUID
    method: str
    amount: Decimal
    collected_by: uuid.UUID
    collected_at: datetime.datetime


class RecordPaymentUseCase:
    """BR-18, D-11."""

    def __init__(self, repository: InvoiceRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: RecordPaymentCommand) -> Invoice:
        invoice = await self._repository.get_by_id(command.invoice_id)
        if invoice is None:
            msg = f"No invoice visible with id {command.invoice_id}."
            raise NotFoundError(msg, invoice_id=str(command.invoice_id))

        invoice.record_payment(
            payment_id=uuid.uuid4(),
            method=command.method,
            amount=command.amount,
            collected_by=command.collected_by,
            collected_at=command.collected_at,
        )

        await self._repository.save(invoice)
        await self._unit_of_work.commit()
        return invoice


@dataclass(frozen=True, slots=True)
class DeclareCashHandoverCommand(Command):
    driver_id: uuid.UUID
    route_id: uuid.UUID
    actual_amount: Decimal
    declared_by: uuid.UUID


class DeclareCashHandoverUseCase:
    """BR-32. `expected_amount` is computed from real
    `orders.proof_of_delivery` data, not entered by hand."""

    def __init__(
        self,
        cash_handover_repository: CashHandoverRepository,
        route_repository: RouteRepository,
        unit_of_work: UnitOfWork,
        handover_number_sequence: CashHandoverNumberSequence,
    ) -> None:
        self._cash_handover_repository = cash_handover_repository
        self._route_repository = route_repository
        self._unit_of_work = unit_of_work
        self._handover_number_sequence = handover_number_sequence

    async def execute(self, command: DeclareCashHandoverCommand) -> CashHandover:
        route = await self._route_repository.get_by_id(command.route_id)
        # Same "don't distinguish not-found from not-yours" reasoning
        # `NotFoundError`'s own docstring gives for cross-tenant records —
        # extended here to cross-driver ones.
        if route is None or route.driver_id != command.driver_id:
            msg = f"No route visible with id {command.route_id} for this driver."
            raise NotFoundError(msg, route_id=str(command.route_id))

        # One handover per route — the `cash_handover` table has no `save`,
        # and `uq_cash_handover_route` enforces this at the DB. Check here so
        # a retry gets a clean 409 rather than a raw IntegrityError.
        existing = await self._cash_handover_repository.get_by_route(command.route_id)
        if existing is not None:
            msg = "Cash has already been handed over for this route."
            raise ConflictError(msg, route_id=str(command.route_id))

        # BR-32: the handover reconciles a *completed* route. `expected_amount`
        # is only meaningful once every stop has a final proof-of-delivery.
        if route.status != "completed":
            msg = "Cash can only be handed over once the route is completed."
            raise ValidationError(msg, route_id=str(command.route_id))

        expected_amount = await self._cash_handover_repository.get_expected_cash_for_route(
            command.route_id
        )

        handover_number = await self._handover_number_sequence.next()
        handover = CashHandover.declare(
            cash_handover_id=self._cash_handover_repository.next_id(),
            tenant_id=route.tenant_id,
            driver_id=command.driver_id,
            route_id=command.route_id,
            expected_amount=expected_amount,
            actual_amount=command.actual_amount,
            declared_by=command.declared_by,
            handover_number=handover_number,
        )

        await self._cash_handover_repository.add(handover)
        await self._unit_of_work.commit()
        return handover


@dataclass(frozen=True, slots=True)
class GetRouteCashHandoverViewQuery(Query):
    route_id: uuid.UUID
    # `None` for dispatch staff — they can read any route in their tenant
    # (RLS still applies); a driver id scopes the lookup to that driver.
    driver_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class RouteCashHandoverView:
    """Everything the Driver App's cash-handover screen needs in one read:
    what's expected, and the handover if it's already been declared.
    """

    route_id: uuid.UUID
    driver_id: uuid.UUID
    route_status: str
    route_date: datetime.datetime
    expected_amount: Decimal
    cash_stop_count: int
    handover: CashHandover | None


class GetRouteCashHandoverViewUseCase:
    """Read model behind `GET /cash-handovers/for-route/{route_id}`. Same
    driver-scoping as `DeclareCashHandoverUseCase` — a route that isn't this
    driver's is indistinguishable from one that doesn't exist.
    """

    def __init__(
        self,
        cash_handover_repository: CashHandoverRepository,
        route_repository: RouteRepository,
    ) -> None:
        self._cash_handover_repository = cash_handover_repository
        self._route_repository = route_repository

    async def execute(self, query: GetRouteCashHandoverViewQuery) -> RouteCashHandoverView:
        route = await self._route_repository.get_by_id(query.route_id)
        if route is None or (
            query.driver_id is not None and route.driver_id != query.driver_id
        ):
            msg = f"No route visible with id {query.route_id}."
            raise NotFoundError(msg, route_id=str(query.route_id))

        return RouteCashHandoverView(
            route_id=query.route_id,
            driver_id=route.driver_id,
            route_status=route.status,
            route_date=route.date,
            expected_amount=await self._cash_handover_repository.get_expected_cash_for_route(
                query.route_id
            ),
            cash_stop_count=await self._cash_handover_repository.count_cash_stops_for_route(
                query.route_id
            ),
            handover=await self._cash_handover_repository.get_by_route(query.route_id),
        )


@dataclass(frozen=True, slots=True)
class RequestRefundCommand(Command):
    invoice_id: uuid.UUID
    amount: Decimal
    reason: str
    requested_by: uuid.UUID


class RequestRefundUseCase:
    """BR-20. `amount` must not exceed the invoice's actual `amount_paid`
    — validated here, since `CreditNote` has no visibility into `Invoice`.
    """

    def __init__(
        self,
        credit_note_repository: CreditNoteRepository,
        invoice_repository: InvoiceRepository,
        unit_of_work: UnitOfWork,
        credit_note_number_sequence: CreditNoteNumberSequence,
    ) -> None:
        self._credit_note_repository = credit_note_repository
        self._invoice_repository = invoice_repository
        self._unit_of_work = unit_of_work
        self._credit_note_number_sequence = credit_note_number_sequence

    async def execute(self, command: RequestRefundCommand) -> CreditNote:
        invoice = await self._invoice_repository.get_by_id(command.invoice_id)
        if invoice is None:
            msg = f"No invoice visible with id {command.invoice_id}."
            raise NotFoundError(msg, invoice_id=str(command.invoice_id))

        if command.amount > invoice.amount_paid:
            msg = (
                f"Refund amount {command.amount} exceeds this invoice's "
                f"amount paid ({invoice.amount_paid})."
            )
            raise ValidationError(msg, invoice_id=str(command.invoice_id))

        credit_note_number = await self._credit_note_number_sequence.next()
        credit_note = CreditNote.request(
            credit_note_id=self._credit_note_repository.next_id(),
            tenant_id=invoice.tenant_id,
            invoice_id=invoice.id,
            amount=command.amount,
            reason=command.reason,
            requested_by=command.requested_by,
            credit_note_number=credit_note_number,
        )

        await self._credit_note_repository.add(credit_note)
        await self._unit_of_work.commit()
        return credit_note


@dataclass(frozen=True, slots=True)
class ApproveRefundCommand(Command):
    invoice_id: uuid.UUID
    credit_note_id: uuid.UUID
    approved_by: uuid.UUID


class ApproveRefundUseCase:
    """BR-20."""

    def __init__(
        self, credit_note_repository: CreditNoteRepository, unit_of_work: UnitOfWork
    ) -> None:
        self._credit_note_repository = credit_note_repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: ApproveRefundCommand) -> CreditNote:
        credit_note = await self._credit_note_repository.get_by_id(command.credit_note_id)
        # Same "don't distinguish not-found from not-yours" reasoning
        # `NotFoundError`'s own docstring gives for cross-tenant records —
        # extended here to the nested-resource URL's `invoice_id` not
        # actually owning this credit note.
        if credit_note is None or credit_note.invoice_id != command.invoice_id:
            msg = f"No credit note visible with id {command.credit_note_id} on this invoice."
            raise NotFoundError(msg, credit_note_id=str(command.credit_note_id))

        credit_note.approve(command.approved_by)

        await self._credit_note_repository.save(credit_note)
        await self._unit_of_work.commit()
        return credit_note
