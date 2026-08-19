"""RBAC coverage for the `users:manage`/`users:read` permission codes used by
`POST /employees` and `GET /employees`.

Claims-based `require_permission` allow/deny, mirroring `test_customer_rbac.py`'s
pattern — no database or Redis touched.

`users:manage` is granted to `agency_admin` only
(`b8d4e0a6c2f9_add_administration_permission_codes`). `users:read` is
granted to `super_admin, agency_admin, manager, dispatcher`
(`a907e81bc74c_add_users_read_permission`) — narrower than `users:manage`,
so a manager can list employees but cannot register one.
"""

from __future__ import annotations

import uuid

import pytest

from lpg.api.v1.dependencies.identity import require_permission
from lpg.application.common.errors import PermissionDeniedError
from lpg.application.identity.principal import JwtAuthenticatedPrincipal

pytestmark = pytest.mark.integration


class TestUsersManagePermission:
    async def test_denies_a_manager_without_users_manage(self) -> None:
        """`manager` holds `users:read` but not `users:manage` — narrower
        permission does not imply the broader one."""
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="manager",
            permission_codes=frozenset({"users:read"}),
        )
        dependency = require_permission("users:manage")

        with pytest.raises(PermissionDeniedError):
            await dependency(principal)

    async def test_denies_a_dispatcher_without_users_manage(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="dispatcher",
            permission_codes=frozenset({"orders:create"}),
        )
        dependency = require_permission("users:manage")

        with pytest.raises(PermissionDeniedError):
            await dependency(principal)

    async def test_allows_an_agency_admin_with_users_manage(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="agency_admin",
            permission_codes=frozenset({"users:manage"}),
        )
        dependency = require_permission("users:manage")

        result = await dependency(principal)

        assert result is principal


class TestUsersReadPermission:
    async def test_denies_a_driver_without_users_read(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="driver",
            permission_codes=frozenset({"orders:deliver"}),
        )
        dependency = require_permission("users:read")

        with pytest.raises(PermissionDeniedError):
            await dependency(principal)

    async def test_denies_an_accountant_without_users_read(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="accountant",
            permission_codes=frozenset({"invoices:read"}),
        )
        dependency = require_permission("users:read")

        with pytest.raises(PermissionDeniedError):
            await dependency(principal)

    async def test_allows_a_dispatcher_with_users_read(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="dispatcher",
            permission_codes=frozenset({"users:read"}),
        )
        dependency = require_permission("users:read")

        result = await dependency(principal)

        assert result is principal

    async def test_allows_a_manager_with_users_read(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="manager",
            permission_codes=frozenset({"users:read"}),
        )
        dependency = require_permission("users:read")

        result = await dependency(principal)

        assert result is principal
