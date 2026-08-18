"""RBAC coverage for the inventory permission codes.

Claims-based `require_permission` allow/deny per the exact matrices in
`docs/data/17-api-security.md` §6 (also encoded in migration
`4f8b2d6a9c1e_create_inventory_schema.py`), plus a live-check test class for
`reconciliation:approve` mirroring `test_admin_rbac.py`'s
`TestLivePermissionCheckForPlatformFlags` — proving the live re-query denies
`manager` even with a tampered claim (§6: `reconciliation:approve` excludes
`manager`, unlike `inventory:adjust`, which includes it).
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
    """A superuser-privileged connection, for seeding a *real* backing user.

    A live check against a synthetic ``uuid.uuid4()`` user_id can never
    succeed under the per-user permission model (``8c221c3e0a91``), no
    matter what role or claim is attached — so "allows a real X" must
    actually seed one.
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


def _principal(role: str, permission_code: str) -> JwtAuthenticatedPrincipal:
    return JwtAuthenticatedPrincipal(
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        role=role,
        permission_codes=frozenset({permission_code}),
    )


class TestClaimsBasedChecks:
    async def test_allows_warehouse_staff_inventory_read(self) -> None:
        dependency = require_permission("inventory:read")
        result = await dependency(_principal("warehouse_staff", "inventory:read"))
        assert result.role == "warehouse_staff"

    async def test_denies_customer_inventory_read(self) -> None:
        dependency = require_permission("inventory:read")
        with pytest.raises(PermissionDeniedError):
            await dependency(_principal("customer", "orders:read"))

    async def test_allows_driver_inventory_load(self) -> None:
        """driver: 11-api-contracts.md line 126 — the route-loading endpoint."""
        dependency = require_permission("inventory:load")
        result = await dependency(_principal("driver", "inventory:load"))
        assert result.role == "driver"

    async def test_denies_accountant_inventory_load(self) -> None:
        dependency = require_permission("inventory:load")
        with pytest.raises(PermissionDeniedError):
            await dependency(_principal("accountant", "inventory:read"))

    async def test_allows_warehouse_staff_inventory_adjust(self) -> None:
        dependency = require_permission("inventory:adjust")
        result = await dependency(_principal("warehouse_staff", "inventory:adjust"))
        assert result.role == "warehouse_staff"

    async def test_denies_driver_inventory_adjust(self) -> None:
        dependency = require_permission("inventory:adjust")
        with pytest.raises(PermissionDeniedError):
            await dependency(_principal("driver", "inventory:load"))


class TestLivePermissionCheckForReconciliationApprove:
    """Seeded in `fa52b77ec442`: `agency_admin`/`warehouse_staff` only —
    deliberately excludes `manager`, unlike `inventory:adjust`.
    """

    async def test_denies_a_manager_even_with_a_tampered_claim(self, database: Database) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="manager",
            # Claim says manager *does* have it — tampered/stale. The live
            # check must not trust this and must still deny.
            permission_codes=frozenset({"reconciliation:approve"}),
        )
        checker = PermissionChecker(SqlAlchemyPermissionRepository(database))
        dependency = require_live_permission("reconciliation:approve")

        with pytest.raises(PermissionDeniedError):
            await dependency(principal, checker)

    async def test_allows_a_real_warehouse_staff(
        self, database: Database, admin_engine_lpg_test: AsyncEngine
    ) -> None:
        """Unlike the sibling test above, this must check against a *real*
        identity_user with a real permission grant — `has_permission` now
        queries `identity_user_permission` by user_id (8c221c3e0a91), which
        a synthetic uuid.uuid4() can never have a row for.
        """

        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()

        async with admin_engine_lpg_test.begin() as session:
            await session.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (:tenant_id, 'Inventory RBAC Tenant', :slug, 'ops@example.com')"
                ),
                {"tenant_id": tenant_id, "slug": f"TS{uuid.uuid4().hex[:6]}"},
            )
            await session.execute(
                text(
                    "INSERT INTO identity.identity_user "
                    "(id, tenant_id, email, password_hash, role) "
                    "VALUES (:user_id, :tenant_id, :email, 'hash', :role)"
                ),
                {
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "email": f"{uuid.uuid4().hex}@rbac.example",
                    "role": "warehouse_staff",
                },
            )
            await session.execute(
                text(
                    "INSERT INTO identity.identity_user_permission (user_id, permission_id) "
                    "SELECT :user_id, id FROM identity.permission WHERE code = :code"
                ),
                {"user_id": user_id, "code": "reconciliation:approve"},
            )

        principal = JwtAuthenticatedPrincipal(
            tenant_id=tenant_id,
            user_id=user_id,
            role="warehouse_staff",
            permission_codes=frozenset({"reconciliation:approve"}),
        )
        checker = PermissionChecker(SqlAlchemyPermissionRepository(database))
        dependency = require_live_permission("reconciliation:approve")

        result = await dependency(principal, checker)

        assert result is principal
