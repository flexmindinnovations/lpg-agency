"""RBAC coverage for Phase 9's delivery permission codes.

Tests `require_permission` allow/deny for `drivers:read`/`drivers:manage`
and `vehicles:read`/`vehicles:manage` mirroring test_customer_rbac.py.
"""

from __future__ import annotations

import uuid

import pytest

from lpg.api.v1.dependencies.identity import require_permission
from lpg.application.common.errors import PermissionDeniedError
from lpg.application.identity.principal import JwtAuthenticatedPrincipal

pytestmark = pytest.mark.integration


class TestDriverPermissionChecks:
    async def test_denies_customer_without_drivers_read(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="customer",
            permission_codes=frozenset({"orders:create"}),
        )
        dependency = require_permission("drivers:read")

        with pytest.raises(PermissionDeniedError):
            await dependency(principal)

    async def test_allows_dispatcher_with_drivers_read(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="dispatcher",
            permission_codes=frozenset({"drivers:read"}),
        )
        dependency = require_permission("drivers:read")

        result = await dependency(principal)
        assert result is principal

    async def test_denies_driver_role_without_drivers_manage(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="driver",
            permission_codes=frozenset({"drivers:read"}),
        )
        dependency = require_permission("drivers:manage")

        with pytest.raises(PermissionDeniedError):
            await dependency(principal)

    async def test_allows_manager_with_drivers_manage(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="manager",
            permission_codes=frozenset({"drivers:manage"}),
        )
        dependency = require_permission("drivers:manage")

        result = await dependency(principal)
        assert result is principal


class TestVehiclePermissionChecks:
    async def test_denies_customer_without_vehicles_read(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="customer",
            permission_codes=frozenset({"orders:create"}),
        )
        dependency = require_permission("vehicles:read")

        with pytest.raises(PermissionDeniedError):
            await dependency(principal)

    async def test_allows_warehouse_staff_with_vehicles_read(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="warehouse_staff",
            permission_codes=frozenset({"vehicles:read"}),
        )
        dependency = require_permission("vehicles:read")

        result = await dependency(principal)
        assert result is principal

    async def test_denies_driver_without_vehicles_manage(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="driver",
            permission_codes=frozenset({"vehicles:read"}),
        )
        dependency = require_permission("vehicles:manage")

        with pytest.raises(PermissionDeniedError):
            await dependency(principal)

    async def test_allows_agency_admin_with_vehicles_manage(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="agency_admin",
            permission_codes=frozenset({"vehicles:manage"}),
        )
        dependency = require_permission("vehicles:manage")

        result = await dependency(principal)
        assert result is principal
