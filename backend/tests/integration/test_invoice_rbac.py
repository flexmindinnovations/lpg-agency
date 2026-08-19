"""RBAC coverage for the `invoices:read` permission code used by both invoice
read endpoints (`GET /invoices`, `GET /invoices/{id}`), and the
`invoices:record_payment` code (R10) used by `POST /invoices/{id}/payments`.

Claims-based `require_permission` allow/deny, mirroring `test_customer_rbac.py`'s
pattern — no database or Redis touched.

Both codes are granted to the same role set —
`super_admin, agency_admin, manager, accountant` — by
`b9248bf4b34f_grant_invoices_read_permission` and `11ddf55a78ed_create_
payment_table` respectively; `dispatcher`, `warehouse_staff`, `driver`, and
`customer` are deliberately excluded from both — invoices are a back-office/
accounting concern, not something a customer reads or pays through this
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


class TestInvoicesRecordPaymentPermission:
    async def test_denies_a_dispatcher_without_invoices_record_payment(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="dispatcher",
            permission_codes=frozenset({"orders:create"}),
        )
        dependency = require_permission("invoices:record_payment")

        with pytest.raises(PermissionDeniedError):
            await dependency(principal)

    async def test_denies_an_accountant_with_only_invoices_read(self) -> None:
        """Narrower permission does not imply the broader one — an
        accountant who can read invoices cannot record a payment without
        the separate `invoices:record_payment` grant."""
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="accountant",
            permission_codes=frozenset({"invoices:read"}),
        )
        dependency = require_permission("invoices:record_payment")

        with pytest.raises(PermissionDeniedError):
            await dependency(principal)

    async def test_allows_an_accountant_with_invoices_record_payment(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="accountant",
            permission_codes=frozenset({"invoices:record_payment"}),
        )
        dependency = require_permission("invoices:record_payment")

        result = await dependency(principal)

        assert result is principal

    async def test_allows_an_agency_admin_with_invoices_record_payment(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="agency_admin",
            permission_codes=frozenset({"invoices:record_payment"}),
        )
        dependency = require_permission("invoices:record_payment")

        result = await dependency(principal)

        assert result is principal


class TestCreditNotesRequestPermission:
    async def test_denies_a_dispatcher_without_credit_notes_request(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="dispatcher",
            permission_codes=frozenset({"orders:create"}),
        )
        dependency = require_permission("credit_notes:request")

        with pytest.raises(PermissionDeniedError):
            await dependency(principal)

    async def test_allows_an_accountant_with_credit_notes_request(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="accountant",
            permission_codes=frozenset({"credit_notes:request"}),
        )
        dependency = require_permission("credit_notes:request")

        result = await dependency(principal)

        assert result is principal


class TestCreditNotesApprovePermission:
    async def test_denies_an_accountant_without_credit_notes_approve(self) -> None:
        """`credit_notes:approve` deliberately excludes `accountant` —
        narrower than `credit_notes:request`, holding that alone does not
        imply approval rights."""
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="accountant",
            permission_codes=frozenset({"credit_notes:request"}),
        )
        dependency = require_permission("credit_notes:approve")

        with pytest.raises(PermissionDeniedError):
            await dependency(principal)

    async def test_allows_a_manager_with_credit_notes_approve(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="manager",
            permission_codes=frozenset({"credit_notes:approve"}),
        )
        dependency = require_permission("credit_notes:approve")

        result = await dependency(principal)

        assert result is principal

    async def test_allows_an_agency_admin_with_credit_notes_approve(self) -> None:
        principal = JwtAuthenticatedPrincipal(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            role="agency_admin",
            permission_codes=frozenset({"credit_notes:approve"}),
        )
        dependency = require_permission("credit_notes:approve")

        result = await dependency(principal)

        assert result is principal
