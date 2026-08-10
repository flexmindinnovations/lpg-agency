"""`SqlAlchemyTenantConfigurationRepository`, against a real PostgreSQL."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from lpg.application.common.tenant import RequestTenantContext
from lpg.application.tenant.tenant_configuration import (
    GetEffectiveTenantConfigurationQuery,
    GetEffectiveTenantConfigurationUseCase,
    SetTenantConfigurationCommand,
    SetTenantConfigurationUseCase,
)
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.repositories.tenant import (
    SqlAlchemyTenantConfigurationRepository,
)
from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncEngine

    from lpg.config.settings import Settings

pytestmark = pytest.mark.integration


@pytest.fixture
async def database(
    integration_settings: Settings, postgres_available: bool
) -> AsyncIterator[Database]:
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable — start it with ./scripts/dev-up.sh")
    db = Database(integration_settings)
    db.connect()
    try:
        yield db
    finally:
        await db.disconnect()


async def _seed_tenant(admin_engine: AsyncEngine) -> uuid.UUID:
    async with admin_engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), 'Config Test Co', :slug, 'ops@example.com') "
                    "RETURNING id"
                ),
                {"slug": f"config-test-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
    return uuid.UUID(str(tenant_id))


class TestSetAndResolve:
    async def test_the_most_recent_effective_entry_wins(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        context = RequestTenantContext(tenant_id=tenant_id)
        now = datetime.now(UTC)

        # A `SqlAlchemyUnitOfWork` is scoped to one command — `commit()` is
        # idempotent-after-first-call by design (its own docstring), so each
        # `SetTenantConfigurationCommand` here needs its own UoW, exactly
        # like two separate API requests would each get their own via
        # `get_unit_of_work`.
        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                use_case = SetTenantConfigurationUseCase(
                    SqlAlchemyTenantConfigurationRepository(uow), uow
                )
                await use_case.execute(
                    SetTenantConfigurationCommand(
                        tenant_id=tenant_id,
                        config_key="gst_rate_percent",
                        config_value="5.0",
                        effective_from=now - timedelta(days=30),
                    )
                )
        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                use_case = SetTenantConfigurationUseCase(
                    SqlAlchemyTenantConfigurationRepository(uow), uow
                )
                await use_case.execute(
                    SetTenantConfigurationCommand(
                        tenant_id=tenant_id,
                        config_key="gst_rate_percent",
                        config_value="12.0",
                        effective_from=now - timedelta(days=1),
                    )
                )

        async for session in database.open_session(tenant_id=tenant_id):
            query_use_case = GetEffectiveTenantConfigurationUseCase(
                SqlAlchemyTenantConfigurationRepository(SqlAlchemyUnitOfWork(session, context))
            )
            effective = await query_use_case.execute(
                GetEffectiveTenantConfigurationQuery(
                    tenant_id=tenant_id, config_key="gst_rate_percent", at=now
                )
            )
            assert effective is not None
            assert effective.config_value == "12.0"

    async def test_a_query_at_a_past_point_in_time_sees_the_value_from_back_then(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        context = RequestTenantContext(tenant_id=tenant_id)
        old_effective = datetime(2026, 1, 1, tzinfo=UTC)
        new_effective = datetime(2026, 6, 1, tzinfo=UTC)
        query_time = datetime(2026, 3, 1, tzinfo=UTC)

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                use_case = SetTenantConfigurationUseCase(
                    SqlAlchemyTenantConfigurationRepository(uow), uow
                )
                await use_case.execute(
                    SetTenantConfigurationCommand(
                        tenant_id=tenant_id,
                        config_key="gst_rate_percent",
                        config_value="5.0",
                        effective_from=old_effective,
                    )
                )
        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                use_case = SetTenantConfigurationUseCase(
                    SqlAlchemyTenantConfigurationRepository(uow), uow
                )
                await use_case.execute(
                    SetTenantConfigurationCommand(
                        tenant_id=tenant_id,
                        config_key="gst_rate_percent",
                        config_value="12.0",
                        effective_from=new_effective,
                    )
                )

        async for session in database.open_session(tenant_id=tenant_id):
            query_use_case = GetEffectiveTenantConfigurationUseCase(
                SqlAlchemyTenantConfigurationRepository(SqlAlchemyUnitOfWork(session, context))
            )
            effective = await query_use_case.execute(
                GetEffectiveTenantConfigurationQuery(
                    tenant_id=tenant_id, config_key="gst_rate_percent", at=query_time
                )
            )
            assert effective is not None
            assert effective.config_value == "5.0"

    async def test_cannot_see_another_tenants_configuration(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        own_tenant = await _seed_tenant(admin_engine)
        other_tenant = await _seed_tenant(admin_engine)
        other_context = RequestTenantContext(tenant_id=other_tenant)

        async for session in database.open_session(tenant_id=other_tenant):
            async with SqlAlchemyUnitOfWork(session, other_context) as uow:
                use_case = SetTenantConfigurationUseCase(
                    SqlAlchemyTenantConfigurationRepository(uow), uow
                )
                await use_case.execute(
                    SetTenantConfigurationCommand(
                        tenant_id=other_tenant,
                        config_key="gst_rate_percent",
                        config_value="99.0",
                    )
                )

        own_context = RequestTenantContext(tenant_id=own_tenant)
        async for session in database.open_session(tenant_id=own_tenant):
            entries = await SqlAlchemyTenantConfigurationRepository(
                SqlAlchemyUnitOfWork(session, own_context)
            ).list_for_tenant(own_tenant)
            assert entries == []
