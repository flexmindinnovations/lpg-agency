"""`JwtTenantResolver` implements `application/common/ports.py::TenantResolver`.

Replaces `HeaderTenantResolver` (`infrastructure/tenant/header_resolver.py`)
— the one-line rebind in `api/v1/dependencies/tenant.py` is the entire point
of ADR-017's seam. Reads `Authorization: Bearer <token>`, verifies it via
`JwtSigner`, and returns an `AuthenticatedPrincipal` built from the verified
claims — never from a client-supplied header or body parameter.

**Known limitation, not a gap**: Super Admin's `tenant_id` claim is `null`
(D-01 — Super Admin operates above tenant scope), but `TenantContext.
tenant_id` (Phase 2's protocol, unchanged here) is non-optional — every
business endpoint's session-opening path (`get_unit_of_work`) requires a
real UUID. Full Super Admin request-handling is Phase 7+ scope; this
resolver raises rather than fabricating a tenant_id for a Super Admin's
token.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from lpg.application.common.errors import TenantContextMissingError
from lpg.application.identity.principal import JwtAuthenticatedPrincipal
from lpg.config.logging import get_logger

if TYPE_CHECKING:
    from lpg.application.common.ports import TenantContext
    from lpg.application.identity.ports import JwtSigner

_logger = get_logger(__name__)

AUTHORIZATION_HEADER = "Authorization"
_BEARER_PREFIX = "Bearer "


class JwtTenantResolver:
    def __init__(self, jwt_signer: JwtSigner) -> None:
        self._jwt_signer = jwt_signer

    async def resolve(self, request: Any) -> TenantContext:
        header = request.headers.get(AUTHORIZATION_HEADER)
        if not header or not header.startswith(_BEARER_PREFIX):
            _logger.warning("tenant_context_bearer_token_missing")
            msg = "A valid Authorization: Bearer token is required."
            raise TenantContextMissingError(msg)

        token = header.removeprefix(_BEARER_PREFIX)
        claims = self._jwt_signer.decode_access_token(token)

        raw_tenant_id = claims.get("tenant_id")
        if not raw_tenant_id:
            _logger.warning("tenant_context_super_admin_unsupported")
            msg = (
                "This token has no tenant scope (Super Admin). Tenant-scoped "
                "endpoints don't support Super Admin sessions yet."
            )
            raise TenantContextMissingError(msg)

        raw_branch_id = claims.get("branch_id")

        return JwtAuthenticatedPrincipal(
            tenant_id=uuid.UUID(raw_tenant_id),
            user_id=uuid.UUID(claims["sub"]),
            user_display_name=claims.get("name"),
            role=claims["role"],
            permission_codes=frozenset(claims.get("scope", "").split()),
            branch_id=uuid.UUID(raw_branch_id) if raw_branch_id else None,
        )
