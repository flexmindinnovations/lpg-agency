"""Online payments through Razorpay payment links (ADR-053).

- `POST /orders/{order_id}/payment-links` — create (or reuse) a link for
  what is still owed on an order. Used by the Customer App, staff, and the
  WhatsApp assistant alike.
- `GET /orders/{order_id}/online-payments` — the order's payment attempts.
- `POST /online-payments/{id}/refresh` — ask Razorpay for the link's status
  now (the app calls this when the customer returns from the payment page,
  so a missed or not-yet-delivered webhook never leaves an order unpaid).
- `GET /online-payments/availability` — whether online payment can be
  offered at all, so the apps hide "Pay Online" instead of failing with 503.
- `POST /payments/razorpay/webhook` — Razorpay's server-to-server callback for
  the platform's shared account; `…/webhook/{token}` is the per-agency URL
  (ADR-067). Unauthenticated by design; trusted only after the HMAC signature
  verifies against the right account's webhook secret.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

from lpg.api.v1.dependencies.accounting import get_invoice_repository
from lpg.api.v1.dependencies.admin import (
    get_cylinder_type_repository,
    get_tenant_configuration_repository,
)
from lpg.api.v1.dependencies.customer import get_customer_repository
from lpg.api.v1.dependencies.identity import get_current_principal, require_permission
from lpg.api.v1.dependencies.order import get_order_repository
from lpg.api.v1.dependencies.payments import (
    CredentialScopeFactory,
    GatewayBuilder,
    WebhookUseCaseFactory,
    get_gateway_builder,
    get_online_payment_repository,
    get_payment_credential_scope_factory,
    get_payment_gateway,
    get_payment_webhook_tenant_resolver,
    get_payment_webhook_use_case_factory,
    get_platform_gateway,
)
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.api.v1.schemas.online_payment import (
    OnlinePaymentAvailabilityResponse,
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
    SimulateOnlinePaymentPaidUseCase,
)
from lpg.application.accounting.payment_credentials import WebhookTenantResolver
from lpg.application.accounting.payment_gateway import (
    InvalidWebhookSignatureError,
    PaymentGateway,
    PaymentLinkStatus,
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
    "/online-payments/availability",
    response_model=OnlinePaymentAvailabilityResponse,
    dependencies=[Depends(require_permission("orders:read"))],
    summary="Whether online payment can be offered in this environment",
)
async def get_online_payment_availability(
    gateway: Annotated[PaymentGateway, Depends(get_payment_gateway)],
) -> OnlinePaymentAvailabilityResponse:
    """`available` is false when no payment gateway is configured; creating a
    payment link would then fail with 503, so the apps don't offer it.
    """
    return OnlinePaymentAvailabilityResponse(available=gateway.is_configured)


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
    "/online-payments/{online_payment_id}/simulate-paid",
    response_model=OnlinePaymentResponse,
    dependencies=[Depends(require_permission("payments:create"))],
    summary="Demo gateway only: mark a payment link paid",
    responses={409: {"description": "The payment was not made through the demo gateway."}},
)
async def simulate_online_payment_paid(
    online_payment_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    order_repository: Annotated[OrderRepository, Depends(get_order_repository)],
    invoice_repository: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
    online_payment_repository: Annotated[
        OnlinePaymentRepository, Depends(get_online_payment_repository)
    ],
    customer_repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> OnlinePaymentResponse:
    """Staff only (customers cannot pay themselves). Never available with a
    real gateway: the payment's own provider must be `mock`.
    """
    if principal.role == "customer":
        raise HTTPException(status_code=403, detail="Staff only.")
    scope = await _resolve_scope(principal, customer_repository)
    payment = await SimulateOnlinePaymentPaidUseCase(
        order_repository=order_repository,
        invoice_repository=invoice_repository,
        online_payment_repository=online_payment_repository,
        unit_of_work=unit_of_work,
    ).execute(
        RefreshOnlinePaymentCommand(
            tenant_id=principal.tenant_id, online_payment_id=online_payment_id, scope=scope
        )
    )
    return _to_response(payment)


@router.get(
    "/payments/mock/{link_id}",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def mock_checkout_page(link_id: str) -> HTMLResponse:  # noqa: ARG001
    """What the demo gateway's payment link opens. No money moves."""
    if get_settings().payments_provider != "mock":
        raise HTTPException(status_code=404)
    return HTMLResponse(
        "<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
        "<title>Demo payment</title>"
        "<body style='font-family:sans-serif;max-width:28rem;margin:3rem auto;padding:0 1rem'>"
        "<h2>Demo payment gateway</h2>"
        "<p>This is a test link. No money is taken.</p>"
        "<p>Ask the agency to confirm the payment (staff use <b>Simulate payment</b>), "
        "then come back to the app and pull to refresh.</p></body>"
    )


