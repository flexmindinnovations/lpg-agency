"""`PaymentLinkPort` adapters for the WhatsApp assistant (ADR-054).

`GatewayPaymentLinks` hands the request to `CreateOrderPaymentLinkUseCase`
(ADR-053), the one entry point the Customer App and staff use too, so the
amount due, link reuse and the payment webhook all work the same way for a
link sent over WhatsApp. `UnconfiguredPaymentLinks` stands in when no
payment gateway is configured.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lpg.application.accounting.online_payments import (
    CreateOrderPaymentLinkCommand,
    CreateOrderPaymentLinkUseCase,
    OrderPaymentScope,
)
from lpg.application.common.errors import ServiceUnavailableError
from lpg.application.whatsapp.ports import PaymentLink
from lpg.config.logging import get_logger
from lpg.infrastructure.persistence.repositories.accounting import (
    SqlAlchemyInvoiceRepository,
    SqlAlchemyOnlinePaymentRepository,
)

if TYPE_CHECKING:
    import uuid
    from collections.abc import Callable
    from contextlib import AbstractAsyncContextManager
    from datetime import timedelta

    from lpg.application.accounting.payment_gateway import PaymentGateway
    from lpg.application.whatsapp.ports import PaymentLinkRequest, WhatsAppScope
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

_logger = get_logger(__name__)


class UnconfiguredPaymentLinks:
    async def create_payment_link(self, request: PaymentLinkRequest) -> PaymentLink | None:  # noqa: ARG002
        return None


class GatewayPaymentLinks:
    def __init__(
        self,
        *,
        tenant_id: uuid.UUID,
        gateway: PaymentGateway,
        scope_factory: Callable[[], AbstractAsyncContextManager[WhatsAppScope]],
        link_ttl: timedelta,
    ) -> None:
        self._tenant_id = tenant_id
        self._gateway = gateway
        self._scope_factory = scope_factory
        self._link_ttl = link_ttl

    async def create_payment_link(self, request: PaymentLinkRequest) -> PaymentLink | None:
        async with self._scope_factory() as scope:
            # `build_scope_factory` always binds a `SqlAlchemyUnitOfWork`.
            uow: SqlAlchemyUnitOfWork = scope.unit_of_work  # type: ignore[assignment]
            use_case = CreateOrderPaymentLinkUseCase(
                order_repository=scope.orders,
                invoice_repository=SqlAlchemyInvoiceRepository(uow),
                online_payment_repository=SqlAlchemyOnlinePaymentRepository(uow),
                customer_repository=scope.customers,
                tenant_config_repository=scope.tenant_configuration,
                gateway=self._gateway,
                unit_of_work=uow,
                link_ttl=self._link_ttl,
            )
            try:
                payment = await use_case.execute(
                    CreateOrderPaymentLinkCommand(
                        tenant_id=self._tenant_id,
                        order_id=request.order_id,
                        requested_by=request.requested_by,
                        scope=OrderPaymentScope(customer_id=request.customer_id),
                    )
                )
            except ServiceUnavailableError as exc:
                _logger.warning(
                    "whatsapp_payment_link_unavailable",
                    order_id=str(request.order_id),
                    error=str(exc),
                )
                return None
        return PaymentLink(url=payment.short_url, amount=payment.amount)
