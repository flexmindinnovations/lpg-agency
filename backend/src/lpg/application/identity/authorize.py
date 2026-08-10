"""`PermissionChecker` — claims-based and live permission checks.

Not a Command/UseCase — a small application service the RBAC dependency
layer (`api/v1/dependencies/identity.py`, Area E) calls directly from a
FastAPI dependency, the same way `TenantResolver` implementations are called
from `get_tenant_context`.

Two check modes, per `docs/data/17-api-security.md` §4/§7:
- `has_permission` — claims-based, no I/O, fast. Correct for the vast
  majority of endpoints; staleness is bounded by the 15-minute access-token
  lifetime.
- `has_permission_live` — re-queries `identity.role_permission` through the
  real UoW session. Required for exactly four action classes named in §7:
  `reconciliation:approve`, `credit_notes:approve`, `orders:cancel_approve`,
  and any `super_admin` cross-tenant action — claim staleness is judged
  unacceptable for these specifically, not as a blanket policy.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lpg.application.identity.ports import AuthenticatedPrincipal, PermissionRepository


class PermissionChecker:
    def __init__(self, permission_repository: PermissionRepository) -> None:
        self._permission_repository = permission_repository

    def has_permission(self, principal: AuthenticatedPrincipal, permission_code: str) -> bool:
        return permission_code in principal.permission_codes

    async def has_permission_live(
        self, principal: AuthenticatedPrincipal, permission_code: str
    ) -> bool:
        return await self._permission_repository.has_permission(
            role=principal.role, permission_code=permission_code
        )
