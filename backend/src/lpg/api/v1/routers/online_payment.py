"""Online payments through Razorpay payment links (ADR-053).

- `POST /orders/{order_id}/payment-links` — create (or reuse) a link for
  what is still owed on an order. Used by the Customer App, staff, and the
  WhatsApp assistant alike.
- `GET /orders/{order_id}/online-payments` — the order's payment attempts.
- `POST /online-payments/{id}/refresh` — ask Razorpay for the link's status
  now (the app calls this when the customer returns from the payment page,
  so a missed or not-yet-delivered webhook never leaves an order unpaid).
- `POST /payments/razorpay/webhook` — Razorpay's server-to-server callback.
  Unauthenticated by design; trusted only after its HMAC signature verifies.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from lpg.api.v1.dependencies.accounting import get_invoice_repository
from lpg.api.v1.dependencies.admin import (
    get_cylinder_type_repository,
    get_tenant_configuration_repository,
)
from lpg.api.v1.dependencies.customer import get_customer_repository
from lpg.api.v1.dependencies.identity import get_current_principal, require_permission
from lpg.api.v1.dependencies.order import get_order_repository
from lpg.api.v1.dependencies.payments import (
    WebhookUseCaseFactory,
    get_online_payment_repository,
    get_payment_gateway,
    get_payment_webhook_use_case_factory,
)
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.api.v1.schemas.online_payment import (
    OnlinePaymentListResponse,
    OnlinePaymentResponse,
    WebhookAck,
)
from lpg.application.accounting.online_payments import (
    CreateOrderPaymentLinkCommand,
    CreateOrderPaymentLinkUseCase,
    ListOrderOnlinePaymentsQuery,
    ListOrderOnlinePaymentsUseCase,
    OrderPaymentScope,
    RefreshOnlinePaymentCommand,
    RefreshOnlinePaymentUseCase,
)
from lpg.application.accounting.payment_gateway import (
    InvalidWebhookSignatureError,
    PaymentGateway,
)
from lpg.application.accounting.ports import InvoiceRepository, OnlinePaymentRepository
from lpg.application.common.errors import NotFoundError
from lpg.application.common.ports import UnitOfWork
from lpg.application.customer.ports import CustomerRepository
from lpg.application.identity.ports import AuthenticatedPrincipal
from lpg.application.order.ports import OrderRepository
from lpg.application.tenant.ports import CylinderTypeRepository, TenantConfigurationRepository
from lpg.config.logging import get_logger
from lpg.config.settings import get_settings
from lpg.domain.accounting.online_payment import OnlinePayment

router = APIRouter(tags=["Online Payments"])

_logger = get_logger(__name__)


async def _resolve_scope(
    principal: AuthenticatedPrincipal, customer_repository: CustomerRepository
) -> OrderPaymentScope:
    """Customers see only their own orders; dispatchers and managers only
    their branch's — the same rule the order endpoints apply.
    """
    if principal.role == "customer":
        own = (
            await customer_repository.get_by_identity_user_id(principal.user_id)
            if principal.user_id is not None
            else None
        )
        if own is None:
            msg = "No customer profile linked to this account."
            raise NotFoundError(msg)
        return OrderPaymentScope(customer_id=own.id)
    if principal.role in ("dispatcher", "manager"):
        return OrderPaymentScope(branch_id=principal.branch_id)
    return OrderPaymentScope()


def _to_response(payment: OnlinePayment) -> OnlinePaymentResponse:
    return OnlinePaymentResponse(
        online_payment_id=payment.id,
        order_id=payment.order_id,
        invoice_id=payment.invoice_id,
        amount=payment.amount,
        currency=payment.currency,
        status=payment.status,
        provider=payment.provider,
        payment_url=payment.short_url,
        expires_at=payment.expires_at,
        paid_at=payment.paid_at,
        payment_method=payment.payment_method,
        applied_to_invoice=payment.is_applied,
        created_at=payment.created_at,
    )


@router.post(
    "/orders/{order_id}/payment-links",
    response_model=OnlinePaymentResponse,
    status_code=201,
    dependencies=[Depends(require_permission("payments:create"))],
    summary="Create a payment link for what is owed on an order",
    responses={
        404: {"description": "Order not found or not visible to the caller."},
        409: {"description": "Nothing is due, or the order cannot be paid yet."},
        503: {"description": "Payments are not configured or the gateway failed."},
    },
)
async def create_payment_link(
    order_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    order_repository: Annotated[OrderRepository, Depends(get_order_repository)],
    invoice_repository: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
    online_payment_repository: Annotated[
        OnlinePaymentRepository, Depends(get_online_payment_repository)
    ],
    customer_repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
    tenant_config_repository: Annotated[
        TenantConfigurationRepository, Depends(get_tenant_configuration_repository)
    ],
    cylinder_type_repository: Annotated[
        CylinderTypeRepository, Depends(get_cylinder_type_repository)
    ],
    gateway: Annotated[PaymentGateway, Depends(get_payment_gateway)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> OnlinePaymentResponse:
    """Returns the still-open link instead of a new one if the amount due
    has not changed, so repeated taps never produce two payable links.
    """
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="An authenticated user is required.")
    scope = await _resolve_scope(principal, customer_repository)
    use_case = CreateOrderPaymentLinkUseCase(
        order_repository=order_repository,
        invoice_repository=invoice_repository,
        online_payment_repository=online_payment_repository,
        customer_repository=customer_repository,
        tenant_config_repository=tenant_config_repository,
        cylinder_type_repository=cylinder_type_repository,
        gateway=gateway,
        unit_of_work=unit_of_work,
        link_ttl=timedelta(minutes=get_settings().payment_link_ttl_minutes),
    )
    payment = await use_case.execute(
        CreateOrderPaymentLinkCommand(
            tenant_id=principal.tenant_id,
            order_id=order_id,
            requested_by=principal.user_id,
            scope=scope,
        )
    )
    return _to_response(payment)


@router.get(
    "/orders/{order_id}/online-payments",
    response_model=OnlinePaymentListResponse,
    dependencies=[Depends(require_permission("orders:read"))],
    summary="List an order's online payment attempts, newest first",
)
async def list_order_online_payments(
    order_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    order_repository: Annotated[OrderRepository, Depends(get_order_repository)],
    online_payment_repository: Annotated[
        OnlinePaymentRepository, Depends(get_online_payment_repository)
    ],
    customer_repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
) -> OnlinePaymentListResponse:
    scope = await _resolve_scope(principal, customer_repository)
    use_case = ListOrderOnlinePaymentsUseCase(
        order_repository=order_repository,
        online_payment_repository=online_payment_repository,
    )
    payments = await use_case.execute(ListOrderOnlinePaymentsQuery(order_id=order_id, scope=scope))
    return OnlinePaymentListResponse(items=[_to_response(p) for p in payments])


@router.post(
    "/online-payments/{online_payment_id}/refresh",
    response_model=OnlinePaymentResponse,
    dependencies=[Depends(require_permission("payments:create"))],
    summary="Re-check a payment link's status with the gateway",
)
async def refresh_online_payment(
    online_payment_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    order_repository: Annotated[OrderRepository, Depends(get_order_repository)],
    invoice_repository: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
    online_payment_repository: Annotated[
        OnlinePaymentRepository, Depends(get_online_payment_repository)
    ],
    customer_repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
    gateway: Annotated[PaymentGateway, Depends(get_payment_gateway)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> OnlinePaymentResponse:
    scope = await _resolve_scope(principal, customer_repository)
    use_case = RefreshOnlinePaymentUseCase(
        order_repository=order_repository,
        invoice_repository=invoice_repository,
        online_payment_repository=online_payment_repository,
        gateway=gateway,
        unit_of_work=unit_of_work,
    )
    payment = await use_case.execute(
        RefreshOnlinePaymentCommand(
            tenant_id=principal.tenant_id,
            online_payment_id=online_payment_id,
            scope=scope,
        )
    )
    return _to_response(payment)


@router.post(
    "/payments/razorpay/webhook",
    response_model=WebhookAck,
    summary="Razorpay webhook receiver",
    responses={400: {"description": "Signature missing or invalid."}},
)
async def razorpay_webhook(
    request: Request,
    gateway: Annotated[PaymentGateway, Depends(get_payment_gateway)],
    use_case_factory: Annotated[
        WebhookUseCaseFactory, Depends(get_payment_webhook_use_case_factory)
    ],
) -> WebhookAck:
    """Answers 200 for every verified event, including ones it ignores, so
    Razorpay does not keep retrying them; only a bad signature is refused.
    """
    body = await request.body()
    try:
        status = gateway.parse_webhook(body, request.headers.get("X-Razorpay-Signature"))
    except InvalidWebhookSignatureError:
        _logger.warning("payment_webhook_signature_invalid")
        raise HTTPException(status_code=400, detail="Invalid webhook signature.") from None

    if status is None:
        return WebhookAck(received=True)

    try:
        tenant_id = uuid.UUID(status.notes.get("tenant_id", ""))
    except ValueError:
        _logger.warning("payment_webhook_without_tenant", link_id=status.link_id)
        return WebhookAck(received=True)

    async with use_case_factory(tenant_id) as use_case:
        await use_case.execute(status)
    return WebhookAck(received=True)
