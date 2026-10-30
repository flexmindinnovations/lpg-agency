"""The agency's payment profile and UPI pay QR (ADR-066).

- `GET /payment-profile` — any signed-in user; bank and UPI details are
  printed on every invoice anyway, and the apps show them beside the QR.
- `PUT /payment-profile` — `tenant:configure`. Refuses an IFSC no bank branch holds.
- `POST /payment-profile/verify` — `tenant:configure`. Checks an IFSC against the
  bank-branch directory and a UPI ID's handle, without saving anything.
- `GET /payments/upi-qr?order_id=|invoice_id=` — the UPI link and QR for what
  is still owed. Customers see only their own orders and invoices; branch
  staff only their branch's orders (the same scope as online payments).
"""

from __future__ import annotations

import base64
import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from lpg.api.v1.dependencies.accounting import get_invoice_repository
from lpg.api.v1.dependencies.admin import (
    get_cylinder_type_repository,
    get_tenant_configuration_repository,
)
from lpg.api.v1.dependencies.customer import get_customer_repository
from lpg.api.v1.dependencies.identity import get_current_principal, require_permission
from lpg.api.v1.dependencies.order import get_order_repository
from lpg.api.v1.dependencies.payments import (
    get_ifsc_directory,
    get_online_payment_repository,
    get_payment_gateway,
)
from lpg.api.v1.dependencies.printing import get_printing_engine
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.api.v1.routers.online_payment import _resolve_scope
from lpg.api.v1.schemas.payment_profile import (
    IfscCheckResponse,
    PaymentProfileResponse,
    SetPaymentProfileRequest,
    UpiCheckResponse,
    UpiQrResponse,
    VerifyPaymentDetailsRequest,
    VerifyPaymentDetailsResponse,
)
from lpg.application.accounting.online_payments import (
    CreateOrderPaymentLinkCommand,
    CreateOrderPaymentLinkUseCase,
)
from lpg.application.accounting.payment_gateway import PaymentGateway
from lpg.application.accounting.payment_profile import (
    GetPaymentProfileUseCase,
    PaymentProfile,
    SetPaymentProfileUseCase,
    build_upi_uri,
    is_valid_ifsc,
    is_valid_vpa,
)
from lpg.application.accounting.payment_verification import (
    IfscDirectory,
    check_ifsc,
    check_upi_id,
)
from lpg.application.accounting.ports import InvoiceRepository, OnlinePaymentRepository
from lpg.application.common.errors import ConflictError, NotFoundError, ValidationError
from lpg.application.common.ports import UnitOfWork
from lpg.application.customer.ports import CustomerRepository
from lpg.application.identity.ports import AuthenticatedPrincipal
from lpg.application.order.ports import OrderRepository
from lpg.application.printing.ports import PrintingEngine
from lpg.application.tenant.ports import CylinderTypeRepository, TenantConfigurationRepository

router = APIRouter(tags=["Payment Profile"])


def _to_response(profile: PaymentProfile) -> PaymentProfileResponse:
    return PaymentProfileResponse(
        **profile.to_config(),
        has_bank_details=profile.has_bank_details,
        has_upi=profile.has_upi,
    )


@router.get("/payment-profile", response_model=PaymentProfileResponse)
async def get_payment_profile(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[
        TenantConfigurationRepository, Depends(get_tenant_configuration_repository)
    ],
) -> PaymentProfileResponse:
    profile = await GetPaymentProfileUseCase(repository).execute(principal.tenant_id)
    return _to_response(profile)


@router.put("/payment-profile", response_model=PaymentProfileResponse)
async def set_payment_profile(
    body: SetPaymentProfileRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("tenant:configure"))],
    repository: Annotated[
        TenantConfigurationRepository, Depends(get_tenant_configuration_repository)
    ],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    ifsc_directory: Annotated[IfscDirectory, Depends(get_ifsc_directory)],
) -> PaymentProfileResponse:
    """Replaces the whole profile. Each save is a new historised row."""
    profile = PaymentProfile.validated(**body.model_dump())
    if profile.ifsc and (await check_ifsc(ifsc_directory, profile.ifsc)).status == "not_found":
        msg = "No bank branch has this IFSC. Check the code on your cheque book or passbook."
        raise ValidationError(msg, field="ifsc")
    saved = await SetPaymentProfileUseCase(repository, unit_of_work).execute(
        principal.tenant_id, profile
    )
    return _to_response(saved)


