"""Concrete `AuthenticatedPrincipal`.

A plain value object — no FastAPI, no SQLAlchemy, no PyJWT — so it belongs
in the application layer alongside the protocol it implements
(`application/identity/ports.py`), not in infrastructure. Mirrors
`application/common/tenant.py::RequestTenantContext`'s placement exactly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid


@dataclass(frozen=True, slots=True)
class JwtAuthenticatedPrincipal:
    """Structurally satisfies both `TenantContext` and `AuthenticatedPrincipal`
    (`application/common/ports.py`, `application/identity/ports.py`) —
    `get_tenant_context`/`get_unit_of_work` need zero changes to accept this
    in place of `RequestTenantContext`.
    """

    tenant_id: uuid.UUID
    user_id: uuid.UUID | None
    role: str
    permission_codes: frozenset[str]
    user_display_name: str | None = None
    token_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None
