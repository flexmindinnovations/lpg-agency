"""Compliance-document expiry check — nightly cron (Part E, driver/vehicle
compliance pack: docs/research/feature-gap-analysis.md D24 ·
planning/features/20-regulatory-compliance).

Iterates every tenant, resolves that tenant's configured lead time (default
``DEFAULT_LEAD_DAYS``) via `TenantConfiguration` key
``compliance_expiry_lead_days``, and enqueues one
``compliance_document_expiring_staff`` notification per document
``ComplianceDocumentRepository.list_expiring()`` returns. That repository
method itself excludes documents already notified within the same lead-time
window (``last_expiry_notified_at``), so a re-run (retry, or two nights in a
row before staff act) never double-notifies — this job additionally marks
each document notified before moving to the next, the same
read-then-mark-then-commit shape `SqlAlchemyComplianceDocumentRepository`'s
other mutators use.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import structlog

from lpg.config.logging import get_logger

if TYPE_CHECKING:
    from lpg.infrastructure.jobs.pool import JobQueue
    from lpg.infrastructure.persistence.database import Database

_logger = get_logger(__name__)

#: Lead time applied when a tenant has no `compliance_expiry_lead_days`
#: configuration entry of its own.
DEFAULT_LEAD_DAYS = 30

#: Placeholder tenant id for the one cross-tenant, RLS-bypassing read this
#: job does (`SqlAlchemyTenantRepository.list_all`) — `RequestTenantContext.
#: tenant_id` isn't nullable, and this mirrors the same nil-UUID convention
#: `PLATFORM_AUDIT_TENANT_ID` uses in `api/v1/dependencies/platform.py` for
#: the identical "genuinely cross-tenant, no real tenant to attribute it to"
#: situation, without this infrastructure module reaching into the API layer
#: to import it.
_CROSS_TENANT_PLACEHOLDER_ID = uuid.UUID(int=0)


async def check_compliance_expiry(ctx: dict[str, Any]) -> None:
    """Cron job: flags every driver/vehicle compliance document expiring
    within its tenant's configured lead time and enqueues a
    `compliance_document_expiring_staff` notification for each."""
    structlog.contextvars.bind_contextvars(
        correlation_id=str(uuid.uuid4()), job_name="check_compliance_expiry"
    )
    database: Database = ctx["database"]
    job_queue: JobQueue = ctx["job_queue"]

    _logger.info("job_check_compliance_expiry_started")

    from lpg.application.common.tenant import RequestTenantContext
    from lpg.application.tenant.tenant_configuration import (
        GetEffectiveTenantConfigurationQuery,
        GetEffectiveTenantConfigurationUseCase,
    )
    from lpg.infrastructure.persistence.repositories.compliance_document import (
        SqlAlchemyComplianceDocumentRepository,
    )
    from lpg.infrastructure.persistence.repositories.tenant import (
        SqlAlchemyTenantConfigurationRepository,
        SqlAlchemyTenantRepository,
    )
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

    async for session in database.open_session(tenant_id=None):
        cross_tenant_context = RequestTenantContext(tenant_id=_CROSS_TENANT_PLACEHOLDER_ID)
        async with SqlAlchemyUnitOfWork(session, cross_tenant_context) as uow:
            tenants = await SqlAlchemyTenantRepository(uow).list_all()

    documents_notified = 0
    for tenant in tenants:
        if tenant.status == "closed":
            continue

        structlog.contextvars.bind_contextvars(tenant_id=str(tenant.id))
        async for session in database.open_session(tenant_id=tenant.id):
            tenant_context = RequestTenantContext(tenant_id=tenant.id)
            async with SqlAlchemyUnitOfWork(session, tenant_context) as uow:
                config_repo = SqlAlchemyTenantConfigurationRepository(uow)
                lead_days = DEFAULT_LEAD_DAYS
                config = await GetEffectiveTenantConfigurationUseCase(config_repo).execute(
                    GetEffectiveTenantConfigurationQuery(
                        tenant_id=tenant.id, config_key="compliance_expiry_lead_days"
                    )
                )
                if config is not None:
                    try:
                        lead_days = int(config.config_value)
                    except (TypeError, ValueError):
                        _logger.warning(
                            "compliance_expiry_lead_days_invalid", value=config.config_value
                        )

                doc_repository = SqlAlchemyComplianceDocumentRepository(uow)
                expiring = await doc_repository.list_expiring(within_days=lead_days)

                for doc in expiring:
                    await job_queue.enqueue(
                        "send_notification",
                        {
                            "type": "compliance_document_expiring_staff",
                            "tenant_id": str(tenant.id),
                            "document_id": str(doc.id),
                            "owner_type": doc.owner_type,
                            "owner_id": str(doc.owner_id),
                            "doc_type": doc.doc_type,
                            "expiry_date": doc.expiry_date.isoformat() if doc.expiry_date else "",
                        },
                        # Deterministic id — ARQ's own dedupe primitive
                        # (`JobQueue.enqueue`'s docstring) — a retried or
                        # overlapping cron run enqueues the same notification
                        # job at most once per document per day.
                        _job_id=f"compliance_expiry_{doc.id}",
                    )
                    await doc_repository.mark_expiry_notified(doc.id)
                    documents_notified += 1

    _logger.info("job_check_compliance_expiry_completed", documents_notified=documents_notified)
