"""`SqlAlchemyFeatureFlagRepository`/`SqlAlchemyFeatureFlagOverrideRepository`,
against a real PostgreSQL — proves the platform table has no RLS (visible
regardless of session tenant) while the override table is properly
tenant-isolated.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

from lpg.application.common.tenant import RequestTenantContext
from lpg.application.platform.feature_flag import (
    CreateFeatureFlagCommand,
    CreateFeatureFlagUseCase,
    IsFeatureFlagEnabledQuery,
    IsFeatureFlagEnabledUseCase,
    SetTenantFeatureFlagOverrideCommand,
    SetTenantFeatureFlagOverrideUseCase,
)
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.repositories.platform import SqlAlchemyFeatureFlagRepository
from lpg.infrastructure.persistence.repositories.tenant import (
    SqlAlchemyFeatureFlagOverrideRepository,
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
                    "VALUES (gen_random_uuid(), 'Flag Test Co', :slug, 'ops@example.com') "
                    "RETURNING id"
                ),
                {"slug": f"flag-test-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
    return uuid.UUID(str(tenant_id))


class TestFeatureFlagLifecycle:
    async def test_a_flag_created_by_one_tenants_session_is_visible_to_another(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_a = await _seed_tenant(admin_engine)
        tenant_b = await _seed_tenant(admin_engine)
        flag_key = f"flag-{uuid.uuid4().hex[:10]}"
        context_a = RequestTenantContext(tenant_id=tenant_a)

        async for session in database.open_session(tenant_id=tenant_a):
            async with SqlAlchemyUnitOfWork(session, context_a) as uow:
                use_case = CreateFeatureFlagUseCase(SqlAlchemyFeatureFlagRepository(uow), uow)
                await use_case.execute(
                    CreateFeatureFlagCommand(
                        key=flag_key, description="Test flag", is_enabled_by_default=True
                    )
                )

        # A completely different tenant's session still sees the flag —
        # platform.feature_flag has no RLS, unlike every tenant.* table.
        context_b = RequestTenantContext(tenant_id=tenant_b)
        async for session in database.open_session(tenant_id=tenant_b):
            flag = await SqlAlchemyFeatureFlagRepository(
                SqlAlchemyUnitOfWork(session, context_b)
            ).get(flag_key)
            assert flag is not None
            assert flag.is_enabled_by_default is True

    async def test_a_tenant_override_is_isolated_from_other_tenants(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_a = await _seed_tenant(admin_engine)
        tenant_b = await _seed_tenant(admin_engine)
        flag_key = f"flag-{uuid.uuid4().hex[:10]}"
        context_a = RequestTenantContext(tenant_id=tenant_a)

        async for session in database.open_session(tenant_id=tenant_a):
            async with SqlAlchemyUnitOfWork(session, context_a) as uow:
                create_use_case = CreateFeatureFlagUseCase(
                    SqlAlchemyFeatureFlagRepository(uow), uow
                )
                await create_use_case.execute(
                    CreateFeatureFlagCommand(
                        key=flag_key, description="Test flag", is_enabled_by_default=False
                    )
                )
        async for session in database.open_session(tenant_id=tenant_a):
            async with SqlAlchemyUnitOfWork(session, context_a) as uow:
                override_use_case = SetTenantFeatureFlagOverrideUseCase(
                    SqlAlchemyFeatureFlagOverrideRepository(uow),
                    SqlAlchemyFeatureFlagRepository(uow),
                    uow,
                )
                await override_use_case.execute(
                    SetTenantFeatureFlagOverrideCommand(
                        tenant_id=tenant_a, flag_key=flag_key, enabled=True
                    )
                )

        # Tenant A: overridden on.
        async for session in database.open_session(tenant_id=tenant_a):
            query_use_case = IsFeatureFlagEnabledUseCase(
                SqlAlchemyFeatureFlagRepository(SqlAlchemyUnitOfWork(session, context_a)),
                SqlAlchemyFeatureFlagOverrideRepository(SqlAlchemyUnitOfWork(session, context_a)),
            )
            enabled_a = await query_use_case.execute(
                IsFeatureFlagEnabledQuery(tenant_id=tenant_a, flag_key=flag_key)
            )
            assert enabled_a is True

        # Tenant B: no override, falls back to the platform default (off).
        context_b = RequestTenantContext(tenant_id=tenant_b)
        async for session in database.open_session(tenant_id=tenant_b):
            query_use_case = IsFeatureFlagEnabledUseCase(
                SqlAlchemyFeatureFlagRepository(SqlAlchemyUnitOfWork(session, context_b)),
                SqlAlchemyFeatureFlagOverrideRepository(SqlAlchemyUnitOfWork(session, context_b)),
            )
            enabled_b = await query_use_case.execute(
                IsFeatureFlagEnabledQuery(tenant_id=tenant_b, flag_key=flag_key)
            )
            assert enabled_b is False

    async def test_setting_an_override_twice_updates_it_rather_than_duplicating(
        self, database: Database, admin_engine: AsyncEngine
    ) -> None:
        tenant_id = await _seed_tenant(admin_engine)
        flag_key = f"flag-{uuid.uuid4().hex[:10]}"
        context = RequestTenantContext(tenant_id=tenant_id)

        async for session in database.open_session(tenant_id=tenant_id):
            async with SqlAlchemyUnitOfWork(session, context) as uow:
                create_use_case = CreateFeatureFlagUseCase(
                    SqlAlchemyFeatureFlagRepository(uow), uow
                )
                await create_use_case.execute(
                    CreateFeatureFlagCommand(key=flag_key, description="Test flag")
                )

        for enabled in (True, False):
            async for session in database.open_session(tenant_id=tenant_id):
                async with SqlAlchemyUnitOfWork(session, context) as uow:
                    override_use_case = SetTenantFeatureFlagOverrideUseCase(
                        SqlAlchemyFeatureFlagOverrideRepository(uow),
                        SqlAlchemyFeatureFlagRepository(uow),
                        uow,
                    )
                    await override_use_case.execute(
                        SetTenantFeatureFlagOverrideCommand(
                            tenant_id=tenant_id, flag_key=flag_key, enabled=enabled
                        )
                    )

        async for session in database.open_session(tenant_id=tenant_id):
            overrides = await SqlAlchemyFeatureFlagOverrideRepository(
                SqlAlchemyUnitOfWork(session, context)
            ).list_for_tenant(tenant_id)
            assert len(overrides) == 1
            assert overrides[0].is_enabled is False
