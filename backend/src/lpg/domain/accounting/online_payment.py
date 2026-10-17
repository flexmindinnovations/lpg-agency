"""`OnlinePayment` aggregate root.

One attempt to collect money through a payment gateway (Razorpay, ADR-052)
for an order — either before delivery (a prepayment, `payment-flow.md`
Path A) or against the order's already-issued invoice. Tracked as its own
aggregate rather than inside `Invoice` because a prepayment exists before
any invoice does: invoices are only generated at delivery (BR-17), and the
gateway's confirmation arrives asynchronously, on a webhook, as a separate
transaction from the request that created the link.

Lifecycle: `created` -> `paid` | `expired` | `cancelled`. A `paid` payment
is later *applied* to the order's invoice (becoming an ordinary
`accounting.payment` row with method `online_gateway`) — immediately if the
invoice already exists, otherwise when the invoice is generated.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from lpg.domain.common.base import AggregateRoot, DomainEvent, InvariantViolation

if TYPE_CHECKING:
    import uuid
    from datetime import datetime


ONLINE_PAYMENT_STATUSES: frozenset[str] = frozenset({"created", "paid", "expired", "cancelled"})


@dataclass(frozen=True, slots=True)
class OnlinePaymentReceived(DomainEvent):
    """The gateway confirmed the money was captured."""

    online_payment_id: uuid.UUID
    tenant_id: uuid.UUID
    order_id: uuid.UUID
    customer_id: uuid.UUID
    amount: Decimal
    provider: str
    provider_payment_id: str
    paid_at: datetime


class OnlinePayment(AggregateRoot):
    """Business invariants:
    - `amount` is positive and has at most two decimal places (gateways
      charge in whole paise).
    - Only a `created` payment can expire or be cancelled.
    - A gateway's "paid" confirmation always wins, even over a locally
      expired/cancelled link — the money has moved, so the record must say so.
    - It can be applied to an invoice once, and only after it is `paid`.
    """

    __slots__ = (
        "_amount",
        "_applied_payment_id",
        "_created_at",
        "_created_by",
        "_currency",
        "_customer_id",
        "_expires_at",
        "_invoice_id",
        "_order_id",
        "_paid_at",
        "_payment_method",
        "_provider",
        "_provider_link_id",
        "_provider_payment_id",
        "_short_url",
        "_status",
        "_tenant_id",
    )

    def __init__(
        self,
        *,
        online_payment_id: uuid.UUID,
        tenant_id: uuid.UUID,
        order_id: uuid.UUID,
        customer_id: uuid.UUID,
        amount: Decimal,
        currency: str,
        provider: str,
        provider_link_id: str,
        short_url: str,
        status: str,
        created_by: uuid.UUID,
        created_at: datetime,
        expires_at: datetime | None = None,
        invoice_id: uuid.UUID | None = None,
        provider_payment_id: str | None = None,
        payment_method: str | None = None,
        paid_at: datetime | None = None,
        applied_payment_id: uuid.UUID | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(online_payment_id, version=version)
        if status not in ONLINE_PAYMENT_STATUSES:
            msg = f"'{status}' is not a valid online payment status."
            raise InvariantViolation(msg, status=status)
        if amount <= Decimal("0"):
            msg = f"Online payment amount must be > 0, got {amount}."
            raise InvariantViolation(msg)
        if amount != amount.quantize(Decimal("0.01")):
            msg = f"Online payment amount must have at most 2 decimal places, got {amount}."
            raise InvariantViolation(msg)

        self._tenant_id = tenant_id
        self._order_id = order_id
        self._customer_id = customer_id
        self._invoice_id = invoice_id
        self._amount = amount
        self._currency = currency
        self._provider = provider
        self._provider_link_id = provider_link_id
        self._short_url = short_url
        self._status = status
        self._created_by = created_by
        self._created_at = created_at
        self._expires_at = expires_at
        self._provider_payment_id = provider_payment_id
        self._payment_method = payment_method
        self._paid_at = paid_at
        self._applied_payment_id = applied_payment_id

    @classmethod
    def create(
        cls,
        *,
        online_payment_id: uuid.UUID,
        tenant_id: uuid.UUID,
        order_id: uuid.UUID,
        customer_id: uuid.UUID,
        invoice_id: uuid.UUID | None,
        amount: Decimal,
        currency: str,
        provider: str,
        provider_link_id: str,
        short_url: str,
        created_by: uuid.UUID,
        created_at: datetime,
        expires_at: datetime | None,
    ) -> OnlinePayment:
        return cls(
            online_payment_id=online_payment_id,
            tenant_id=tenant_id,
            order_id=order_id,
            customer_id=customer_id,
            invoice_id=invoice_id,
            amount=amount,
            currency=currency,
            provider=provider,
            provider_link_id=provider_link_id,
            short_url=short_url,
            status="created",
            created_by=created_by,
            created_at=created_at,
            expires_at=expires_at,
        )

    # -- Properties ------------------------------------------------------

    @property
    def tenant_id(self) -> uuid.UUID:
        return self._tenant_id

    @property
    def order_id(self) -> uuid.UUID:
        return self._order_id

    @property
    def customer_id(self) -> uuid.UUID:
        return self._customer_id

    @property
    def invoice_id(self) -> uuid.UUID | None:
        return self._invoice_id

    @property
    def amount(self) -> Decimal:
        return self._amount

    @property
    def currency(self) -> str:
        return self._currency

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def provider_link_id(self) -> str:
        return self._provider_link_id

    @property
    def short_url(self) -> str:
        return self._short_url

    @property
    def status(self) -> str:
        return self._status

    @property
    def created_by(self) -> uuid.UUID:
        return self._created_by

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def expires_at(self) -> datetime | None:
        return self._expires_at

    @property
    def provider_payment_id(self) -> str | None:
        return self._provider_payment_id

    @property
    def payment_method(self) -> str | None:
        return self._payment_method

    @property
    def paid_at(self) -> datetime | None:
        return self._paid_at

    @property
    def applied_payment_id(self) -> uuid.UUID | None:
        return self._applied_payment_id

    @property
    def is_applied(self) -> bool:
        return self._applied_payment_id is not None

    def is_reusable(self, *, amount: Decimal, now: datetime) -> bool:
        """Whether this still-open link can be handed out again instead of
        creating a new one — the customer tapping "Pay" twice must not
        produce two links that could both be paid.
        """
        if self._status != "created" or self._amount != amount:
            return False
        return self._expires_at is None or self._expires_at > now

    # -- Transitions -----------------------------------------------------

    def mark_paid(
        self,
        *,
        provider_payment_id: str,
        payment_method: str | None,
        paid_at: datetime,
    ) -> bool:
        """Record the gateway's capture confirmation. Returns `False` (and
        changes nothing) if it was already recorded — gateways retry
        webhooks, so this must be idempotent.
        """
        if self._status == "paid":
            return False
        self._status = "paid"
        self._provider_payment_id = provider_payment_id
        self._payment_method = payment_method
        self._paid_at = paid_at
        self.record_event(
            OnlinePaymentReceived(
                online_payment_id=self.id,
                tenant_id=self._tenant_id,
                order_id=self._order_id,
                customer_id=self._customer_id,
                amount=self._amount,
                provider=self._provider,
                provider_payment_id=provider_payment_id,
                paid_at=paid_at,
            )
        )
        return True

    def mark_closed(self, status: str) -> bool:
        """`created -> expired | cancelled`. Returns `False` if the payment
        is no longer open (already paid, expired or cancelled).
        """
        if status not in ("expired", "cancelled"):
            msg = f"'{status}' is not a closing status."
            raise InvariantViolation(msg, status=status)
        if self._status != "created":
            return False
        self._status = status
        return True

    def mark_applied(self, *, invoice_id: uuid.UUID, payment_id: uuid.UUID) -> None:
        """Link this payment to the invoice `Payment` it became."""
        if self._status != "paid":
            msg = "Only a paid online payment can be applied to an invoice."
            raise InvariantViolation(msg, status=self._status)
        if self._applied_payment_id is not None:
            msg = "Online payment has already been applied to an invoice."
            raise InvariantViolation(msg)
        self._invoice_id = invoice_id
        self._applied_payment_id = payment_id
