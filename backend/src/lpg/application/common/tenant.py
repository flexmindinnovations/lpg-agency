"""Concrete ``TenantContext``.

A plain value object — no FastAPI, no SQLAlchemy — so it belongs in the
application layer alongside the ``TenantContext`` protocol it implements
(``lpg.application.common.ports``), not in infrastructure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid


@dataclass(frozen=True, slots=True)
class RequestTenantContext:
    """The tenant and actor resolved for the current request.

    Structurally satisfies the ``TenantContext`` protocol. Construction is
    deliberately not validated here — the *resolver* (infrastructure layer)
    is what decides whether a tenant/user pair is trustworthy; this type only
    carries the result.
    """

    tenant_id: uuid.UUID
    user_id: uuid.UUID | None = None
    user_display_name: str | None = None
