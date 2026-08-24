"""`TenantStatusChecker` — the cheap, cached read backing tenant-suspension
enforcement.

Mirrors `application/license/ports.py::LicenseStatusChecker`'s exact shape
and reasoning: `LoginUseCase`/`RefreshTokenUseCase`/`get_tenant_context`
each need this on every authenticated request, so it's a narrow, cached
seam — never the full `TenantRepository` — the same way license status
checks never go through the full `LicenseRepository`.

Deliberately a **second, independent** check from `LicenseStatusChecker`,
not merged into it — a suspended agency and a revoked license are different
facts about a tenant, decided by different actors (a `super_admin`
suspending the whole agency vs. a license simply expiring or being
revoked), and the two checks live at the same call sites without knowing
about each other.

Returns `Tenant.status` verbatim (`"trial" | "active" | "suspended" |
"closed"`) rather than a dedicated enum — the domain aggregate itself
(`domain/tenant/tenant.py`) never introduced one for this, and this port
shouldn't invent a parallel vocabulary the aggregate doesn't share.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid


@runtime_checkable
class TenantStatusChecker(Protocol):
    async def get_status(self, tenant_id: uuid.UUID) -> str: ...

    async def invalidate(self, tenant_id: uuid.UUID) -> None: ...
