"""`handle_whatsapp_message` — answers one inbound WhatsApp message (ADR-055).

Enqueued by `POST /webhooks/whatsapp` once per customer message, so the
webhook can acknowledge Meta immediately (Meta retries slow or failed
deliveries) while the model call runs here.

Satisfies the worker contract in `worker.py`:

- **Tenant-scoped**: the tenant is resolved from the receiving business
  number before anything else, and every session is opened for that tenant.
- **Idempotent**: the message is recorded under Meta's message id first; a
  repeat (Meta's retry, or ARQ's) is detected there and answered nothing.
  The enqueue also uses that id as the ARQ job id.
- **Observable**: a correlation id per run, bound before any work.
- **Retry-safe**: a failure before the message is recorded (database or
  Redis briefly down) is retried and answered normally; a failure after it is
  recorded makes the retry stop at the duplicate check. A retry can lose a
  reply but never send one twice.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import structlog

from lpg.application.common.tenant import RequestTenantContext
from lpg.application.whatsapp.ports import InboundWhatsAppMessage
from lpg.application.whatsapp.use_cases import HandleInboundWhatsAppMessageUseCase
from lpg.config.logging import get_logger
from lpg.config.settings import get_settings
from lpg.infrastructure.ai.factory import get_model_gateway
from lpg.infrastructure.payments.credentials import resolve_payment_gateway
from lpg.infrastructure.payments.factory import get_payment_gateway
from lpg.infrastructure.persistence.repositories.accounting import (
    SqlAlchemyPaymentCredentialRepository,
)
from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from lpg.infrastructure.security.field_encryption import FernetFieldEncryptor
from lpg.infrastructure.whatsapp.payment_links import (
    GatewayPaymentLinks,
    UnconfiguredPaymentLinks,
)
from lpg.infrastructure.whatsapp.scope import build_scope_factory
from lpg.infrastructure.whatsapp.tenant_resolver import SqlAlchemyWhatsAppTenantResolver
from lpg.infrastructure.whatsapp.webhook import HANDLE_MESSAGE_JOB

if TYPE_CHECKING:
    from lpg.application.accounting.payment_gateway import PaymentGateway
    from lpg.application.customer.ports import FieldEncryptor
    from lpg.application.whatsapp.ports import PaymentLinkPort
    from lpg.application.whatsapp.tools import WhatsAppScopeFactory
    from lpg.config.settings import Settings
    from lpg.infrastructure.persistence.database import Database

_logger = get_logger(__name__)


async def _resolve_tenant_gateway(
    database: Database,
    tenant_id: uuid.UUID,
    field_encryptor: FieldEncryptor,
    settings: Settings,
) -> PaymentGateway:
    """The agency's own Razorpay account if it saved a key, else the platform
    default (ADR-067)."""
    tenant_context = RequestTenantContext(tenant_id=tenant_id)
    async for session in database.open_session(tenant_id=tenant_id):
        async with SqlAlchemyUnitOfWork(session, tenant_context) as uow:
            return await resolve_payment_gateway(
                settings,
                SqlAlchemyPaymentCredentialRepository(uow, field_encryptor),
                fallback=get_payment_gateway,
            )
    msg = "Unreachable"
    raise RuntimeError(msg)


async def handle_whatsapp_message(ctx: dict[str, Any], message: dict[str, Any]) -> str:
    inbound = InboundWhatsAppMessage(
        phone_number_id=str(message["phone_number_id"]),
        wa_message_id=str(message["wa_message_id"]),
        from_phone=str(message["from_phone"]),
        profile_name=message.get("profile_name"),
        text=str(message["text"]),
    )
    structlog.contextvars.bind_contextvars(
        correlation_id=str(uuid.uuid4()),
        job_name=HANDLE_MESSAGE_JOB,
        wa_message_id=inbound.wa_message_id,
    )
    database: Database = ctx["database"]

    tenant_id = await SqlAlchemyWhatsAppTenantResolver(database).resolve(inbound.phone_number_id)
    if tenant_id is None:
        _logger.warning(
            "whatsapp_unmapped_phone_number_id", phone_number_id=inbound.phone_number_id
        )
        return "unmapped_number"
    structlog.contextvars.bind_contextvars(tenant_id=str(tenant_id))

    settings = get_settings()
    field_encryptor = FernetFieldEncryptor(settings)
    event_dispatcher = ctx.get("event_dispatcher")

    def scope_factories(actor_id: uuid.UUID | None) -> WhatsAppScopeFactory:
        return build_scope_factory(
            database=database,
            tenant_id=tenant_id,
            field_encryptor=field_encryptor,
            event_dispatcher=event_dispatcher,
            actor_id=actor_id,
        )

    payment_gateway = await _resolve_tenant_gateway(database, tenant_id, field_encryptor, settings)
    payment_links: PaymentLinkPort = (
        GatewayPaymentLinks(
            tenant_id=tenant_id,
            gateway=payment_gateway,
            scope_factory=scope_factories(None),
            link_ttl=timedelta(minutes=settings.payment_link_ttl_minutes),
        )
        if payment_gateway.is_configured
        else UnconfiguredPaymentLinks()
    )

    use_case = HandleInboundWhatsAppMessageUseCase(
        tenant_id=tenant_id,
        gateway=get_model_gateway(settings),
        sender=ctx["whatsapp_sender"],
        scope_factories=scope_factories,
        payment_links=payment_links,
    )
    result = await use_case.execute(inbound)
    _logger.info("job_handle_whatsapp_message_completed", outcome=result.outcome)
    return result.outcome
