"""The Phase 2 stand-in ``TenantResolver``.

Resolves a ``TenantContext`` from an explicit, **unverified** request header.
This exists to prove and test the request → tenant context → session →
PostgreSQL RLS seam end to end (Phase 2's Area B) before Authentication
(Phase 6) exists to supply a real, cryptographically-verified principal.

**This is not a security boundary.** A client can set the header to any UUID
it likes; nothing here proves the caller is entitled to that tenant. It is
safe *only* because, in Phase 2, no protected business endpoint consumes it —
the composition root wires no router that would let an unauthenticated
request reach a tenant-scoped resource through this path. Wiring this
resolver into a real, reachable endpoint before Phase 6 replaces it would be
a tenant-isolation bypass, not a convenience.

**Phase 6 replaces this file's role, not its shape.** A ``JwtTenantResolver``
implementing the same ``TenantResolver`` protocol (`lpg.application.common
.ports`), reading the verified `tenant_id`/`sub` claims instead of a header,
is a drop-in replacement — the protocol is the seam ADR-017 and this module
exist to prove works before the real resolver is written.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from lpg.application.common.errors import TenantContextMissingError
from lpg.application.common.tenant import RequestTenantContext
from lpg.config.logging import get_logger

if TYPE_CHECKING:
    from lpg.application.common.ports import TenantContext

_logger = get_logger(__name__)

TENANT_HEADER = "X-Debug-Tenant-Id"
USER_HEADER = "X-Debug-User-Id"


class HeaderTenantResolver:
    """Reads ``X-Debug-Tenant-Id`` (and optionally ``X-Debug-User-Id``).

    Structurally satisfies ``TenantResolver``. Raises ``TenantContextMissingError``
    when the header is absent or not a valid UUID, so the failure surfaces as
    the same RFC 7807 shape a real authentication failure would.
    """

    async def resolve(self, request: Any) -> TenantContext:
        raw_tenant_id = request.headers.get(TENANT_HEADER)
        if not raw_tenant_id:
            _logger.warning("tenant_context_header_missing", header=TENANT_HEADER)
            msg = f"Required header {TENANT_HEADER!r} was not supplied."
            raise TenantContextMissingError(msg)

        try:
            tenant_id = uuid.UUID(raw_tenant_id)
        except ValueError as exc:
            _logger.warning("tenant_context_header_invalid", header=TENANT_HEADER)
            msg = f"Header {TENANT_HEADER!r} is not a valid UUID."
            raise TenantContextMissingError(msg) from exc

        raw_user_id = request.headers.get(USER_HEADER)
        user_id = uuid.UUID(raw_user_id) if raw_user_id else None

        return RequestTenantContext(tenant_id=tenant_id, user_id=user_id)
