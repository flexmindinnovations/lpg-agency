"""RBAC coverage for Phase 7's admin permission codes — claims-based
`require_permission` allow/deny, plus a live-check test proving
`feature_flags:manage_platform` re-queries the DB and denies a non-super_admin
even with a tampered claim, mirroring `test_auth_flows.py`'s
`TestPermissionCheckerLiveRecheck`.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
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
    """Missing from this file until now — `test_allows_a_real_super_admin`
    referenced it without ever defining it, so the test errored on
    collection rather than running. Copied verbatim from
    `test_admin_endpoints_smoke.py`, which every other file needing a
    superuser-privileged connection duplicates the same way.
    """
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
    async def test_denies_a_driver_without_tenant_configure(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="driver",
            permission_codes=frozenset({"orders:deliver"}),
        )
        dependency = require_permission("tenant:configure")

        with pytest.raises(PermissionDeniedError):
            await dependency(principal)

    async def test_allows_an_agency_admin_with_tenant_configure(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="agency_admin",
            permission_codes=frozenset({"tenant:configure"}),
        )
        dependency = require_permission("tenant:configure")

        result = await dependency(principal)

        assert result is principal

    async def test_denies_a_manager_without_users_manage(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="manager",
            permission_codes=frozenset({"tenant:configure"}),
        )
        dependency = require_permission("users:manage")

        with pytest.raises(PermissionDeniedError):
            await dependency(principal)

    async def test_allows_a_manager_with_audit_read(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="manager",
            permission_codes=frozenset({"audit:read"}),
        )
        dependency = require_permission("audit:read")

        result = await dependency(principal)

        assert result is principal

    async def test_denies_an_agency_admin_without_feature_flags_manage_tenant(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="agency_admin",
            permission_codes=frozenset({"tenant:configure"}),
        )
        dependency = require_permission("feature_flags:manage_tenant")

        with pytest.raises(PermissionDeniedError):
            await dependency(principal)


class TestLivePermissionCheckForPlatformFlags:
    """Seeded in `fa52b77ec442`/`b8d4e0a6c2f9`: only `super_admin` has
    `feature_flags:manage_platform`.
    """

    async def test_denies_a_non_super_admin_even_with_a_tampered_claim(
        self, database: Database
    ) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="manager",
            # Claim says manager *does* have it — tampered/stale. The live
            # check must not trust this and must still deny.
            permission_codes=frozenset({"feature_flags:manage_platform"}),
        )
        checker = PermissionChecker(SqlAlchemyPermissionRepository(database))
        dependency = require_live_permission("feature_flags:manage_platform")

        with pytest.raises(PermissionDeniedError):
            await dependency(principal, checker)

    async def test_allows_a_real_super_admin(
        self, database: Database, admin_engine_lpg_test: AsyncEngine
    ) -> None:
        from sqlalchemy import text
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        # uuid4-suffixed rather than a fixed literal: a fixed email collides
        # with a leftover row from a prior local run against the same
        # lpg_test database (uq_identity_identity_user_email) — the same
        # flake class R1 already fixed twice in test_identity_repositories.py.
        email = f"{uuid.uuid4().hex}@super-admin.example"

        async with admin_engine_lpg_test.begin() as session:
            await session.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (:tenant_id, 'Super Admin Tenant', :slug, :email)"
                ),
                {"tenant_id": tenant_id, "slug": f"TS{uuid.uuid4().hex[:6]}", "email": email},
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
                    "SELECT :user_id, id FROM identity.permission WHERE code = 'feature_flags:manage_platform'"
                ),
                {"user_id": user_id},
            )

        principal = JwtAuthenticatedPrincipal(
            tenant_id=tenant_id,
            user_id=user_id,
            role="super_admin",
            permission_codes=frozenset({"feature_flags:manage_platform"}),
        )
        checker = PermissionChecker(SqlAlchemyPermissionRepository(database))
        dependency = require_live_permission("feature_flags:manage_platform")

        result = await dependency(principal, checker)

        assert result is principal
