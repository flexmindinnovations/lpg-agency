"""The `/platform/*` dependency chain — the control-plane sibling of
`dependencies/tenant.py`/`dependencies/unit_of_work.py`/
`dependencies/identity.py`'s `require_permission`/`require_live_permission`.

Every dependency here is built on `PlatformPrincipal`
(`application/platform/principal.py`), never `TenantContext`/
`AuthenticatedPrincipal` — a `/platform/*` route must never be reachable by
a tenant-scoped session, and a tenant-scoped route must never accept a
`PlatformPrincipal` in its place; the two dependency chains share no code
path by construction, not just by convention.

Same deliberate exception to "SQLAlchemy/infrastructure stays out of the api
layer" that `dependencies/unit_of_work.py`/`dependencies/license.py` already
carry — every type referenced by a function passed to `Depends()` is a real
import here, never `TYPE_CHECKING`-guarded.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, Callable, Coroutine
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Annotated

import structlog
from fastapi import Depends, Request

from lpg.application.common.errors import PermissionDeniedError
from lpg.application.common.ports import UnitOfWork
from lpg.application.platform.principal import PlatformPrincipal

_logger = structlog.get_logger(__name__)

#: Attributed `tenant_id` for audit-log rows written by a genuinely
#: cross-tenant platform action (list-all reads, and writes with no single
#: target tenant — e.g. creating a platform feature flag). Never a real
#: `tenant.tenant.id` (those are always `gen_random_uuid()`-generated), so
#: it can never collide with one. `RequestTenantContext.tenant_id`
#: (`application/common/ports.py::TenantContext`) is a non-optional
#: `uuid.UUID` — this sentinel exists so that contract never has to change
#: to `uuid.UUID | None` just for this one edge case. Migration
#: `63c55035ebbb`'s RLS policy on `audit.audit_log` knows this exact value
#: and only ever accepts it from a session with no `app.current_tenant_id`
#: set at all (i.e. only from this dependency's own unscoped path) — keep
#: both in sync if this ever changes.
PLATFORM_AUDIT_TENANT_ID = uuid.UUID(int=0)


async def get_platform_principal(request: Request) -> PlatformPrincipal:
    """FastAPI dependency resolving a verified `super_admin` session.

    `JwtPlatformPrincipalResolver` is constructed fresh per call, same
    reasoning `get_tenant_context` already gives for `JwtTenantResolver`:
    cheap construction, and it isn't available until the application
    lifespan has populated `AppState.jwt_signer`. Binds `user_id` into
    structlog's contextvars the same way `get_tenant_context` binds
    `tenant_id`/`user_id` — deliberately no `tenant_id` key here, since
    there is none to bind.
    """
    from lpg.api.v1.dependencies.identity import get_jwt_signer
    from lpg.infrastructure.identity.jwt_platform_principal_resolver import (
        JwtPlatformPrincipalResolver,
    )

    resolver = JwtPlatformPrincipalResolver(get_jwt_signer())
    principal = await resolver.resolve(request)
    structlog.contextvars.bind_contextvars(
        user_id=str(principal.user_id), platform_session=True
    )
    return principal


def require_platform_permission(
    permission_code: str,
) -> Callable[..., Coroutine[None, None, PlatformPrincipal]]:
    """Dependency factory: claims-based check, no I/O — the `/platform/*`
    twin of `dependencies/identity.py::require_permission`."""

    async def _dependency(
        principal: Annotated[PlatformPrincipal, Depends(get_platform_principal)],
    ) -> PlatformPrincipal:
        if permission_code not in principal.permission_codes:
            _logger.warning(
                "platform_permission_denied",
                permission_code=permission_code,
                role=principal.role,
                user_id=str(principal.user_id),
            )
            msg = f"Missing required permission: {permission_code!r}."
            raise PermissionDeniedError(msg, permission_code=permission_code)
        return principal

    return _dependency


def require_live_platform_permission(
    permission_code: str,
) -> Callable[..., Coroutine[None, None, PlatformPrincipal]]:
    """Dependency factory: claims check first, then a live re-query against
    `identity.identity_user_permission` — the `/platform/*` twin of
    `dependencies/identity.py::require_live_permission`. Every route in
    `routers/platform.py` uses this, not the claims-only variant above:
    every operation there (issue/revoke a license, suspend an agency) is
    exactly the high-sensitivity tier that check exists for.

    Deliberately does **not** reuse `PermissionChecker.has_permission_live`
    — that method is typed against `AuthenticatedPrincipal`
    (`application/identity/authorize.py`), which `PlatformPrincipal`
    doesn't structurally satisfy (no `user_display_name`). It only ever
    touches `.user_id`/`.permission_codes` at runtime, so calling
    `PermissionRepository.has_permission` directly here is the same
    behavior without the type mismatch.
    """

    async def _dependency(
        principal: Annotated[PlatformPrincipal, Depends(get_platform_principal)],
    ) -> PlatformPrincipal:
        from lpg.api.v1.dependencies.identity import get_permission_repository

        if permission_code not in principal.permission_codes:
            _logger.warning(
                "platform_permission_denied",
                permission_code=permission_code,
                role=principal.role,
                user_id=str(principal.user_id),
            )
            msg = f"Missing required permission: {permission_code!r}."
            raise PermissionDeniedError(msg, permission_code=permission_code)

        permission_repository = get_permission_repository()
        if not await permission_repository.has_permission(
            user_id=principal.user_id, permission_code=permission_code
        ):
            _logger.warning(
                "platform_permission_denied_live_recheck",
                permission_code=permission_code,
                role=principal.role,
                user_id=str(principal.user_id),
            )
            msg = f"Missing required permission: {permission_code!r}."
            raise PermissionDeniedError(msg, permission_code=permission_code)
        return principal

    return _dependency


def get_platform_unit_of_work_factory(
    principal: Annotated[PlatformPrincipal, Depends(get_platform_principal)],
) -> Callable[[uuid.UUID | None], AbstractAsyncContextManager[UnitOfWork]]:
    """Mints a `UnitOfWork` scoped to an explicit *target* tenant, supplied
    per call by the endpoint from its own path/body parameter — never
    derived from the caller's JWT, since a `PlatformPrincipal` has none.

    Pass the target `tenant_id` for a single-tenant-targeted platform write
    (issue/revoke/suspend/...) — RLS behaves exactly as it does for an
    ordinary tenant-scoped request, just keyed off the *target* tenant
    instead of the *caller*. Pass `None` for a genuinely cross-tenant read
    (list-all) — no `app.current_tenant_id` gets set at all, which is
    exactly why every list-all query in this codebase goes through a
    `SECURITY DEFINER` function (migration `fdd3afde337c`) rather than
    relying on this session to see every row on its own; an unscoped
    session sees zero rows under RLS, never every row.

    Requiring `get_platform_principal` here (only used to stamp
    `RequestTenantContext.user_id` for audit purposes on writes) keeps a
    bare `Depends(get_platform_unit_of_work_factory)` unreachable without a
    verified Super Admin session — the same defense-in-depth
    `get_unit_of_work`'s own dependency chain already gives tenant-scoped
    routes via `get_tenant_context`.
    """
    from lpg.api.app import get_app_state
    from lpg.application.common.tenant import RequestTenantContext
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

    state = get_app_state()
    database = state.database
    if database is None:
        msg = "Database is not connected — the application lifespan has not run."
        raise RuntimeError(msg)

    @asynccontextmanager
    async def _open(tenant_id: uuid.UUID | None) -> AsyncGenerator[UnitOfWork]:
        context = RequestTenantContext(
            tenant_id=tenant_id or PLATFORM_AUDIT_TENANT_ID, user_id=principal.user_id
        )
        async for session in database.open_session(tenant_id=tenant_id):
            uow = SqlAlchemyUnitOfWork(session, context, event_dispatcher=state.event_dispatcher)
            async with uow:
                yield uow

    return _open
