"""Accounting use cases."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from lpg.application.accounting.gst import (
    GstClass,
    resolve_gst_classes,
    resolve_place_of_supply,
    resolve_prices_include_gst,
)
from lpg.application.common.cqrs import Command, Query
from lpg.application.common.errors import ConflictError, NotFoundError, ValidationError
from lpg.config.logging import get_logger
from lpg.domain.accounting.cash_handover import CashHandover, CashHandoverReview
from lpg.domain.accounting.credit_note import CreditNote
from lpg.domain.accounting.invoice import STAFF_PAYMENT_METHODS, Invoice, InvoiceLine
from lpg.domain.common.gst import compute_line_tax, split_inclusive, to_cents

if TYPE_CHECKING:
    import datetime
    from collections.abc import Sequence

    from lpg.application.accounting.ports import (
        CashHandoverNumberSequence,
        CashHandoverRegisterEntry,
        CashHandoverRepository,
        CreditNoteNumberSequence,
        CreditNoteRepository,
        InvoiceNumberSequence,
        InvoiceRepository,
        OnlinePaymentRepository,
        ProofOfDeliveryReader,
        UninvoicedOrder,
        UninvoicedOrderReader,
    )
    from lpg.application.common.ports import UnitOfWork
    from lpg.application.customer.ports import CustomerRepository
    from lpg.application.delivery.ports import RouteRepository
    from lpg.application.order.ports import OrderRepository, ProofOfDeliveryEntry
    from lpg.application.tenant.ports import (
        CylinderTypeRepository,
        TenantConfigurationRepository,
        TenantRepository,
    )
    from lpg.domain.accounting.online_payment import OnlinePayment
    from lpg.domain.order.order import Order

_logger = get_logger(__name__)


def apply_online_payments_to_invoice(
    invoice: Invoice, online_payments: Sequence[OnlinePayment]
) -> list[OnlinePayment]:
    """Turn each paid, not-yet-applied gateway payment for this invoice's
    order into an `online_gateway` invoice `Payment` (ADR-053). Returns the
    online payments that changed, for the caller to save.

    A prepayment can exceed the invoice when fewer cylinders were delivered
    than ordered; only the outstanding amount is applied and the excess is
    logged for a refund (no automated refund exists yet — see TASKS.md).
    """
    changed: list[OnlinePayment] = []
    for online_payment in online_payments:
        if online_payment.status != "paid" or online_payment.is_applied:
            continue
        outstanding = invoice.total_amount - invoice.amount_paid
        if invoice.status not in ("issued", "partially_paid") or outstanding <= 0:
            _logger.warning(
                "online_payment_not_applied_invoice_settled",
                online_payment_id=str(online_payment.id),
                invoice_id=str(invoice.id),
                amount=str(online_payment.amount),
            )
            continue
        amount = min(online_payment.amount, outstanding)
        if amount < online_payment.amount:
            _logger.warning(
                "online_payment_excess_needs_refund",
                online_payment_id=str(online_payment.id),
                invoice_id=str(invoice.id),
                excess=str(online_payment.amount - amount),
            )
        payment_id = uuid.uuid4()
        invoice.record_payment(
            payment_id=payment_id,
            method="online_gateway",
            amount=amount,
            collected_by=online_payment.created_by,
            collected_at=online_payment.paid_at or online_payment.created_at,
        )
        online_payment.mark_applied(invoice_id=invoice.id, payment_id=payment_id)
        changed.append(online_payment)
    return changed


#: Doorstep payment methods that settle the invoice there and then. `credit`
#: means the customer took the cylinders on account, so nothing was paid.
_DOORSTEP_SETTLEMENT_METHODS: frozenset[str] = frozenset({"cash", "upi", "card", "online_gateway"})


def apply_doorstep_collection_to_invoice(
    invoice: Invoice, proof_of_delivery: ProofOfDeliveryEntry | None
) -> bool:
    """Record what the driver collected at the door as an invoice payment
    (`payment-flow.md` Path B step 4), so a delivery paid in cash or UPI
    leaves a paid invoice and nothing is asked for a second time online.

    Runs after gateway prepayments are applied: only the balance still
    outstanding is recorded, and anything collected beyond it is logged.
    Returns whether a payment was recorded.
    """
    if (
        proof_of_delivery is None
        or proof_of_delivery.payment_method not in _DOORSTEP_SETTLEMENT_METHODS
        or proof_of_delivery.amount_collected <= 0
    ):
        return False
    outstanding = invoice.total_amount - invoice.amount_paid
    if invoice.status not in ("issued", "partially_paid") or outstanding <= 0:
        _logger.warning(
            "doorstep_collection_not_applied_invoice_settled",
            invoice_id=str(invoice.id),
            amount=str(proof_of_delivery.amount_collected),
        )
        return False
    amount = min(proof_of_delivery.amount_collected, outstanding)
    if amount < proof_of_delivery.amount_collected:
        _logger.warning(
            "doorstep_collection_exceeds_invoice",
            invoice_id=str(invoice.id),
            excess=str(proof_of_delivery.amount_collected - amount),
        )
    invoice.record_payment(
        payment_id=uuid.uuid4(),
        method=proof_of_delivery.payment_method,
        amount=amount,
        collected_by=proof_of_delivery.recorded_by,
        collected_at=proof_of_delivery.recorded_at,
    )
    return True


def _taxed_line(
    *,
    cylinder_type_id: uuid.UUID,
    quantity: int,
    unit_price: Decimal,
    gst: GstClass,
    prices_include_gst: bool,
    kind: str = "supply",
    description: str | None = None,
) -> InvoiceLine:
    """One invoice line. `unit_price` is the price-list amount. By default
    (exclusive) GST is added on top of `unit_price * quantity`. When the
    tenant set `prices_include_gst`, the line total is exactly `unit_price *
    quantity` and the taxable value and tax are derived inside it, rounded
    per line so they add back to the paisa.
    """
    if prices_include_gst:
        subtotal, tax_amount = split_inclusive(unit_price * quantity, gst.rate_percent)
    else:
        subtotal = to_cents(unit_price * quantity)
        tax_amount = compute_line_tax(subtotal, gst.rate_percent)
    return InvoiceLine(
        line_id=uuid.uuid4(),
        cylinder_type_id=cylinder_type_id,
        quantity=quantity,
        unit_price=unit_price,
        subtotal=subtotal,
        tax_amount=tax_amount,
        total_amount=subtotal + tax_amount,
        hsn_code=gst.hsn_code,
        gst_rate_percent=gst.rate_percent,
        kind=kind,
        description=description,
    )


class GenerateInvoiceForOrderUseCase:
    """Issues the tax invoice for a delivered order (BR-17) or, for an
    order cancelled after dispatch, for its cancellation charge (DO-14).

    Raises `GstNotConfiguredError` when a cylinder type on the order has no
    GST rate (DA-06) — nothing is written, and the order shows up in
    `ListUninvoicedOrdersUseCase` until someone configures the rate and
    issues it.
    """

    def __init__(
        self,
        invoice_repository: InvoiceRepository,
        order_repository: OrderRepository,
        customer_repository: CustomerRepository,
        tenant_config_repository: TenantConfigurationRepository,
        invoice_number_sequence: InvoiceNumberSequence,
        cylinder_type_repository: CylinderTypeRepository,
        tenant_repository: TenantRepository,
        online_payment_repository: OnlinePaymentRepository | None = None,
        proof_of_delivery_reader: ProofOfDeliveryReader | None = None,
    ) -> None:
        self._invoice_repository = invoice_repository
        self._order_repository = order_repository
        self._customer_repository = customer_repository
        self._tenant_config_repository = tenant_config_repository
        self._invoice_number_sequence = invoice_number_sequence
        self._cylinder_type_repository = cylinder_type_repository
        self._tenant_repository = tenant_repository
        # Optional so callers that never take online payments (and the
        # existing unit tests) need not wire it; the production event
        # handler always does, so gateway prepayments land on the invoice.
        self._online_payment_repository = online_payment_repository
        # Optional for the same reason; when wired, the driver's doorstep
        # collection is recorded on the new invoice.
        self._proof_of_delivery_reader = proof_of_delivery_reader

    async def execute(
        self,
        tenant_id: uuid.UUID,
        order_id: uuid.UUID,
        delivered_at: datetime.datetime,
    ) -> Invoice | None:
        """Invoice a delivered order. Returns the new invoice, or `None`
        when there is nothing to invoice (already invoiced, unknown order,
        nothing delivered).
        """
        existing_invoice = await self._invoice_repository.get_by_order_id(tenant_id, order_id)
        if existing_invoice is not None:
            _logger.info("invoice_already_exists", order_id=str(order_id))
            return None

        order = await self._order_repository.get_by_id(order_id)
        if order is None:
            _logger.error("order_not_found_for_invoice", order_id=str(order_id))
            return None

        delivered = [line for line in order.lines if line.quantity_delivered > 0]
        if not delivered:
            _logger.info("order_had_no_delivered_lines", order_id=str(order_id))
            return None

        gst_classes = await resolve_gst_classes(
            cylinder_type_repository=self._cylinder_type_repository,
            tenant_config_repository=self._tenant_config_repository,
            tenant_id=tenant_id,
            cylinder_type_ids=[line.cylinder_type_id for line in delivered],
            at=delivered_at,
        )
        inclusive = await resolve_prices_include_gst(
            self._tenant_config_repository, tenant_id, delivered_at
        )
        lines = [
            _taxed_line(
                cylinder_type_id=line.cylinder_type_id,
                quantity=line.quantity_delivered,
                unit_price=line.unit_price or Decimal("0.00"),
                gst=gst_classes[line.cylinder_type_id],
                prices_include_gst=inclusive,
            )
            for line in delivered
        ]

        invoice = await self._issue(tenant_id, order, lines, delivered_at)
        if self._online_payment_repository is not None:
            prepayments = await self._online_payment_repository.list_for_order(order.id)
            for online_payment in apply_online_payments_to_invoice(invoice, prepayments):
                await self._online_payment_repository.save(online_payment)
        if self._proof_of_delivery_reader is not None:
            apply_doorstep_collection_to_invoice(
                invoice, await self._proof_of_delivery_reader.get_by_order_id(order.id)
            )
        await self._invoice_repository.add(invoice)
        _logger.info("invoice_generated", invoice_id=str(invoice.id), order_id=str(order_id))
        return invoice

    async def execute_cancellation_charge(
        self,
        tenant_id: uuid.UUID,
        order_id: uuid.UUID,
        charge: Decimal,
        cancelled_at: datetime.datetime,
    ) -> Invoice | None:
        """Bill the fee for a cancellation a manager approved (D-19, DO-14).

        Contract with Order Management: `BookingCancelled.cancellation_charge`
        the amount configured in `cancellation_fee_amount`, read on the
        same basis as the price list: before GST, with GST added on top
        (the default), or GST-inclusive when the tenant set
        `prices_include_gst` to true. Under GST a cancellation charge is
        consideration for the supply it relates to, so it is taxed at that
        supply's rate and HSN; with lines at different rates the highest
        applies.
        """
        if charge <= 0:
            return None
        if await self._invoice_repository.get_by_order_id(tenant_id, order_id) is not None:
            _logger.info("invoice_already_exists", order_id=str(order_id))
            return None
        order = await self._order_repository.get_by_id(order_id)
        if order is None or not order.lines:
            _logger.error("order_not_found_for_invoice", order_id=str(order_id))
            return None

        gst_classes = await resolve_gst_classes(
            cylinder_type_repository=self._cylinder_type_repository,
            tenant_config_repository=self._tenant_config_repository,
            tenant_id=tenant_id,
            cylinder_type_ids=[line.cylinder_type_id for line in order.lines],
            at=cancelled_at,
        )
        principal_line = max(
            order.lines, key=lambda line: gst_classes[line.cylinder_type_id].rate_percent
        )
        line = _taxed_line(
            cylinder_type_id=principal_line.cylinder_type_id,
            quantity=1,
            unit_price=to_cents(charge),
            gst=gst_classes[principal_line.cylinder_type_id],
            prices_include_gst=await resolve_prices_include_gst(
                self._tenant_config_repository, tenant_id, cancelled_at
            ),
            kind="cancellation_charge",
            description="Cancellation charge",
        )
        invoice = await self._issue(tenant_id, order, [line], cancelled_at)
        await self._invoice_repository.add(invoice)
        _logger.info(
            "cancellation_charge_invoiced", invoice_id=str(invoice.id), order_id=str(order_id)
        )
        return invoice

    async def _issue(
        self,
        tenant_id: uuid.UUID,
        order: Order,
        lines: list[InvoiceLine],
        issued_at: datetime.datetime,
    ) -> Invoice:
        customer = await self._customer_repository.get_by_id(order.customer_id)
        supply = await resolve_place_of_supply(
            tenant_repository=self._tenant_repository, tenant_id=tenant_id, customer=customer
        )
        return Invoice.generate_for_delivered_order(
            invoice_id=uuid.uuid4(),
            tenant_id=tenant_id,
            invoice_number=await self._invoice_number_sequence.next(),
            customer_id=order.customer_id,
            order_id=order.id,
            delivered_at=issued_at,
            lines=lines,
            order_number=order.order_number,
            customer_consumer_number=customer.consumer_number if customer else None,
            supply=supply,
        )


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
    issued_from: datetime.datetime | None = None
    issued_to: datetime.datetime | None = None
    search: str | None = None


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
            issued_from=query.issued_from,
            issued_to=query.issued_to,
            search=query.search,
        )
        total = await self._repository.count_invoices(
            customer_id=query.customer_id,
            order_id=query.order_id,
            status=query.status,
            issued_from=query.issued_from,
            issued_to=query.issued_to,
            search=query.search,
        )
        return items, total


@dataclass(frozen=True, slots=True)
class RecordPaymentCommand(Command):
    invoice_id: uuid.UUID
    method: str
    amount: Decimal
    collected_by: uuid.UUID
    collected_at: datetime.datetime
    reference: str | None = None


#: Office-recorded methods that must carry a reference the accountant can
#: match against the bank statement.
_REFERENCE_REQUIRED_METHODS: frozenset[str] = frozenset({"cheque", "bank_transfer"})


class RecordPaymentUseCase:
    """BR-18, D-11."""

    def __init__(self, repository: InvoiceRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: RecordPaymentCommand) -> Invoice:
        if command.method not in STAFF_PAYMENT_METHODS:
            msg = "Choose cash, UPI, card, cheque or bank transfer."
            raise ValidationError(msg, errors={"method": [msg]})
        if command.method in _REFERENCE_REQUIRED_METHODS and not (command.reference or "").strip():
            msg = "Enter the cheque number or bank reference (UTR)."
            raise ValidationError(msg, errors={"reference": [msg]})

        invoice = await self._repository.get_by_id(command.invoice_id)
        if invoice is None:
            msg = f"No invoice visible with id {command.invoice_id}."
            raise NotFoundError(msg, invoice_id=str(command.invoice_id))
        if command.amount > invoice.balance_due:
            msg = (
                f"Amount is more than the balance due of {invoice.balance_due}."
                if invoice.balance_due > 0
                else "Nothing is due on this invoice."
            )
            raise ValidationError(msg, errors={"amount": [msg]})

        invoice.record_payment(
            payment_id=uuid.uuid4(),
            method=command.method,
            amount=command.amount,
            collected_by=command.collected_by,
            collected_at=command.collected_at,
            reference=command.reference,
        )

        await self._repository.save(invoice)
        await self._unit_of_work.commit()
        return invoice


@dataclass(frozen=True, slots=True)
class SendInvoiceToCustomerCommand(Command):
    invoice_id: uuid.UUID
    sent_by: uuid.UUID


class SendInvoiceToCustomerUseCase:
    """Staff send an issued invoice to the customer (e-mail and push)."""

    def __init__(self, repository: InvoiceRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: SendInvoiceToCustomerCommand) -> Invoice:
        invoice = await self._repository.get_by_id(command.invoice_id)
        if invoice is None:
            msg = f"No invoice visible with id {command.invoice_id}."
            raise NotFoundError(msg, invoice_id=str(command.invoice_id))
        invoice.send_to_customer(sent_by=command.sent_by)
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
        if route is None or (query.driver_id is not None and route.driver_id != query.driver_id):
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


@dataclass(frozen=True, slots=True)
class ListCreditNotesQuery(Query):
    invoice_id: uuid.UUID


class ListCreditNotesUseCase:
    """Refund requests and approvals raised against one invoice."""

    def __init__(self, credit_note_repository: CreditNoteRepository) -> None:
        self._credit_note_repository = credit_note_repository

    async def execute(self, query: ListCreditNotesQuery) -> list[CreditNote]:
        return await self._credit_note_repository.list_for_invoice(query.invoice_id)


# ---------------------------------------------------------------------------
# Billing gaps — orders that should have an invoice but don't (DA-06, DO-14)
# ---------------------------------------------------------------------------


class ListUninvoicedOrdersUseCase:
    def __init__(self, reader: UninvoicedOrderReader) -> None:
        self._reader = reader

    async def execute(self) -> list[UninvoicedOrder]:
        return await self._reader.list_uninvoiced()


@dataclass(frozen=True, slots=True)
class IssueInvoiceForOrderCommand(Command):
    tenant_id: uuid.UUID
    order_id: uuid.UUID
    issued_at: datetime.datetime


class IssueInvoiceForOrderUseCase:
    """Issue the invoice that was held back — typically because GST was not
    configured when the order was delivered or its cancellation approved.
    Re-raises `GstNotConfiguredError` if it still is.
    """

    def __init__(
        self,
        reader: UninvoicedOrderReader,
        generator: GenerateInvoiceForOrderUseCase,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._reader = reader
        self._generator = generator
        self._unit_of_work = unit_of_work

    async def execute(self, command: IssueInvoiceForOrderCommand) -> Invoice:
        pending = await self._reader.get_uninvoiced(command.order_id)
        if pending is None:
            msg = "This order has nothing left to invoice."
            raise NotFoundError(msg, order_id=str(command.order_id))

        if pending.status == "cancelled":
            invoice = await self._generator.execute_cancellation_charge(
                command.tenant_id,
                command.order_id,
                pending.cancellation_charge or Decimal("0"),
                command.issued_at,
            )
        else:
            invoice = await self._generator.execute(
                command.tenant_id, command.order_id, command.issued_at
            )
        if invoice is None:
            msg = "This order has nothing left to invoice."
            raise ConflictError(msg, order_id=str(command.order_id))
        await self._unit_of_work.commit()
        return invoice


# ---------------------------------------------------------------------------
# Cash handover register (DA-33)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ListCashHandoverRegisterQuery(Query):
    declared_from: datetime.datetime | None = None
    declared_to: datetime.datetime | None = None
    driver_id: uuid.UUID | None = None
    review_status: str | None = None


class ListCashHandoverRegisterUseCase:
    def __init__(self, repository: CashHandoverRepository) -> None:
        self._repository = repository

    async def execute(
        self, query: ListCashHandoverRegisterQuery
    ) -> list[CashHandoverRegisterEntry]:
        if query.review_status not in (None, "pending", "accepted", "disputed"):
            msg = "Status must be pending, accepted or disputed."
            raise ValidationError(msg, errors={"review_status": [msg]})
        return await self._repository.list_register(
            declared_from=query.declared_from,
            declared_to=query.declared_to,
            driver_id=query.driver_id,
            review_status=query.review_status,
        )


@dataclass(frozen=True, slots=True)
class ReviewCashHandoverCommand(Command):
    cash_handover_id: uuid.UUID
    outcome: str
    note: str | None
    reviewed_by: uuid.UUID


class ReviewCashHandoverUseCase:
    """The office counts the driver's cash and accepts or disputes the
    declaration. One review per handover.
    """

    def __init__(self, repository: CashHandoverRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: ReviewCashHandoverCommand) -> CashHandoverReview:
        handover = await self._repository.get_by_id(command.cash_handover_id)
        if handover is None:
            msg = f"No cash handover visible with id {command.cash_handover_id}."
            raise NotFoundError(msg, cash_handover_id=str(command.cash_handover_id))
        if await self._repository.get_review(handover.id) is not None:
            msg = "This handover has already been reviewed."
            raise ConflictError(msg, cash_handover_id=str(handover.id))

        review = CashHandoverReview.record(
            review_id=uuid.uuid4(),
            handover=handover,
            outcome=command.outcome,
            note=command.note,
            reviewed_by=command.reviewed_by,
        )
        await self._repository.add_review(review)
        await self._unit_of_work.commit()
        _logger.info(
            "cash_handover_reviewed",
            cash_handover_id=str(handover.id),
            outcome=review.outcome,
            shortfall=str(handover.shortfall),
        )
        return review
