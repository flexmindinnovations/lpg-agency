"""RBAC coverage for the order permission codes.

Claims-based `require_permission` allow/deny per the exact matrices in
`7c3f1a9e2b4d_create_orders_schema.py` (and `fa52b77ec442` for the four
pre-existing codes), plus a live-check test class for `orders:cancel_approve`
mirroring `test_inventory_rbac.py`'s `TestLivePermissionCheckForReconciliationApprove`
— proving the live re-query denies a role even with a tampered claim.
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
    async def test_allows_dispatcher_orders_create(self) -> None:
        dependency = require_permission("orders:create")
        result = await dependency(_principal("dispatcher", "orders:create"))
        assert result.role == "dispatcher"

    async def test_denies_driver_orders_create(self) -> None:
        dependency = require_permission("orders:create")
        with pytest.raises(PermissionDeniedError):
            await dependency(_principal("driver", "orders:deliver"))

    async def test_allows_manager_orders_confirm(self) -> None:
        dependency = require_permission("orders:confirm")
        result = await dependency(_principal("manager", "orders:confirm"))
        assert result.role == "manager"

    async def test_denies_customer_orders_confirm(self) -> None:
        dependency = require_permission("orders:confirm")
        with pytest.raises(PermissionDeniedError):
            await dependency(_principal("customer", "orders:create"))

    async def test_allows_dispatcher_orders_assign(self) -> None:
        dependency = require_permission("orders:assign")
        result = await dependency(_principal("dispatcher", "orders:assign"))
        assert result.role == "dispatcher"

    async def test_denies_warehouse_staff_orders_assign(self) -> None:
        dependency = require_permission("orders:assign")
        with pytest.raises(PermissionDeniedError):
            await dependency(_principal("warehouse_staff", "inventory:load"))

    async def test_allows_driver_orders_dispatch(self) -> None:
        """`orders:dispatch` deliberately folds dispatch/depart/reschedule —
        driver self-triggers "depart".
        """
        dependency = require_permission("orders:dispatch")
        result = await dependency(_principal("driver", "orders:dispatch"))
        assert result.role == "driver"

    async def test_denies_accountant_orders_dispatch(self) -> None:
        dependency = require_permission("orders:dispatch")
        with pytest.raises(PermissionDeniedError):
            await dependency(_principal("accountant", "ledger:read"))

    async def test_allows_driver_orders_deliver(self) -> None:
        dependency = require_permission("orders:deliver")
        result = await dependency(_principal("driver", "orders:deliver"))
        assert result.role == "driver"

    async def test_denies_dispatcher_orders_deliver(self) -> None:
        dependency = require_permission("orders:deliver")
        with pytest.raises(PermissionDeniedError):
            await dependency(_principal("dispatcher", "orders:dispatch"))

    async def test_allows_customer_orders_cancel(self) -> None:
        dependency = require_permission("orders:cancel")
        result = await dependency(_principal("customer", "orders:cancel"))
        assert result.role == "customer"

    async def test_denies_warehouse_staff_orders_cancel(self) -> None:
        dependency = require_permission("orders:cancel")
        with pytest.raises(PermissionDeniedError):
            await dependency(_principal("warehouse_staff", "inventory:load"))

    async def test_allows_manager_orders_close(self) -> None:
        dependency = require_permission("orders:close")
        result = await dependency(_principal("manager", "orders:close"))
        assert result.role == "manager"

    async def test_denies_dispatcher_orders_close(self) -> None:
        dependency = require_permission("orders:close")
        with pytest.raises(PermissionDeniedError):
            await dependency(_principal("dispatcher", "orders:dispatch"))


class TestLivePermissionCheckForOrdersCancelApprove:
    """Seeded in `fa52b77ec442`: `agency_admin`/`manager` only — `dispatcher`
    is deliberately excluded despite holding `orders:cancel`/`orders:dispatch`.
    """

    async def test_denies_a_dispatcher_even_with_a_tampered_claim(self, database: Database) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="dispatcher",
            # Claim says dispatcher *does* have it — tampered/stale. The live
            # check must not trust this and must still deny.
            permission_codes=frozenset({"orders:cancel_approve"}),
        )
        checker = PermissionChecker(SqlAlchemyPermissionRepository(database))
        dependency = require_live_permission("orders:cancel_approve")

        with pytest.raises(PermissionDeniedError):
            await dependency(principal, checker)

    async def test_allows_a_real_agency_admin(self, database: Database) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="agency_admin",
            permission_codes=frozenset({"orders:cancel_approve"}),
        )
        checker = PermissionChecker(SqlAlchemyPermissionRepository(database))
        dependency = require_live_permission("orders:cancel_approve")

        result = await dependency(principal, checker)

        assert result is principal
