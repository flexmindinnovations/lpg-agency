"""RBAC coverage for Phase 8's customer permission codes — claims-based
`require_permission` allow/deny for `customers:create`/`customers:read`/
`customers:update`, and the distinct `kyc:read`/`kyc:manage` codes
(`docs/data/17-api-security.md` §10 — KYC access must be gated separately
from general customer read/update), mirroring `test_admin_rbac.py`'s pattern.
"""

from __future__ import annotations

import uuid

import pytest

from lpg.api.v1.dependencies.identity import require_permission
from lpg.application.common.errors import PermissionDeniedError
from lpg.application.identity.principal import JwtAuthenticatedPrincipal

pytestmark = pytest.mark.integration


class TestCustomerPermissionChecks:
    async def test_denies_a_driver_without_customers_create(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="driver",
            permission_codes=frozenset({"orders:deliver"}),
        )
        dependency = require_permission("customers:create")

        with pytest.raises(PermissionDeniedError):
            await dependency(principal)

    async def test_allows_a_dispatcher_with_customers_create(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="dispatcher",
            permission_codes=frozenset({"customers:create"}),
        )
        dependency = require_permission("customers:create")

        result = await dependency(principal)

        assert result is principal

    async def test_denies_a_warehouse_staff_without_customers_read(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="warehouse_staff",
            permission_codes=frozenset({"inventory:adjust"}),
        )
        dependency = require_permission("customers:read")

        with pytest.raises(PermissionDeniedError):
            await dependency(principal)

    async def test_allows_an_accountant_with_customers_read(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="accountant",
            permission_codes=frozenset({"customers:read"}),
        )
        dependency = require_permission("customers:read")

        result = await dependency(principal)

        assert result is principal


class TestKycPermissionIsDistinctFromCustomersRead:
    """`docs/data/17-api-security.md` §10: KYC access must be gated by a
    permission "distinct from general `customers:read`" — a role holding
    only `customers:read`/`customers:update` must still be denied `kyc:*`.
    """

    async def test_customers_read_alone_does_not_grant_kyc_read(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="dispatcher",
            permission_codes=frozenset({"customers:read"}),
        )
        dependency = require_permission("kyc:read")

        with pytest.raises(PermissionDeniedError):
            await dependency(principal)

    async def test_customers_update_alone_does_not_grant_kyc_manage(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="dispatcher",
            permission_codes=frozenset({"customers:update"}),
        )
        dependency = require_permission("kyc:manage")

        with pytest.raises(PermissionDeniedError):
            await dependency(principal)

    async def test_denies_a_driver_kyc_read(self) -> None:
        # `customers:read` is granted to driver (Phase 8's seed matrix), but
        # `kyc:read` is deliberately narrower — driver must still be denied.
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="driver",
            permission_codes=frozenset({"customers:read"}),
        )
        dependency = require_permission("kyc:read")

        with pytest.raises(PermissionDeniedError):
            await dependency(principal)

    async def test_allows_a_manager_with_kyc_read(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="manager",
            permission_codes=frozenset({"kyc:read"}),
        )
        dependency = require_permission("kyc:read")

        result = await dependency(principal)

        assert result is principal

    async def test_allows_an_agency_admin_with_kyc_manage(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="agency_admin",
            permission_codes=frozenset({"kyc:manage"}),
        )
        dependency = require_permission("kyc:manage")

        result = await dependency(principal)

        assert result is principal
