"""RBAC coverage for the two license permission codes — claims-based
`require_permission` allow/deny for `license:manage_tenant`, plus a
live-check test proving `license:manage_platform` re-queries the DB and
denies a non-super_admin even with a tampered claim, mirroring
`test_admin_rbac.py`'s Feature Flags section exactly.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from lpg.api.v1.dependencies.identity import require_live_permission, require_permission
from lpg.application.common.errors import PermissionDeniedError
from lpg.application.identity.authorize import PermissionChecker
from lpg.application.identity.principal import JwtAuthenticatedPrincipal
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.repositories.identity import SqlAlchemyPermissionRepository

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


@pytest.fixture
async def admin_engine_lpg_test(postgres_available: bool) -> AsyncIterator[AsyncEngine]:
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable — start it with ./scripts/dev-up.sh")
    engine = create_async_engine(
        "postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:55432/lpg_test"
    )
    try:
        yield engine
    finally:
        await engine.dispose()


class TestClaimsBasedChecks:
    async def test_denies_a_manager_without_license_manage_tenant(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="manager",
            permission_codes=frozenset({"tenant:configure"}),
        )
        dependency = require_permission("license:manage_tenant")

        with pytest.raises(PermissionDeniedError):
            await dependency(principal)

    async def test_allows_an_agency_admin_with_license_manage_tenant(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="agency_admin",
            permission_codes=frozenset({"license:manage_tenant"}),
        )
        dependency = require_permission("license:manage_tenant")

        result = await dependency(principal)

        assert result is principal


class TestLivePermissionCheckForLicenseManagePlatform:
    """Seeded in `70666eaa687b`: only `super_admin` has
    `license:manage_platform`.
    """

    async def test_denies_a_non_super_admin_even_with_a_tampered_claim(
        self, database: Database
    ) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="agency_admin",
            # Claim says agency_admin *does* have it — tampered/stale. The
            # live check must not trust this and must still deny.
            permission_codes=frozenset({"license:manage_platform"}),
        )
        checker = PermissionChecker(SqlAlchemyPermissionRepository(database))
        dependency = require_live_permission("license:manage_platform")

        with pytest.raises(PermissionDeniedError):
            await dependency(principal, checker)

    async def test_allows_a_real_super_admin(
        self, database: Database, admin_engine_lpg_test: AsyncEngine
    ) -> None:
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        email = f"{uuid.uuid4().hex}@super-admin.example"

        async with admin_engine_lpg_test.begin() as session:
            await session.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (:tenant_id, 'License Super Admin Tenant', :slug, :email)"
                ),
                {"tenant_id": tenant_id, "slug": f"TL{uuid.uuid4().hex[:6]}", "email": email},
            )
            await session.execute(
                text(
                    "INSERT INTO identity.identity_user "
                    "(id, tenant_id, email, password_hash, role) "
                    "VALUES (:user_id, :tenant_id, :email, 'hash', 'super_admin')"
                ),
                {"user_id": user_id, "tenant_id": tenant_id, "email": email},
            )
            await session.execute(
                text(
                    "INSERT INTO identity.identity_user_permission (user_id, permission_id) "
                    "SELECT :user_id, id FROM identity.permission "
                    "WHERE code = 'license:manage_platform'"
                ),
                {"user_id": user_id},
            )

        principal = JwtAuthenticatedPrincipal(
            tenant_id=tenant_id,
            user_id=user_id,
            role="super_admin",
            permission_codes=frozenset({"license:manage_platform"}),
        )
        checker = PermissionChecker(SqlAlchemyPermissionRepository(database))
        dependency = require_live_permission("license:manage_platform")

        result = await dependency(principal, checker)

        assert result is principal
