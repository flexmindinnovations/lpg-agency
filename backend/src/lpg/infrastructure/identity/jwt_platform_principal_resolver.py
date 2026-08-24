"""`JwtPlatformPrincipalResolver` — the `/platform/*` sibling of
`JwtTenantResolver`.

`JwtTenantResolver.resolve()` rejects any JWT with no `tenant_id` claim —
correct for every tenant-scoped endpoint, since a `super_admin` session
genuinely has no tenant to establish RLS context with (D-01). This resolver
exists for the opposite case: routes that must accept *only* a `super_admin`
session, verified the same way (same `JwtSigner`, same signature check),
but never touching `tenant_id`/RLS/`UnitOfWork` at all.

Deliberately requires `role == "super_admin"` rather than accepting any
authenticated principal and letting a downstream permission check sort it
out: D-01 already establishes `super_admin` as the *only* role with no
tenant, so a token claiming any other role reaching this resolver is
already a contract violation, not merely an unauthorized action — rejected
here, before any `/platform/*` permission code is even considered.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from lpg.application.common.errors import PermissionDeniedError, TenantContextMissingError
from lpg.application.platform.principal import JwtPlatformPrincipal
from lpg.config.logging import get_logger

if TYPE_CHECKING:
    from lpg.application.identity.ports import JwtSigner
    from lpg.application.platform.principal import PlatformPrincipal

_logger = get_logger(__name__)

AUTHORIZATION_HEADER = "Authorization"
_BEARER_PREFIX = "Bearer "


class JwtPlatformPrincipalResolver:
    def __init__(self, jwt_signer: JwtSigner) -> None:
        self._jwt_signer = jwt_signer

    async def resolve(self, request: Any) -> PlatformPrincipal:
        header = request.headers.get(AUTHORIZATION_HEADER)
        if not header or not header.startswith(_BEARER_PREFIX):
            _logger.warning("platform_principal_bearer_token_missing")
            msg = "A valid Authorization: Bearer token is required."
            raise TenantContextMissingError(msg)

        token = header.removeprefix(_BEARER_PREFIX)
        claims = self._jwt_signer.decode_access_token(token)

        role = claims.get("role")
        if role != "super_admin":
            _logger.warning("platform_principal_not_super_admin", role=role)
            msg = "This route is available to Super Admin sessions only."
            raise PermissionDeniedError(msg)

        return JwtPlatformPrincipal(
            user_id=uuid.UUID(claims["sub"]),
            role=role,
            permission_codes=frozenset(claims.get("scope", "").split()),
            email=claims.get("name"),
        )
