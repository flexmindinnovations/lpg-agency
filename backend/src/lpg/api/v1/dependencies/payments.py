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
from lpg.application.accounting.payment_gateway import PaymentGateway
from lpg.application.accounting.payment_verification import IfscDirectory
from lpg.application.accounting.ports import OnlinePaymentRepository
from lpg.application.common.ports import UnitOfWork

if typing.TYPE_CHECKING:
    import uuid


def get_payment_gateway() -> PaymentGateway:
    from lpg.config.settings import get_settings
    from lpg.infrastructure.payments.factory import get_payment_gateway as build_gateway

    return build_gateway(get_settings())


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
