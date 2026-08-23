"""Tenant context dependency.

Wires a ``TenantResolver`` (infrastructure) into FastAPI's dependency system,
producing a ``TenantContext`` every downstream dependency and use case depends
on. Phase 2 bound the interim ``HeaderTenantResolver``; Phase 6 rebinds this
one function to ``JwtTenantResolver`` — the whole point of ADR-017's seam —
and nothing downstream changes.

``Request``/``TenantContext`` are real imports, not ``TYPE_CHECKING``
-guarded — ``get_tenant_context`` is itself passed to ``Depends()`` at
every call site, and with ``from __future__ import annotations``, FastAPI
resolves its signature via ``typing.get_type_hints()`` at request time. See
``api/v1/routers/auth.py``'s module docstring for the full failure mode
this avoids (found the hard way, by a failing end-to-end test).
"""

from __future__ import annotations

import structlog
from fastapi import Request

from lpg.application.common.ports import TenantContext


async def get_tenant_context(request: Request) -> TenantContext:
    """FastAPI dependency resolving the current request's tenant context.

    ``JwtTenantResolver`` is constructed fresh per call rather than cached
    as a module-level singleton (unlike Phase 2's ``HeaderTenantResolver``):
    it wraps ``JwtSigner``, which isn't available until the application
    lifespan has run, and construction itself is a cheap attribute lookup —
    caching would only add lazy-initialization complexity for no real gain.
    Imports are deferred to function scope for the same reason
    ``dependencies/unit_of_work.py`` defers them: ``lpg.api.app`` has a
    module-level ``app = create_app()`` side effect that must not run at
    import time here.

    Binds ``tenant_id``/``user_id`` into structlog's contextvars once
    resolved — every log line for the rest of this request carries them
    automatically, the same mechanism ``CorrelationIdMiddleware`` already
    uses for ``correlation_id`` (``03-backend-architecture.md`` §10: "every
    log entry carries... correlation_id, tenant_id, user_id"). Bound here,
    not in the middleware, because the middleware runs before authentication
    resolves a tenant — there is nothing to bind yet at that point.

    **Also the per-request license check** — deliberately kept here rather
    than inside ``JwtTenantResolver`` itself, which stays a pure JWT-
    verification concern with its own isolated unit tests. This is the
    *only* place that catches a license expiring mid-access-token-lifetime
    (~15 minutes) rather than waiting for the next refresh — every other
    license check (login, OTP verify, refresh) only runs at token issuance.
    Reads through ``LicenseStatusChecker``'s Redis-backed cache, so this
    adds no DB round-trip to the common case.
    """
    from lpg.api.v1.dependencies.identity import get_jwt_signer
    from lpg.api.v1.dependencies.license import get_license_status_checker
    from lpg.application.common.errors import LicenseExpiredError
    from lpg.domain.license.license import LicenseLifecycleState
    from lpg.infrastructure.identity.jwt_tenant_resolver import JwtTenantResolver

    resolver = JwtTenantResolver(get_jwt_signer())
    context = await resolver.resolve(request)
    structlog.contextvars.bind_contextvars(
        tenant_id=str(context.tenant_id),
        user_id=str(context.user_id) if context.user_id else None,
    )

    status_checker = get_license_status_checker()
    license_status = await status_checker.get_status(context.tenant_id)
    if license_status in (LicenseLifecycleState.BLOCKED, LicenseLifecycleState.REVOKED):
        msg = "This tenant's license has expired."
        raise LicenseExpiredError(msg, tenant_id=str(context.tenant_id))

    return context
