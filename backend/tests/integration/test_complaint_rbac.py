"""RBAC coverage for the `complaints.manage` permission code.

Claims-based `require_permission` allow/deny, mirroring `test_customer_rbac.py`'s
pattern — no database or Redis touched, since `require_permission` is a pure
claims check against the JWT-embedded `permission_codes`.

Granted to `super_admin, agency_admin, manager, dispatcher, customer` by
`b05967dbc83e_add_complaint_permission_codes`; `warehouse_staff`, `driver`, and
`accountant` are deliberately excluded.

The two GET endpoints (`GET /complaints`, `GET /complaints/{id}`) carry no
`require_permission` dependency at all — only tenant-context resolution — so
they have no allow/deny pair here; that's a real, deliberate-looking gap
covered separately by the endpoint smoke test's reachability assertions.
"""

from __future__ import annotations

import uuid

import pytest

from lpg.api.v1.dependencies.identity import require_permission
from lpg.application.common.errors import PermissionDeniedError
from lpg.application.identity.principal import JwtAuthenticatedPrincipal

pytestmark = pytest.mark.integration


class TestComplaintsManagePermission:
    async def test_denies_a_warehouse_staff_without_complaints_manage(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="warehouse_staff",
            permission_codes=frozenset({"inventory:adjust"}),
        )
        dependency = require_permission("complaints.manage")

        with pytest.raises(PermissionDeniedError):
            await dependency(principal)

    async def test_denies_a_driver_without_complaints_manage(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="driver",
            permission_codes=frozenset({"orders:deliver"}),
        )
        dependency = require_permission("complaints.manage")

        with pytest.raises(PermissionDeniedError):
            await dependency(principal)

    async def test_denies_an_accountant_without_complaints_manage(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="accountant",
            permission_codes=frozenset({"invoices:read"}),
        )
        dependency = require_permission("complaints.manage")

        with pytest.raises(PermissionDeniedError):
            await dependency(principal)

    async def test_allows_a_dispatcher_with_complaints_manage(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="dispatcher",
            permission_codes=frozenset({"complaints.manage"}),
        )
        dependency = require_permission("complaints.manage")

        result = await dependency(principal)

        assert result is principal

    async def test_allows_a_manager_with_complaints_manage(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="manager",
            permission_codes=frozenset({"complaints.manage"}),
        )
        dependency = require_permission("complaints.manage")

        result = await dependency(principal)

        assert result is principal

    async def test_allows_a_customer_with_complaints_manage(self) -> None:
        """`customer` is deliberately included so customers can raise their
        own complaints through this same endpoint set."""
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="customer",
            permission_codes=frozenset({"complaints.manage"}),
        )
        dependency = require_permission("complaints.manage")

        result = await dependency(principal)

        assert result is principal
