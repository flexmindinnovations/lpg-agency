"""RBAC coverage for `reports:read`, the permission gating
`GET /dashboard/summary`.

Claims-based only (`require_permission`, no I/O) — `reports:read` is not in
`docs/data/17-api-security.md` §7's live-recheck list, so there's no
live-check test class here (contrast `test_inventory_rbac.py`'s
`reconciliation:approve` coverage). The granted-role matrix matches
`backend/migrations/versions/b3f7c1d9e4a2_grant_reports_read_permission.py`:
every staff role that uses the Dashboard, excluding `driver`/`customer`
(mobile-app-only roles).
"""

from __future__ import annotations

import uuid

import pytest

from lpg.api.v1.dependencies.identity import require_permission
from lpg.application.common.errors import PermissionDeniedError
from lpg.application.identity.principal import JwtAuthenticatedPrincipal

pytestmark = pytest.mark.integration


def _principal(role: str, permission_code: str) -> JwtAuthenticatedPrincipal:
    return JwtAuthenticatedPrincipal(
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        role=role,
        permission_codes=frozenset({permission_code}),
    )


class TestClaimsBasedChecks:
    @pytest.mark.parametrize(
        "role",
        [
            "super_admin",
            "agency_admin",
            "manager",
            "warehouse_staff",
            "dispatcher",
            "accountant",
        ],
    )
    async def test_allows_every_granted_staff_role(self, role: str) -> None:
        dependency = require_permission("reports:read")
        result = await dependency(_principal(role, "reports:read"))
        assert result.role == role

    @pytest.mark.parametrize("role", ["driver", "customer"])
    async def test_denies_mobile_app_only_roles(self, role: str) -> None:
        dependency = require_permission("reports:read")
        with pytest.raises(PermissionDeniedError):
            await dependency(_principal(role, "inventory:load"))
