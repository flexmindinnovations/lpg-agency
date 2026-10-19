"""Online payment use cases (ADR-053).

`CreateOrderPaymentLinkUseCase` is the one entry point every channel shares
— the Customer App, staff on the dashboard, and the WhatsApp assistant —
so the amount rule lives in exactly one place:

- the order already has an invoice -> the invoice's outstanding balance;
- otherwise (a prepayment, `payment-flow.md` Path A) -> the confirmed
  order's total plus GST at the tenant's current rate, computed exactly the
  way `GenerateInvoiceForOrderUseCase` will compute the invoice, minus
  anything already paid online for the order.

The gateway's confirmation reaches us by webhook (`HandlePaymentWebhookUseCase`)
or, when no webhook URL is reachable (local dev) or one was missed, by an
explicit `RefreshOnlinePaymentUseCase` that asks the gateway directly. Both
funnel through `_apply_gateway_status`, so they cannot disagree.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

from lpg.application.accounting.payment_gateway import (
    PaymentGatewayError,
    PaymentLinkRequest,
    PaymentLinkStatus,
)
from lpg.application.accounting.use_cases import (
    apply_online_payments_to_invoice,
    resolve_gst_rate_percent,
)
from lpg.application.common.cqrs import Command, Query
from lpg.application.common.errors import (
    ConflictError,
    NotFoundError,
    ServiceUnavailableError,
)
from lpg.config.logging import get_logger
from lpg.domain.accounting.online_payment import OnlinePayment

if TYPE_CHECKING:
    import uuid

    from lpg.application.accounting.payment_gateway import PaymentGateway
    from lpg.application.accounting.ports import InvoiceRepository, OnlinePaymentRepository
    from lpg.application.common.ports import UnitOfWork
    from lpg.application.customer.ports import CustomerRepository
    from lpg.application.order.ports import OrderRepository
    from lpg.application.tenant.ports import TenantConfigurationRepository
    from lpg.domain.order.order import Order

_logger = get_logger(__name__)

_CENT = Decimal("0.01")

#: Before delivery, an order can be prepaid once its price is fixed
#: (`confirm()` snapshots unit prices) and while it is still on its way.
_PREPAYABLE_STATUSES: frozenset[str] = frozenset(
    {"confirmed", "assigned", "ready_for_dispatch", "out_for_delivery", "failed_delivery"}
)


@dataclass(frozen=True, slots=True)
class OrderPaymentScope:
    """Row scoping for the caller, same rule as the order endpoints: a
    scoped caller asking about an order outside its scope gets 404, never
    403 (OWASP API1).
    """

    customer_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None

    def allows(self, order: Order) -> bool:
        if self.customer_id is not None and order.customer_id != self.customer_id:
            return False
        return not (self.branch_id is not None and order.branch_id != self.branch_id)


@dataclass(frozen=True, slots=True)
class CreateOrderPaymentLinkCommand(Command):
    tenant_id: uuid.UUID
    order_id: uuid.UUID
    requested_by: uuid.UUID
    scope: OrderPaymentScope = OrderPaymentScope()


@dataclass(frozen=True, slots=True)
class ListOrderOnlinePaymentsQuery(Query):
    order_id: uuid.UUID
    scope: OrderPaymentScope = OrderPaymentScope()


@dataclass(frozen=True, slots=True)
class RefreshOnlinePaymentCommand(Command):
    tenant_id: uuid.UUID
    online_payment_id: uuid.UUID
    scope: OrderPaymentScope = OrderPaymentScope()


async def _get_scoped_order(
    order_repository: OrderRepository, order_id: uuid.UUID, scope: OrderPaymentScope
) -> Order:
    order = await order_repository.get_by_id(order_id)
    if order is None or not scope.allows(order):
        msg = f"No order visible with id {order_id}."
        raise NotFoundError(msg, order_id=str(order_id))
    return order


def _prepayment_total(order: Order, gst_rate_percent: Decimal) -> Decimal:
    """Mirror of `GenerateInvoiceForOrderUseCase`'s line arithmetic, on the
    ordered (not yet delivered) quantities.
    """
    total = Decimal("0")
    for line in order.lines:
        subtotal = (line.unit_price or Decimal("0")) * line.quantity_ordered
        total += subtotal + (subtotal * gst_rate_percent) / Decimal("100")
    return total.quantize(_CENT, rounding=ROUND_HALF_UP)


async def _apply_gateway_status(
    *,
    online_payment: OnlinePayment,
    status: PaymentLinkStatus,
    invoice_repository: InvoiceRepository,
    online_payment_repository: OnlinePaymentRepository,
) -> None:
    """Bring `online_payment` in line with the gateway, then — if it is paid
    and the order already has an invoice — apply it there. Idempotent:
    re-delivering the same status changes nothing.
    """
    if status.status == "paid":
        online_payment.mark_paid(
            provider_payment_id=status.provider_payment_id or "",
            payment_method=status.payment_method,
            paid_at=status.paid_at or datetime.now(UTC),
        )
    elif status.status in ("expired", "cancelled"):
        online_payment.mark_closed(status.status)

    if online_payment.status == "paid" and not online_payment.is_applied:
        invoice = await invoice_repository.get_by_order_id(
            online_payment.tenant_id, online_payment.order_id
        )
        if invoice is not None and apply_online_payments_to_invoice(invoice, [online_payment]):
            await invoice_repository.save(invoice)

    await online_payment_repository.save(online_payment)


class CreateOrderPaymentLinkUseCase:
    """Create (or reuse) a hosted payment link for whatever is still owed
    on an order.
    """

    def __init__(
        self,
        *,
        order_repository: OrderRepository,
        invoice_repository: InvoiceRepository,
        online_payment_repository: OnlinePaymentRepository,
        customer_repository: CustomerRepository,
        tenant_config_repository: TenantConfigurationRepository,
        gateway: PaymentGateway,
        unit_of_work: UnitOfWork,
        link_ttl: timedelta,
        currency: str = "INR",
    ) -> None:
        self._order_repository = order_repository
        self._invoice_repository = invoice_repository
        self._online_payment_repository = online_payment_repository
        self._customer_repository = customer_repository
        self._tenant_config_repository = tenant_config_repository
        self._gateway = gateway
        self._unit_of_work = unit_of_work
        self._link_ttl = link_ttl
        self._currency = currency

    async def execute(self, command: CreateOrderPaymentLinkCommand) -> OnlinePayment:
        if not self._gateway.is_configured:
            msg = "Online payments are not configured for this environment."
            raise ServiceUnavailableError(msg)

        order = await _get_scoped_order(self._order_repository, command.order_id, command.scope)
        now = datetime.now(UTC)
        existing = await self._online_payment_repository.list_for_order(order.id)
        invoice_id, amount = await self._amount_due(command.tenant_id, order, existing, now)

        for candidate in existing:
            if candidate.is_reusable(amount=amount, now=now):
                return candidate

        customer = await self._customer_repository.get_by_id(order.customer_id)
        online_payment_id = self._online_payment_repository.next_id()
        expires_at = now + self._link_ttl
        label = order.order_number or str(order.id)
        try:
            link = await self._gateway.create_payment_link(
                PaymentLinkRequest(
                    amount=amount,
                    currency=self._currency,
                    reference_id=str(online_payment_id),
                    description=f"LPG order {label}",
                    notes={
                        "tenant_id": str(command.tenant_id),
                        "online_payment_id": str(online_payment_id),
                        "order_id": str(order.id),
                    },
                    customer_name=customer.full_name if customer else None,
                    customer_phone=customer.phone_number if customer else None,
                    customer_email=customer.email if customer else None,
                    expires_at=expires_at,
                )
            )
        except PaymentGatewayError as exc:
            _logger.warning("payment_link_create_failed", order_id=str(order.id), error=str(exc))
            msg = "The payment gateway could not create a payment link. Please try again."
            raise ServiceUnavailableError(msg) from exc

        online_payment = OnlinePayment.create(
            online_payment_id=online_payment_id,
            tenant_id=command.tenant_id,
            order_id=order.id,
            customer_id=order.customer_id,
            invoice_id=invoice_id,
            amount=amount,
            currency=self._currency,
            provider=self._gateway.provider,
            provider_link_id=link.link_id,
            short_url=link.short_url,
            created_by=command.requested_by,
            created_at=now,
            expires_at=expires_at,
        )
        await self._online_payment_repository.add(online_payment)
        await self._unit_of_work.commit()
        _logger.info(
            "payment_link_created",
            online_payment_id=str(online_payment.id),
            order_id=str(order.id),
            amount=str(amount),
        )
        return online_payment

    async def _amount_due(
        self,
        tenant_id: uuid.UUID,
        order: Order,
        existing: list[OnlinePayment],
        now: datetime,
    ) -> tuple[uuid.UUID | None, Decimal]:
        invoice = await self._invoice_repository.get_by_order_id(tenant_id, order.id)
        if invoice is not None:
            if invoice.status not in ("issued", "partially_paid"):
                # Paid, cancelled or refunded: nothing is owed on it.
                msg = f"Nothing is due on this order; its invoice is {invoice.status}."
                raise ConflictError(msg, order_id=str(order.id), invoice_status=invoice.status)
            # Paid-but-unapplied gateway money counts too: it is about to
            # land on this invoice and must not be asked for twice.
            pending = sum(
                (p.amount for p in existing if p.status == "paid" and not p.is_applied),
                Decimal("0"),
            )
            due = (invoice.total_amount - invoice.amount_paid - pending).quantize(
                _CENT, rounding=ROUND_HALF_UP
            )
            invoice_id: uuid.UUID | None = invoice.id
        else:
            if order.status not in _PREPAYABLE_STATUSES:
                msg = f"An order in status '{order.status}' cannot be paid online yet."
                raise ConflictError(msg, order_id=str(order.id), status=order.status)
            gst_rate = await resolve_gst_rate_percent(
                self._tenant_config_repository, tenant_id, now
            )
            paid = sum((p.amount for p in existing if p.status == "paid"), Decimal("0"))
            due = _prepayment_total(order, gst_rate) - paid
            invoice_id = None

        if due <= Decimal("0"):
            msg = "Nothing is due on this order."
            raise ConflictError(msg, order_id=str(order.id))
        return invoice_id, due


class ListOrderOnlinePaymentsUseCase:
    def __init__(
        self,
        *,
        order_repository: OrderRepository,
        online_payment_repository: OnlinePaymentRepository,
    ) -> None:
        self._order_repository = order_repository
        self._online_payment_repository = online_payment_repository

    async def execute(self, query: ListOrderOnlinePaymentsQuery) -> list[OnlinePayment]:
        order = await _get_scoped_order(self._order_repository, query.order_id, query.scope)
        return await self._online_payment_repository.list_for_order(order.id)


class RefreshOnlinePaymentUseCase:
    """Ask the gateway for a link's current status and apply it."""

    def __init__(
        self,
        *,
        order_repository: OrderRepository,
        invoice_repository: InvoiceRepository,
        online_payment_repository: OnlinePaymentRepository,
        gateway: PaymentGateway,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._order_repository = order_repository
        self._invoice_repository = invoice_repository
        self._online_payment_repository = online_payment_repository
        self._gateway = gateway
        self._unit_of_work = unit_of_work

    async def execute(self, command: RefreshOnlinePaymentCommand) -> OnlinePayment:
        online_payment = await self._online_payment_repository.get_by_id(command.online_payment_id)
        if online_payment is None:
            msg = f"No online payment visible with id {command.online_payment_id}."
            raise NotFoundError(msg, online_payment_id=str(command.online_payment_id))
        # Visibility follows the order, so scope is checked against it.
        await _get_scoped_order(self._order_repository, online_payment.order_id, command.scope)

        needs_gateway = online_payment.status == "created"
        if needs_gateway:
            if not self._gateway.is_configured:
                msg = "Online payments are not configured for this environment."
                raise ServiceUnavailableError(msg)
            try:
                status = await self._gateway.fetch_payment_link(online_payment.provider_link_id)
            except PaymentGatewayError as exc:
                msg = "The payment gateway could not be reached. Please try again."
                raise ServiceUnavailableError(msg) from exc
        else:
            # Already settled locally — still retry the invoice application,
            # which a webhook racing invoice generation can leave undone.
            status = PaymentLinkStatus(
                link_id=online_payment.provider_link_id, status=online_payment.status
            )

        await _apply_gateway_status(
            online_payment=online_payment,
            status=status,
            invoice_repository=self._invoice_repository,
            online_payment_repository=self._online_payment_repository,
        )
        await self._unit_of_work.commit()
        return online_payment


class HandlePaymentWebhookUseCase:
    """Apply a verified, tenant-resolved gateway event. The router has
    already checked the signature and opened a session scoped to the tenant
    named in the event's notes; RLS then guarantees the lookup below only
    ever sees that tenant's rows.
    """

    def __init__(
        self,
        *,
        invoice_repository: InvoiceRepository,
        online_payment_repository: OnlinePaymentRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._invoice_repository = invoice_repository
        self._online_payment_repository = online_payment_repository
        self._unit_of_work = unit_of_work

    async def execute(self, status: PaymentLinkStatus) -> OnlinePayment | None:
        online_payment = await self._online_payment_repository.get_by_provider_link_id(
            status.link_id
        )
        if online_payment is None:
            _logger.warning("payment_webhook_unknown_link", link_id=status.link_id)
            return None
        await _apply_gateway_status(
            online_payment=online_payment,
            status=status,
            invoice_repository=self._invoice_repository,
            online_payment_repository=self._online_payment_repository,
        )
        await self._unit_of_work.commit()
        _logger.info(
            "payment_webhook_applied",
            online_payment_id=str(online_payment.id),
            status=online_payment.status,
        )
        return online_payment
