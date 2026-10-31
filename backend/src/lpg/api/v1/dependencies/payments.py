"""Dependencies for online payments (ADR-053).

Wires the payment gateway adapter and the `OnlinePayment` repository, plus
the webhook's own Unit of Work: a gateway webhook carries no JWT, so its
tenant comes from the signature-verified event itself and the session has
to be opened for that tenant here rather than through `get_unit_of_work`.
"""

from __future__ import annotations

import typing
from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.application.accounting.online_payments import HandlePaymentWebhookUseCase
from lpg.application.accounting.payment_credentials import (
    PaymentCredentialRepository,
    Source,
    StoredPaymentCredentials,
    WebhookTenantResolver,
)
from lpg.application.accounting.payment_gateway import PaymentGateway
from lpg.application.accounting.payment_verification import IfscDirectory
from lpg.application.accounting.ports import OnlinePaymentRepository
from lpg.application.common.ports import UnitOfWork
from lpg.application.customer.ports import FieldEncryptor

if typing.TYPE_CHECKING:
    import uuid


def get_field_encryptor() -> FieldEncryptor:
    from lpg.config.settings import get_settings
    from lpg.infrastructure.security.field_encryption import FernetFieldEncryptor

    return FernetFieldEncryptor(get_settings())


def get_payment_credential_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    encryptor: Annotated[FieldEncryptor, Depends(get_field_encryptor)],
) -> PaymentCredentialRepository:
    from lpg.infrastructure.persistence.repositories.accounting import (
        SqlAlchemyPaymentCredentialRepository,
    )
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

    return SqlAlchemyPaymentCredentialRepository(
        typing.cast("SqlAlchemyUnitOfWork", unit_of_work), encryptor
    )


async def get_payment_gateway(
    repository: Annotated[PaymentCredentialRepository, Depends(get_payment_credential_repository)],
) -> PaymentGateway:
    """The signed-in agency's own Razorpay account if it saved a key, else the
    platform default (ADR-067).
    """
    from lpg.config.settings import get_settings
    from lpg.infrastructure.payments.credentials import resolve_payment_gateway

    return await resolve_payment_gateway(get_settings(), repository)


@lru_cache(maxsize=1)
def get_ifsc_directory() -> IfscDirectory:
    """One directory per process, so its answer cache is shared by requests."""
    from lpg.infrastructure.payments.ifsc_directory import RazorpayIfscDirectory

    return RazorpayIfscDirectory()


def get_online_payment_repository(
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> OnlinePaymentRepository:
    from lpg.infrastructure.persistence.repositories.accounting import (
        SqlAlchemyOnlinePaymentRepository,
    )
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

    return SqlAlchemyOnlinePaymentRepository(typing.cast("SqlAlchemyUnitOfWork", unit_of_work))


WebhookUseCaseFactory = Callable[
    ["uuid.UUID"], AbstractAsyncContextManager[HandlePaymentWebhookUseCase]
]


def get_payment_webhook_use_case_factory() -> WebhookUseCaseFactory:
    """Mint a `HandlePaymentWebhookUseCase` bound to a fresh Unit of Work
    scoped to the given tenant — RLS then confines the webhook to rows of
    the tenant its own event names.
    """
    from lpg.api.app import get_app_state
    from lpg.application.common.tenant import RequestTenantContext
    from lpg.infrastructure.persistence.repositories.accounting import (
        SqlAlchemyInvoiceRepository,
        SqlAlchemyOnlinePaymentRepository,
    )
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

    state = get_app_state()
    database = state.database
    if database is None:
        msg = "Database is not connected — the application lifespan has not run."
        raise RuntimeError(msg)

    @asynccontextmanager
    async def _factory(tenant_id: uuid.UUID) -> AsyncGenerator[HandlePaymentWebhookUseCase]:
        tenant_context = RequestTenantContext(tenant_id=tenant_id)
        async for session in database.open_session(tenant_id=tenant_id):
            uow = SqlAlchemyUnitOfWork(
                session, tenant_context, event_dispatcher=state.event_dispatcher
            )
            async with uow:
                yield HandlePaymentWebhookUseCase(
                    invoice_repository=SqlAlchemyInvoiceRepository(uow),
                    online_payment_repository=SqlAlchemyOnlinePaymentRepository(uow),
                    unit_of_work=uow,
                )

    return _factory


CredentialScopeFactory = Callable[
    ["uuid.UUID"], AbstractAsyncContextManager[PaymentCredentialRepository]
]


def get_payment_credential_scope_factory() -> CredentialScopeFactory:
    """Mint a credential repository bound to a fresh read session for a
    tenant the webhook URL named — RLS confines it to that tenant's row.
    """
    from lpg.api.app import get_app_state
    from lpg.application.common.tenant import RequestTenantContext
    from lpg.infrastructure.persistence.repositories.accounting import (
        SqlAlchemyPaymentCredentialRepository,
    )
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

    state = get_app_state()
    database = state.database
    if database is None:
        msg = "Database is not connected — the application lifespan has not run."
        raise RuntimeError(msg)

    @asynccontextmanager
    async def _factory(tenant_id: uuid.UUID) -> AsyncGenerator[PaymentCredentialRepository]:
        tenant_context = RequestTenantContext(tenant_id=tenant_id)
        async for session in database.open_session(tenant_id=tenant_id):
            uow = SqlAlchemyUnitOfWork(
                session, tenant_context, event_dispatcher=state.event_dispatcher
            )
            async with uow:
                yield SqlAlchemyPaymentCredentialRepository(uow, get_field_encryptor())

    return _factory


def get_payment_webhook_tenant_resolver() -> WebhookTenantResolver:
    from lpg.api.app import get_app_state
    from lpg.infrastructure.payments.tenant_resolver import PaymentCredentialTenantResolver

    database = get_app_state().database
    if database is None:
        msg = "Database is not connected — the application lifespan has not run."
        raise RuntimeError(msg)
    return PaymentCredentialTenantResolver(database)


GatewayBuilder = Callable[[StoredPaymentCredentials], PaymentGateway]


def get_gateway_builder() -> GatewayBuilder:
    """Builds a Razorpay gateway from one agency's decrypted credentials."""
    from lpg.config.settings import get_settings
    from lpg.infrastructure.payments.credentials import gateway_from_credentials

    settings = get_settings()
    return lambda credentials: gateway_from_credentials(settings, credentials)


def get_platform_gateway() -> PaymentGateway:
    """The platform-wide default account (`LPG_RAZORPAY_*`), no agency key."""
    from lpg.config.settings import get_settings
    from lpg.infrastructure.payments.factory import get_payment_gateway as build_gateway

    return build_gateway(get_settings())


def get_gateway_fallback() -> Source:
    """What an agency without its own key gets, for the Settings page."""
    from lpg.config.settings import get_settings
    from lpg.infrastructure.payments.credentials import platform_fallback

    return platform_fallback(get_settings())
