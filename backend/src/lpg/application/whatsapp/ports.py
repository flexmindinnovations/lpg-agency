"""Ports for the WhatsApp customer assistant (ADR-054).

Customers message the agency's WhatsApp Business number; Meta's Cloud API
delivers each message to our webhook, a background job runs it through the
model gateway with a fixed menu of customer-scoped tools, and the reply goes
back through the Cloud API.

Everything here is vendor-neutral: Meta specifics live in
`infrastructure/whatsapp/`, persistence in `infrastructure/persistence/`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid
    from datetime import date, datetime
    from decimal import Decimal

    from lpg.application.ai.ports import AssistantRunRepository
    from lpg.application.common.ports import UnitOfWork
    from lpg.application.complaint.ports import ComplaintNumberSequence, ComplaintUnitOfWork
    from lpg.application.customer.ports import CustomerRepository
    from lpg.application.delivery.ports import DriverRepository, RouteRepository, VehicleRepository
    from lpg.application.inventory.ports import InventoryLocationRepository
    from lpg.application.order.ports import (
        CancellationRecordRepository,
        OrderNumberSequence,
        OrderRepository,
    )
    from lpg.application.tenant.ports import (
        CylinderTypeRepository,
        PriceListRepository,
        TenantConfigurationRepository,
    )
    from lpg.application.tenant_admin.ports import EmployeeRepository


@dataclass(frozen=True, slots=True)
class InboundWhatsAppMessage:
    """One customer text message, as parsed from Meta's webhook payload."""

    #: The business number that received it, which decides the tenant.
    phone_number_id: str
    #: Meta's own message id (`wamid...`), the idempotency key: Meta retries
    #: webhook deliveries, and a retried message must not be answered twice.
    wa_message_id: str
    #: The sender in E.164 (`+919876543210`), the same format `Customer`
    #: stores, so it is the customer lookup key.
    from_phone: str
    profile_name: str | None
    text: str


@dataclass(frozen=True, slots=True)
class ConversationEntry:
    direction: Literal["inbound", "outbound"]
    body: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class PendingOrderQuote:
    """An order the assistant has priced and read back to the customer but
    not yet placed. Placing it is a separate tool call that is only allowed
    once the customer has replied after the quote (see `tools.py`), so the
    model alone can never book an order in the same breath it proposes one.
    """

    cylinder_type_id: uuid.UUID
    cylinder_type_name: str
    quantity: int
    address_id: uuid.UUID
    address_line: str
    latitude: float | None
    longitude: float | None
    requested_date: date
    payment_method: str
    estimated_unit_price: Decimal | None
    quoted_at: datetime


@runtime_checkable
class WhatsAppConversationRepository(Protocol):
    """The per-tenant WhatsApp message log and conversation state. Every
    query is RLS-scoped to the current tenant."""

    async def record_inbound(self, message: InboundWhatsAppMessage) -> bool:
        """Stores the message; returns `False` (and stores nothing) when this
        `wa_message_id` was already recorded."""
        ...

    async def record_outbound(
        self, *, to_phone: str, body: str, wa_message_id: str | None, status: str
    ) -> None: ...

    async def list_recent(
        self, phone: str, *, since: datetime, limit: int
    ) -> list[ConversationEntry]:
        """The latest `limit` messages with `phone` since `since`, oldest
        first."""
        ...

    async def get_pending_quote(self, phone: str) -> PendingOrderQuote | None: ...

    async def set_pending_quote(self, phone: str, quote: PendingOrderQuote | None) -> None: ...


@runtime_checkable
class WhatsAppSenderPort(Protocol):
    async def send_text(self, *, phone_number_id: str, to: str, body: str) -> str | None:
        """Sends a free-form text reply. Returns Meta's message id, or `None`
        when sending failed (already logged); never raises."""
        ...


@dataclass(frozen=True, slots=True)
class PaymentLinkRequest:
    order_id: uuid.UUID
    #: The customer the assistant is talking to; the order must be theirs.
    customer_id: uuid.UUID
    #: Audited as the link's creator.
    requested_by: uuid.UUID
    order_number: str
    #: `None` while the order is unpriced (prices are fixed at confirmation).
    amount: Decimal | None
    customer_name: str
    customer_phone: str


@dataclass(frozen=True, slots=True)
class PaymentLink:
    url: str
    amount: Decimal


@runtime_checkable
class PaymentLinkPort(Protocol):
    """Online payment for an order: `GatewayPaymentLinks` when a payment
    gateway is configured (Razorpay, ADR-053), otherwise
    `UnconfiguredPaymentLinks`, which answers every call with `None` so the
    assistant offers cash or UPI on delivery instead."""

    async def create_payment_link(self, request: PaymentLinkRequest) -> PaymentLink | None:
        """`None` when online payment is unavailable; raises
        `ApplicationError` when this order cannot be paid online (nothing
        due, not yet confirmed), which the tool reports to the customer."""
        ...


@dataclass(frozen=True, slots=True)
class WhatsAppScope:
    """The repositories one transaction of the assistant needs, all bound to
    the same tenant-scoped `UnitOfWork`. A `UnitOfWork` commits once
    (`get_unit_of_work_factory`'s docstring explains why), so every write the
    assistant makes opens its own scope through a `WhatsAppScopeFactory`."""

    unit_of_work: UnitOfWork
    conversations: WhatsAppConversationRepository
    customers: CustomerRepository
    orders: OrderRepository
    order_numbers: OrderNumberSequence
    cancellations: CancellationRecordRepository
    cylinder_types: CylinderTypeRepository
    price_lists: PriceListRepository
    tenant_configuration: TenantConfigurationRepository
    routes: RouteRepository
    drivers: DriverRepository
    vehicles: VehicleRepository
    employees: EmployeeRepository
    inventory: InventoryLocationRepository
    complaints: ComplaintUnitOfWork
    complaint_numbers: ComplaintNumberSequence
    assistant_runs: AssistantRunRepository
