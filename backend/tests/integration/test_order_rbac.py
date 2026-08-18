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

    Same reasoning as `test_inventory_rbac.py`'s copy of this fixture.
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

    async def test_allows_a_real_agency_admin(
        self, database: Database, admin_engine_lpg_test: AsyncEngine
    ) -> None:
        """Same reasoning as test_inventory_rbac.py's copy of this test —
        `has_permission` needs a real identity_user_permission row, which a
        synthetic uuid.uuid4() user_id can never have.
        """

        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()

        async with admin_engine_lpg_test.begin() as session:
            await session.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (:tenant_id, 'Order RBAC Tenant', :slug, 'ops@example.com')"
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
                    "role": "agency_admin",
                },
            )
            await session.execute(
                text(
                    "INSERT INTO identity.identity_user_permission (user_id, permission_id) "
                    "SELECT :user_id, id FROM identity.permission WHERE code = :code"
                ),
                {"user_id": user_id, "code": "orders:cancel_approve"},
            )

        principal = JwtAuthenticatedPrincipal(
            tenant_id=tenant_id,
            user_id=user_id,
            role="agency_admin",
            permission_codes=frozenset({"orders:cancel_approve"}),
        )
        checker = PermissionChecker(SqlAlchemyPermissionRepository(database))
        dependency = require_live_permission("orders:cancel_approve")

        result = await dependency(principal, checker)

        assert result is principal