@router.post(
    "/payment-profile/verify",
    response_model=VerifyPaymentDetailsResponse,
    dependencies=[Depends(require_permission("tenant:configure"))],
    summary="Check an IFSC and a UPI ID before saving them",
)
async def verify_payment_details(
    body: VerifyPaymentDetailsRequest,
    ifsc_directory: Annotated[IfscDirectory, Depends(get_ifsc_directory)],
) -> VerifyPaymentDetailsResponse:
    """The IFSC is looked up in the bank-branch directory. The UPI ID is checked
    for shape and a known handle only: that the ID exists, and whose it is,
    needs a payment-provider account, so `account_confirmed` is always false.
    """
    result = VerifyPaymentDetailsResponse()
    ifsc = body.ifsc.strip().upper()
    if ifsc:
        if not is_valid_ifsc(ifsc):
            msg = "IFSC must be 11 characters, like HDFC0001234."
            raise ValidationError(msg, field="ifsc")
        check = await check_ifsc(ifsc_directory, ifsc)
        details = check.details
        result.ifsc = IfscCheckResponse(
            status=check.status,
            bank=details.bank if details else "",
            branch=details.branch if details else "",
            city=details.city if details else "",
            state=details.state if details else "",
            address=details.address if details else "",
            supports_upi=details.upi if details else False,
            supports_neft=details.neft if details else False,
            supports_imps=details.imps if details else False,
        )
    upi_id = body.upi_id.strip().lower()
    if upi_id:
        if not is_valid_vpa(upi_id):
            result.upi = UpiCheckResponse(format_valid=False)
        else:
            upi = check_upi_id(upi_id)
            result.upi = UpiCheckResponse(
                format_valid=True,
                handle=upi.handle,
                provider=upi.provider,
                handle_known=upi.handle_known,
            )
    return result


@router.get(
    "/payments/upi-qr",
    response_model=UpiQrResponse,
    dependencies=[Depends(require_permission("orders:read"))],
    summary="UPI link and QR for what is still owed on an order or invoice",
    responses={409: {"description": "No UPI ID is set up, or nothing is due."}},
)
async def get_upi_qr(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    config_repository: Annotated[
        TenantConfigurationRepository, Depends(get_tenant_configuration_repository)
    ],
    order_repository: Annotated[OrderRepository, Depends(get_order_repository)],
    invoice_repository: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
    online_payment_repository: Annotated[
        OnlinePaymentRepository, Depends(get_online_payment_repository)
    ],
    customer_repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
    cylinder_type_repository: Annotated[
        CylinderTypeRepository, Depends(get_cylinder_type_repository)
    ],
    gateway: Annotated[PaymentGateway, Depends(get_payment_gateway)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    engine: Annotated[PrintingEngine, Depends(get_printing_engine)],
    order_id: Annotated[uuid.UUID | None, Query()] = None,
    invoice_id: Annotated[uuid.UUID | None, Query()] = None,
) -> UpiQrResponse:
    if (order_id is None) == (invoice_id is None):
        msg = "Pass either order_id or invoice_id."
        raise ValidationError(msg)
    profile = await GetPaymentProfileUseCase(config_repository).execute(principal.tenant_id)
    if not profile.has_upi:
        msg = "This agency has not set up a UPI ID yet."
        raise ConflictError(msg)

    scope = await _resolve_scope(principal, customer_repository)
    if order_id is not None:
        use_case = CreateOrderPaymentLinkUseCase(
            order_repository=order_repository,
            invoice_repository=invoice_repository,
            online_payment_repository=online_payment_repository,
            customer_repository=customer_repository,
            tenant_config_repository=config_repository,
            cylinder_type_repository=cylinder_type_repository,
            gateway=gateway,
            unit_of_work=unit_of_work,
            link_ttl=timedelta(minutes=30),
        )
        order, amount = await use_case.quote(
            CreateOrderPaymentLinkCommand(
                tenant_id=principal.tenant_id,
                order_id=order_id,
                requested_by=principal.user_id or uuid.UUID(int=0),
                scope=scope,
            )
        )
        label = order.order_number or str(order.id)
        reference = label
    else:
        invoice = await invoice_repository.get_by_id(invoice_id)  # type: ignore[arg-type]
        if invoice is None or (
            scope.customer_id is not None and invoice.customer_id != scope.customer_id
        ):
            msg = "Invoice not found."
            raise NotFoundError(msg)
        amount = invoice.balance_due
        if amount <= Decimal("0"):
            msg = "Nothing is due on this invoice."
            raise ConflictError(msg)
        label = invoice.invoice_number or str(invoice.id)
        reference = label

    uri = build_upi_uri(profile, amount=amount, note=f"LPG {label}", reference=reference)
    png = engine.generate_qr_code(uri, size=360)
    return UpiQrResponse(
        upi_uri=uri,
        upi_id=profile.upi_id,
        payee_name=profile.payee_name,
        amount=amount,
        order_id=order_id,
        invoice_id=invoice_id,
        qr_png_base64=base64.b64encode(png).decode(),
    )
