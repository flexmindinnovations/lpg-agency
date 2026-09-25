"""`fetch_omc_rates_for_tenant` against a real Postgres session — the
monthly OMC rate-proposal cron (AI Operational Intelligence, Horizon 1
Stage 3).

With `NullOmcRateSource` (the only adapter that exists today — see
`infrastructure/pricing/omc_scraper.py`'s module docstring), this proves
the job is a real, working no-op against a real tenant/cylinder catalog:
zero rates fetched, zero proposals written, no error — not a silently
broken implementation.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

    from lpg.config.settings import Settings

pytestmark = pytest.mark.integration

_ADMIN_URL = "postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:5433/lpg_test"


async def _seed_tenant_with_cylinder_type(engine: AsyncEngine) -> uuid.UUID:
    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), 'Pricing Job Smoke', :slug, 'ops@example.com') "
                    "RETURNING id"
                ),
                {"slug": f"pricing-job-smoke-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO tenant.cylinder_type (id, tenant_id, name, weight_kg) "
                "VALUES (gen_random_uuid(), :t, '14.2kg Domestic', 14.2)"
            ),
            {"t": str(tenant_id)},
        )
    return uuid.UUID(str(tenant_id))


async def _run_for_tenant(integration_settings: Settings, tenant_id: uuid.UUID) -> int:
    from datetime import date

    from lpg.application.common.tenant import RequestTenantContext
    from lpg.infrastructure.jobs.pricing_jobs import fetch_omc_rates_for_tenant
    from lpg.infrastructure.persistence.database import build_database
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
    from lpg.infrastructure.pricing.omc_scraper import NullOmcRateSource

    database = build_database(integration_settings)
    database.connect()
    try:
        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(
                session, RequestTenantContext(tenant_id=tenant_id)
            ) as uow:
                return await fetch_omc_rates_for_tenant(
                    uow,
                    NullOmcRateSource(),
                    tenant_id=tenant_id,
                    city="Mumbai",
                    omc="IOCL",
                    effective_from=date(2026, 10, 1),
                )
        return 0
    finally:
        await database.disconnect()


async def test_fetch_omc_rates_for_tenant_is_a_real_no_op(
    integration_settings: Settings, postgres_available: bool
) -> None:
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable")

    engine = create_async_engine(_ADMIN_URL)
    try:
        tenant_id = await _seed_tenant_with_cylinder_type(engine)

        written = await _run_for_tenant(integration_settings, tenant_id)
        assert written == 0

        async with engine.begin() as conn:
            count = (
                await conn.execute(
                    text("SELECT count(*) FROM tenant.price_list_proposal WHERE tenant_id = :t"),
                    {"t": str(tenant_id)},
                )
            ).scalar_one()
        assert count == 0

        async with engine.begin() as conn:
            for stmt in (
                "DELETE FROM tenant.cylinder_type WHERE tenant_id = :t",
                "DELETE FROM tenant.tenant WHERE id = :t",
            ):
                await conn.execute(text(stmt), {"t": str(tenant_id)})
    finally:
        await engine.dispose()
