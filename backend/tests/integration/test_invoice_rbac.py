"""RBAC coverage for the `invoices:read` permission code used by both invoice
endpoints (`GET /invoices`, `GET /invoices/{id}`).

Claims-based `require_permission` allow/deny, mirroring `test_customer_rbac.py`'s
pattern — no database or Redis touched.

Granted to `super_admin, agency_admin, manager, accountant` by
`b9248bf4b34f_grant_invoices_read_permission`; `dispatcher`, `warehouse_staff`,
`driver`, and `customer` are deliberately excluded — invoices are a
back-office/accounting concern, not something a customer reads through this
staff-facing router.
"""

from __future__ import annotations

import uuid

import pytest

from lpg.api.v1.dependencies.identity import require_permission
from lpg.application.common.errors import PermissionDeniedError
from lpg.application.identity.principal import JwtAuthenticatedPrincipal

pytestmark = pytest.mark.integration


class TestInvoicesReadPermission:
    async def test_denies_a_dispatcher_without_invoices_read(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="dispatcher",
            permission_codes=frozenset({"orders:create"}),
        )
        dependency = require_permission("invoices:read")

        with pytest.raises(PermissionDeniedError):
            await dependency(principal)

    async def test_denies_a_customer_without_invoices_read(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="customer",
            permission_codes=frozenset({"complaints.manage"}),
        )
        dependency = require_permission("invoices:read")

        with pytest.raises(PermissionDeniedError):
            await dependency(principal)

    async def test_denies_a_driver_without_invoices_read(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="driver",
            permission_codes=frozenset({"orders:deliver"}),
        )
        dependency = require_permission("invoices:read")

        with pytest.raises(PermissionDeniedError):
            await dependency(principal)

    async def test_allows_an_accountant_with_invoices_read(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="accountant",
            permission_codes=frozenset({"invoices:read"}),
        )
        dependency = require_permission("invoices:read")

        result = await dependency(principal)

        assert result is principal

    async def test_allows_a_manager_with_invoices_read(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="manager",
            permission_codes=frozenset({"invoices:read"}),
        )
        dependency = require_permission("invoices:read")

        result = await dependency(principal)

        assert result is principal
