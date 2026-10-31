"""An agency's own Razorpay credentials (ADR-067).

All endpoints need `tenant:configure` (agency admins). Secrets are
write-only: no response ever carries a key secret or webhook secret.

- `GET    /payment-gateway`                       — masked key, mode, webhook path.
- `PUT    /payment-gateway`                       — save the key (and webhook secret).
- `DELETE /payment-gateway`                       — remove it; the platform default applies again.
- `POST   /payment-gateway/rotate-webhook-token`  — issue a new webhook URL.
- `POST   /payment-gateway/test`                  — one authenticated call to Razorpay.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from lpg.api.v1.dependencies.identity import require_permission
from lpg.api.v1.dependencies.payments import (
    GatewayBuilder,
    get_gateway_builder,
    get_gateway_fallback,
    get_payment_credential_repository,
)
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.api.v1.schemas.payment_gateway import (
    PaymentGatewaySettingsResponse,
    PaymentGatewayTestResponse,
    SetPaymentGatewayRequest,
)
from lpg.application.accounting.payment_credentials import (
    GetPaymentGatewaySettingsUseCase,
    PaymentCredentialRepository,
    PaymentGatewaySettings,
    RemovePaymentCredentialsUseCase,
    RotateWebhookTokenUseCase,
    SetPaymentCredentialsCommand,
    SetPaymentCredentialsUseCase,
    Source,
)
from lpg.application.accounting.payment_gateway import PaymentGatewayError
from lpg.application.common.errors import NotFoundError
from lpg.application.common.ports import UnitOfWork
from lpg.application.identity.ports import AuthenticatedPrincipal
from lpg.config.settings import get_settings

router = APIRouter(tags=["Online Payments"])

_PERMISSION = Depends(require_permission("tenant:configure"))


def webhook_path(token: str) -> str:
    return f"{get_settings().api_v1_prefix}/payments/razorpay/webhook/{token}"


def _to_response(settings_view: PaymentGatewaySettings) -> PaymentGatewaySettingsResponse:
    return PaymentGatewaySettingsResponse(
        configured=settings_view.configured,
        source=settings_view.source,
        key_id_masked=settings_view.key_id_masked,
        mode=settings_view.mode,
        has_key_secret=settings_view.has_key_secret,
        has_webhook_secret=settings_view.has_webhook_secret,
        webhook_path=webhook_path(settings_view.webhook_token)
        if settings_view.webhook_token
        else "",
        updated_at=settings_view.updated_at,
    )


@router.get(
    "/payment-gateway",
    response_model=PaymentGatewaySettingsResponse,
    dependencies=[_PERMISSION],
    summary="The agency's Razorpay setup (no secrets)",
)
async def get_payment_gateway_settings(
    repository: Annotated[PaymentCredentialRepository, Depends(get_payment_credential_repository)],
    fallback: Annotated[Source, Depends(get_gateway_fallback)],
) -> PaymentGatewaySettingsResponse:
    result = await GetPaymentGatewaySettingsUseCase(repository).execute(fallback=fallback)
    return _to_response(result)


@router.put(
    "/payment-gateway",
    response_model=PaymentGatewaySettingsResponse,
    summary="Save the agency's Razorpay key",
    responses={422: {"description": "Malformed key id or missing secret."}},
)
async def set_payment_gateway(
    body: SetPaymentGatewayRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("tenant:configure"))],
    repository: Annotated[PaymentCredentialRepository, Depends(get_payment_credential_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    fallback: Annotated[Source, Depends(get_gateway_fallback)],
) -> PaymentGatewaySettingsResponse:
    result = await SetPaymentCredentialsUseCase(
        repository,
        unit_of_work,
        fallback=fallback,
    ).execute(
        SetPaymentCredentialsCommand(
            tenant_id=principal.tenant_id,
            updated_by=principal.user_id,
            key_id=body.key_id,
            key_secret=body.key_secret.get_secret_value(),
            webhook_secret=body.webhook_secret.get_secret_value(),
        )
    )
    return _to_response(result)


@router.delete(
    "/payment-gateway",
    status_code=204,
    dependencies=[_PERMISSION],
    summary="Remove the agency's Razorpay key; the platform default applies again",
)
async def remove_payment_gateway(
    repository: Annotated[PaymentCredentialRepository, Depends(get_payment_credential_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> None:
    await RemovePaymentCredentialsUseCase(repository, unit_of_work).execute()


@router.post(
    "/payment-gateway/rotate-webhook-token",
    response_model=PaymentGatewaySettingsResponse,
    summary="Issue a new webhook URL (the old one stops working at once)",
)
async def rotate_payment_webhook_token(
    principal: Annotated[AuthenticatedPrincipal, Depends(require_permission("tenant:configure"))],
    repository: Annotated[PaymentCredentialRepository, Depends(get_payment_credential_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    fallback: Annotated[Source, Depends(get_gateway_fallback)],
) -> PaymentGatewaySettingsResponse:
    result = await RotateWebhookTokenUseCase(repository, unit_of_work, fallback=fallback).execute(
        updated_by=principal.user_id
    )
    return _to_response(result)


@router.post(
    "/payment-gateway/test",
    response_model=PaymentGatewayTestResponse,
    dependencies=[_PERMISSION],
    summary="Check the saved key with Razorpay",
)
async def test_payment_gateway(
    repository: Annotated[PaymentCredentialRepository, Depends(get_payment_credential_repository)],
    build_gateway: Annotated[GatewayBuilder, Depends(get_gateway_builder)],
) -> PaymentGatewayTestResponse:
    stored = await repository.get()
    if stored is None:
        msg = "Save your Razorpay key first."
        raise NotFoundError(msg)
    try:
        await build_gateway(stored).verify_credentials()
    except PaymentGatewayError:
        return PaymentGatewayTestResponse(
            ok=False,
            message="Razorpay did not accept this key. Check the key id and secret, "
            "and that both are from the same mode (test or live).",
        )
    return PaymentGatewayTestResponse(ok=True, message="Razorpay accepted this key.")