async def _apply_webhook_event(
    status: PaymentLinkStatus | None,
    use_case_factory: WebhookUseCaseFactory,
    *,
    expected_tenant_id: uuid.UUID | None,
) -> WebhookAck:
    """Applies a signature-verified event. `expected_tenant_id` is the tenant
    the per-agency webhook URL named: the event must belong to it, so one
    agency's webhook secret can never settle another agency's payments.
    """
    if status is None:
        return WebhookAck(received=True)

    try:
        tenant_id = uuid.UUID(status.notes.get("tenant_id", ""))
    except ValueError:
        _logger.warning("payment_webhook_without_tenant", link_id=status.link_id)
        return WebhookAck(received=True)
    if expected_tenant_id is not None and tenant_id != expected_tenant_id:
        _logger.warning("payment_webhook_tenant_mismatch", link_id=status.link_id)
        return WebhookAck(received=True)

    async with use_case_factory(tenant_id) as use_case:
        await use_case.execute(status)
    return WebhookAck(received=True)


@router.post(
    "/payments/razorpay/webhook",
    response_model=WebhookAck,
    summary="Razorpay webhook receiver (platform default account)",
    responses={400: {"description": "Signature missing or invalid."}},
)
async def razorpay_webhook(
    request: Request,
    gateway: Annotated[PaymentGateway, Depends(get_platform_gateway)],
    use_case_factory: Annotated[
        WebhookUseCaseFactory, Depends(get_payment_webhook_use_case_factory)
    ],
) -> WebhookAck:
    """For agencies on the platform's shared Razorpay account (the
    `LPG_RAZORPAY_*` environment). Answers 200 for every verified event,
    including ones it ignores, so Razorpay does not keep retrying them; only
    a bad signature is refused.
    """
    body = await request.body()
    try:
        status = gateway.parse_webhook(body, request.headers.get("X-Razorpay-Signature"))
    except InvalidWebhookSignatureError:
        _logger.warning("payment_webhook_signature_invalid")
        raise HTTPException(status_code=400, detail="Invalid webhook signature.") from None
    return await _apply_webhook_event(status, use_case_factory, expected_tenant_id=None)


@router.post(
    "/payments/razorpay/webhook/{token}",
    response_model=WebhookAck,
    summary="Razorpay webhook receiver for one agency's own account",
    responses={
        400: {"description": "Signature missing or invalid."},
        404: {"description": "Unknown webhook URL."},
    },
)
async def razorpay_agency_webhook(
    token: str,
    request: Request,
    tenant_resolver: Annotated[WebhookTenantResolver, Depends(get_payment_webhook_tenant_resolver)],
    build_gateway: Annotated[GatewayBuilder, Depends(get_gateway_builder)],
    credential_scope: Annotated[
        CredentialScopeFactory, Depends(get_payment_credential_scope_factory)
    ],
    use_case_factory: Annotated[
        WebhookUseCaseFactory, Depends(get_payment_webhook_use_case_factory)
    ],
) -> WebhookAck:
    """The opaque `token` names the agency; that agency's own webhook secret
    then verifies the signature (ADR-067).
    """
    tenant_id = await tenant_resolver.resolve(token)
    if tenant_id is None:
        raise HTTPException(status_code=404, detail="Unknown webhook URL.")
    async with credential_scope(tenant_id) as repository:
        credentials = await repository.get()
    if credentials is None:
        raise HTTPException(status_code=404, detail="Unknown webhook URL.")

    gateway = build_gateway(credentials)
    body = await request.body()
    try:
        status = gateway.parse_webhook(body, request.headers.get("X-Razorpay-Signature"))
    except InvalidWebhookSignatureError:
        _logger.warning("payment_webhook_signature_invalid", tenant_id=str(tenant_id))
        raise HTTPException(status_code=400, detail="Invalid webhook signature.") from None
    return await _apply_webhook_event(status, use_case_factory, expected_tenant_id=tenant_id)
