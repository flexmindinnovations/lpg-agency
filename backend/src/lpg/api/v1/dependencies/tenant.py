"""Tenant context dependency.

Wires a ``TenantResolver`` (infrastructure) into FastAPI's dependency system,
producing a ``TenantContext`` every downstream dependency and use case depends
on. Phase 2 binds the interim ``HeaderTenantResolver``; Phase 6 rebinds this
one function to a ``JwtTenantResolver`` and nothing downstream changes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from lpg.infrastructure.tenant.header_resolver import HeaderTenantResolver

if TYPE_CHECKING:
    from fastapi import Request

    from lpg.application.common.ports import TenantContext, TenantResolver

# Module-level: the resolver carries no per-request state, so there is
# nothing to gain from reconstructing it on every call. Phase 6 replaces this
# binding, not the dependency function's signature or callers.
_resolver: TenantResolver = HeaderTenantResolver()


async def get_tenant_context(request: Request) -> TenantContext:
    """FastAPI dependency resolving the current request's tenant context.

    Binds ``tenant_id``/``user_id`` into structlog's contextvars once
    resolved — every log line for the rest of this request carries them
    automatically, the same mechanism ``CorrelationIdMiddleware`` already
    uses for ``correlation_id`` (``03-backend-architecture.md`` §10: "every
    log entry carries... correlation_id, tenant_id, user_id"). Bound here,
    not in the middleware, because the middleware runs before authentication
    resolves a tenant — there is nothing to bind yet at that point.
    """
    context = await _resolver.resolve(request)
    structlog.contextvars.bind_contextvars(
        tenant_id=str(context.tenant_id),
        user_id=str(context.user_id) if context.user_id else None,
    )
    return context
