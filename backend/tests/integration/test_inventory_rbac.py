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

from lpg.api.v1.dependencies.identity import require_live_permission, require_permission
from lpg.application.common.errors import PermissionDeniedError
from lpg.application.identity.authorize import PermissionChecker
from lpg.application.identity.principal import JwtAuthenticatedPrincipal
from lpg.infrastructure.persistence.database import Database
from lpg.infrastructure.persistence.repositories.identity import SqlAlchemyPermissionRepository

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

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

    async def test_allows_a_real_warehouse_staff(self, database: Database) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="warehouse_staff",
            permission_codes=frozenset({"reconciliation:approve"}),
        )
        checker = PermissionChecker(SqlAlchemyPermissionRepository(database))
        dependency = require_live_permission("reconciliation:approve")

        result = await dependency(principal, checker)

        assert result is principal
