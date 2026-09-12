"""`fetch_omc_rates` — monthly OMC rate-proposal cron (AI Operational
Intelligence, Horizon 1 Stage 3).

Per tenant that has opted into `omc_rate_ingestion_enabled` and configured
`omc_provider`/`omc_city`: fetches rates via the configured
`OmcRateSourcePort` (see `infrastructure/pricing/omc_scraper.py`'s module
docstring for why that's `NullOmcRateSource` — always zero rates — today),
maps each rate onto the tenant's own `cylinder_type` catalog by nearest
weight match, and inserts a `tenant.price_list_proposal` row per match
with `effective_from` = the 1st of next month. `ON CONFLICT DO NOTHING` on
the same historization dimension `tenant.price_list` itself uses makes a
re-run of this job for the same month a harmless no-op. One
`lpg_rate_review_staff` notification per tenant that got at least one new
proposal.

Cross-tenant iteration + per-tenant `RequestTenantContext` follows
`stale_order_jobs.py` / `feature_store_jobs.py` exactly.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

from lpg.application.common.config import is_truthy_config_value
from lpg.application.common.tenant import RequestTenantContext
from lpg.application.tenant.tenant_configuration import (
    GetEffectiveTenantConfigurationQuery,
    GetEffectiveTenantConfigurationUseCase,
)
from lpg.config.logging import get_logger
from lpg.config.settings import get_settings
from lpg.domain.tenant.price_list_proposal import PriceListProposal
from lpg.infrastructure.persistence.repositories.tenant import (
    SqlAlchemyCylinderTypeRepository,
    SqlAlchemyPriceListProposalRepository,
    SqlAlchemyTenantConfigurationRepository,
    SqlAlchemyTenantRepository,
)
from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from lpg.infrastructure.pricing.factory import get_omc_rate_source

if TYPE_CHECKING:
    from datetime import date

    from lpg.application.pricing.ports import OmcRate, OmcRateSourcePort
    from lpg.application.tenant.ports import TenantConfigurationRepository
    from lpg.domain.tenant.cylinder_type import CylinderType
    from lpg.infrastructure.jobs.pool import JobQueue
    from lpg.infrastructure.persistence.database import Database

_logger = get_logger(__name__)

#: Same cross-tenant, RLS-bypassing-read placeholder every other
#: all-tenant cron in this codebase duplicates rather than imports.
_CROSS_TENANT_PLACEHOLDER_ID = uuid.UUID(int=0)

#: An OMC's published weight and a tenant's own `cylinder_type.weight_kg`
#: can differ by rounding (14.2 vs 14.20, or a slightly different nominal
#: figure) — match within this tolerance, nearest wins.
_WEIGHT_MATCH_TOLERANCE_KG = 0.5


def _first_of_next_month(today: date) -> date:
    if today.month == 12:
        return today.replace(year=today.year + 1, month=1, day=1)
    return today.replace(month=today.month + 1, day=1)


def _match_cylinder_type(
    rate: OmcRate, cylinder_types: list[CylinderType]
) -> CylinderType | None:
    """The tenant's own cylinder type nearest `rate.weight_kg`, within
    `_WEIGHT_MATCH_TOLERANCE_KG`. `None` when the tenant doesn't stock
    anything near this weight — never guesses, skips the rate instead."""
    candidates = [
        ct
        for ct in cylinder_types
        if abs(float(ct.weight_kg) - float(rate.weight_kg)) <= _WEIGHT_MATCH_TOLERANCE_KG
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda ct: abs(float(ct.weight_kg) - float(rate.weight_kg)))


async def fetch_omc_rates_for_tenant(
    uow: SqlAlchemyUnitOfWork,
    rate_source: OmcRateSourcePort,
    *,
    tenant_id: uuid.UUID,
    city: str,
    omc: str,
    effective_from: date,
) -> int:
    """Fetches this tenant's configured OMC/city, maps each rate onto its
    own cylinder catalog, and inserts one `price_list_proposal` row per
    match. Split out from the cron loop so it's testable against a single
    seeded tenant — the same reason `feature_store_jobs.
    build_customer_refill_snapshots_for_tenant` and `refill_jobs.
    predict_refill_due_for_tenant` are. `uow` must already be
    tenant-scoped (RLS) for `tenant_id`. Returns the number of proposals
    actually inserted."""
    cylinder_repo = SqlAlchemyCylinderTypeRepository(uow)
    proposal_repo = SqlAlchemyPriceListProposalRepository(uow)

    cylinder_types = list(await cylinder_repo.list_for_tenant(tenant_id))
    rates = await rate_source.fetch_rates(city=city, omc=omc)
    effective_from_dt = datetime(
        effective_from.year, effective_from.month, effective_from.day, tzinfo=UTC
    )

    proposals: list[PriceListProposal] = []
    for rate in rates:
        cylinder_type = _match_cylinder_type(rate, cylinder_types)
        if cylinder_type is None:
            continue
        proposals.append(
            PriceListProposal(
                proposal_repo.next_id(),
                tenant_id,
                cylinder_type.id,
                rate.customer_type,
                rate.price,
                effective_from_dt,
                rate.source_url,
                rate.fetched_at,
            )
        )

    written = await proposal_repo.add_ignoring_conflicts(proposals)
    _logger.info(
        "price_list_proposals_written",
        city=city,
        omc=omc,
        rates_fetched=len(rates),
        matched=len(proposals),
        inserted=written,
    )
    return written


async def fetch_omc_rates(ctx: dict[str, Any]) -> None:
    """Cron job: proposes next month's rates for every tenant that has
    opted in and configured a provider/city."""
    structlog.contextvars.bind_contextvars(
        correlation_id=str(uuid.uuid4()), job_name="fetch_omc_rates"
    )
    database: Database = ctx["database"]
    job_queue: JobQueue = ctx["job_queue"]
    rate_source = get_omc_rate_source(get_settings())
    effective_from = _first_of_next_month(datetime.now(UTC).date())

    _logger.info("job_fetch_omc_rates_started", effective_from=effective_from.isoformat())

    async for session in database.open_session(tenant_id=None):
        cross_tenant_context = RequestTenantContext(tenant_id=_CROSS_TENANT_PLACEHOLDER_ID)
        async with SqlAlchemyUnitOfWork(session, cross_tenant_context) as uow:
            tenants = await SqlAlchemyTenantRepository(uow).list_all()

    total_written = 0
    for tenant in tenants:
        if tenant.status == "closed":
            continue
        structlog.contextvars.bind_contextvars(tenant_id=str(tenant.id))
        async for session in database.open_session(tenant_id=tenant.id):
            tenant_context = RequestTenantContext(tenant_id=tenant.id)
            async with SqlAlchemyUnitOfWork(session, tenant_context) as uow:
                config_repo = SqlAlchemyTenantConfigurationRepository(uow)
                enabled = await _is_enabled(config_repo, tenant.id, "omc_rate_ingestion_enabled")
                if not enabled:
                    continue

                city = await _get_str_config(config_repo, tenant.id, "omc_city")
                omc = await _get_str_config(config_repo, tenant.id, "omc_provider")
                if not city or not omc:
                    _logger.info("omc_rate_ingestion_not_configured", tenant_id=str(tenant.id))
                    continue

                written = await fetch_omc_rates_for_tenant(
                    uow,
                    rate_source,
                    tenant_id=tenant.id,
                    city=city,
                    omc=omc,
                    effective_from=effective_from,
                )
                total_written += written

                if written > 0:
                    await job_queue.enqueue(
                        "send_notification",
                        {
                            "type": "lpg_rate_review_staff",
                            "tenant_id": str(tenant.id),
                            "proposal_count": str(written),
                        },
                        # ARQ's own dedupe primitive against overlapping
                        # runs for the same tenant + month.
                        _job_id=f"lpg_rate_review_{tenant.id}_{effective_from.isoformat()}",
                    )

    _logger.info(
        "job_fetch_omc_rates_completed",
        effective_from=effective_from.isoformat(),
        total_written=total_written,
    )


async def _is_enabled(
    config_repo: TenantConfigurationRepository, tenant_id: uuid.UUID, key: str
) -> bool:
    config = await GetEffectiveTenantConfigurationUseCase(config_repo).execute(
        GetEffectiveTenantConfigurationQuery(tenant_id=tenant_id, config_key=key)
    )
    return config is not None and is_truthy_config_value(config.config_value)


async def _get_str_config(
    config_repo: TenantConfigurationRepository, tenant_id: uuid.UUID, key: str
) -> str | None:
    config = await GetEffectiveTenantConfigurationUseCase(config_repo).execute(
        GetEffectiveTenantConfigurationQuery(tenant_id=tenant_id, config_key=key)
    )
    if config is None or config.config_value is None:
        return None
    return str(config.config_value)
