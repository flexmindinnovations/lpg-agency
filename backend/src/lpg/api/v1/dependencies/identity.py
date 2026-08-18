"""Identity dependencies — `AuthenticatedPrincipal`, permission checks, and
the concrete infra pieces (`JwtSigner`, `PasswordHasher`, repositories) use
cases need, pulled from `AppState`.

Same deliberate exception to "SQLAlchemy/infrastructure stays out of the
api layer" that `dependencies/unit_of_work.py` already carries — this is a
dependency-wiring module, exactly where the API layer is allowed to know
concrete infrastructure types exist (see the `ignore_imports` entries in
`pyproject.toml`).

**Every type referenced by a function FastAPI actually inspects via
`Depends()` — i.e. a function passed *as* a `Depends()` argument somewhere
— is a real import here, never `TYPE_CHECKING`-guarded.** See
`api/v1/routers/auth.py`'s module docstring for why: with `from __future__
import annotations`, an unresolvable name anywhere in such a function's
signature breaks `Depends()` resolution for that whole function silently,
not loudly. `AppState`/`Settings`/`Database` stay `TYPE_CHECKING`-guarded
below on purpose — they appear only on the *private* `_get_app_state_and_
settings`/`_get_database` helpers, which are called directly, never passed
to `Depends()`, so FastAPI never inspects them (and a real, module-level
`AppState` import here would both reintroduce the `lpg.api.app` import-time
side effect every other dependency module in this package defers, and
create a circular import: `lpg.api.app` → `routers.auth` →
`dependencies.identity` → `lpg.api.app`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, cast

from fastapi import Depends, Request

from lpg.api.v1.dependencies.tenant import get_tenant_context
from lpg.application.common.errors import PermissionDeniedError
from lpg.application.common.ports import TenantContext
from lpg.application.identity.authorize import PermissionChecker
from lpg.application.identity.ports import (
    AuthenticatedPrincipal,
    EmailSender,
    IdentityUserRepository,
    JwtSigner,
    OtpDeliveryPort,
    OtpStore,
    PasswordHasher,
    PasswordResetTokenRepository,
    PermissionRepository,
    RefreshTokenRepository,
    TenantSlugResolver,
    TokenHasher,
)
from lpg.config.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from lpg.api.app import AppState
    from lpg.config.settings import Settings
    from lpg.infrastructure.persistence.database import Database

_logger = get_logger(__name__)


def require_rate_limit(
    *, key_prefix: str, limit: int, window_seconds: int
) -> Callable[[Request], Coroutine[None, None, None]]:
    """Dependency factory wrapping the existing `RateLimiter`
    (`infrastructure/rate_limit/limiter.py`, whose own docstring already
    names "login, OTP requests, password reset" as intended call sites).

    Keyed by client IP rather than tenant/user: login and OTP-request are
    exactly the endpoints reached *before* either is known. Real client IP
    behind a reverse proxy needs `X-Forwarded-For` handling — deferred with
    the hosting-topology decision (ADR-022), same as this project's other
    proxy-dependent concerns.
    """

    async def _dependency(request: Request) -> None:
        from lpg.infrastructure.rate_limit.limiter import RateLimiter

        state, _settings = _get_app_state_and_settings()
        if state.redis is None:
            # No Redis at all is a startup-configuration problem elsewhere
            # (readiness already reports it) — never block an auth attempt
            # on it here, matching RateLimiter's own fail-open philosophy
            # for outages (`docs/data/17-api-security.md` §8).
            return

        client_host = request.client.host if request.client else "unknown"
        limiter = RateLimiter(state.redis)
        await limiter.enforce(
            key=f"{key_prefix}:{client_host}",
            limit=limit,
            window_seconds=window_seconds,
        )

    return _dependency


def get_current_principal(
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
) -> AuthenticatedPrincipal:
    """Thin cast: `get_tenant_context` always resolves a
    `JwtAuthenticatedPrincipal` via `JwtTenantResolver` in this phase — it
    structurally satisfies both `TenantContext` and the richer
    `AuthenticatedPrincipal` (`role`, `permission_codes`), so this is a type
    narrowing, not a runtime conversion.
    """
    return cast("AuthenticatedPrincipal", tenant_context)


def require_permission(
    permission_code: str,
) -> Callable[..., Coroutine[None, None, AuthenticatedPrincipal]]:
    """Dependency factory: claims-based check, no I/O. Correct for the vast
    majority of endpoints — staleness is bounded by the 15-minute access
    -token lifetime (`docs/data/17-api-security.md` §4/§7).
    """

    async def _dependency(
        principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    ) -> AuthenticatedPrincipal:
        if permission_code not in principal.permission_codes:
            _logger.warning(
                "permission_denied",
                permission_code=permission_code,
                role=principal.role,
                user_id=str(principal.user_id),
            )
            msg = f"Missing required permission: {permission_code!r}."
            msg = (
                f"DEBUG FAIL: \n"
                f"Checking for: {permission_code!r} (type: {type(permission_code)})\n"
                f"Against: {principal.permission_codes!r} (type: {type(principal.permission_codes)})"
            )
            raise PermissionDeniedError(msg, permission_code=permission_code)
        return principal

    return _dependency


def require_permission_or_self(
    permission_code: str,
    user_id_param: str = "customer_id",
) -> Callable[..., Coroutine[None, None, AuthenticatedPrincipal]]:
    """Dependency factory: grants access if the `user_id_param` path parameter
    matches the current principal's `user_id`, OR if the principal holds the
    required `permission_code`. Used for endpoints where a customer can
    read/update their own data without needing global agency permissions.
    """

    async def _dependency(
        request: Request,
        principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    ) -> AuthenticatedPrincipal:
        path_user_id = request.path_params.get(user_id_param)
        if path_user_id and str(principal.user_id) == path_user_id:
            return principal

        if permission_code not in principal.permission_codes:
            _logger.warning(
                "permission_denied",
                permission_code=permission_code,
                role=principal.role,
                user_id=str(principal.user_id),
                path_user_id=path_user_id,
            )
            msg = f"Missing required permission: {permission_code!r} or must be the owner."
            raise PermissionDeniedError(msg, permission_code=permission_code)
        return principal

    return _dependency


def require_live_permission(
    permission_code: str,
) -> Callable[..., Coroutine[None, None, AuthenticatedPrincipal]]:
    """Dependency factory for the four high-sensitivity actions
    (`docs/data/17-api-security.md` §7): claims check first (fails fast for
    an obviously-unauthorized role), then a live re-query against
    `identity.role_permission` — claim staleness (up to 15 minutes) is
    judged unacceptable for these specifically.
    """

    async def _dependency(
        principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
        permission_checker: Annotated[
            PermissionChecker, Depends(get_permission_checker)
        ],
    ) -> AuthenticatedPrincipal:
        if permission_code not in principal.permission_codes:
            _logger.warning(
                "permission_denied",
                permission_code=permission_code,
                role=principal.role,
                user_id=str(principal.user_id),
            )
            msg = f"Missing required permission: {permission_code!r}."
            raise PermissionDeniedError(msg, permission_code=permission_code)

        if not await permission_checker.has_permission_live(principal, permission_code):
            _logger.warning(
                "permission_denied_live_recheck",
                permission_code=permission_code,
                role=principal.role,
                user_id=str(principal.user_id),
            )
            msg = f"Missing required permission: {permission_code!r}."
            raise PermissionDeniedError(msg, permission_code=permission_code)
        return principal

    return _dependency


def _get_app_state_and_settings() -> tuple[AppState, Settings]:
    """Deferred import, same reason as `dependencies/unit_of_work.py`:
    `lpg.api.app` has a module-level `app = create_app()` side effect that
    must not run at import time here.
    """
    from lpg.api.app import get_app_state
    from lpg.config.settings import get_settings

    return get_app_state(), get_settings()


def get_jwt_signer() -> JwtSigner:
    state, _settings = _get_app_state_and_settings()
    if state.jwt_signer is None:
        msg = "JwtSigner is not configured — the application lifespan has not run."
        raise RuntimeError(msg)
    return state.jwt_signer


def get_password_hasher() -> PasswordHasher:
    state, _settings = _get_app_state_and_settings()
    if state.password_hasher is None:
        msg = "PasswordHasher is not configured — the application lifespan has not run."
        raise RuntimeError(msg)
    return state.password_hasher


def get_token_hasher() -> TokenHasher:
    from lpg.infrastructure.identity.token_hasher import Sha256TokenHasher

    # Stateless, cheap to construct — no reason to hold this in AppState.
    return Sha256TokenHasher()


def get_otp_store() -> OtpStore:
    state, settings = _get_app_state_and_settings()
    from lpg.infrastructure.identity.otp_service import OtpService

    if state.redis is None:
        msg = "RedisClient is not configured — the application lifespan has not run."
        raise RuntimeError(msg)
    return OtpService(state.redis, settings)


def get_otp_delivery() -> OtpDeliveryPort:
    from lpg.infrastructure.identity.otp_delivery import LoggingOtpDelivery

    # Only implementation that exists — a real SMS provider is Phase 14
    # scope. `Settings.otp_delivery_dev_mode` is rejected outright outside
    # local/dev by `model_post_init`, so this being reachable at all in a
    # real environment would already have failed loudly at startup.
    return LoggingOtpDelivery()


def get_email_sender() -> EmailSender:
    from lpg.infrastructure.identity.email_sender import LoggingEmailSender

    return LoggingEmailSender()


def _get_database() -> Database:
    state, _settings = _get_app_state_and_settings()
    if state.database is None:
        msg = "Database is not configured — the application lifespan has not run."
        raise RuntimeError(msg)
    return state.database


def get_identity_user_repository() -> IdentityUserRepository:
    from lpg.infrastructure.persistence.repositories.identity import (
        SqlAlchemyIdentityUserRepository,
    )

    return SqlAlchemyIdentityUserRepository(_get_database())


def get_refresh_token_repository() -> RefreshTokenRepository:
    from lpg.infrastructure.persistence.repositories.identity import (
        SqlAlchemyRefreshTokenRepository,
    )

    return SqlAlchemyRefreshTokenRepository(_get_database())


def get_password_reset_token_repository() -> PasswordResetTokenRepository:
    from lpg.infrastructure.persistence.repositories.identity import (
        SqlAlchemyPasswordResetTokenRepository,
    )

    return SqlAlchemyPasswordResetTokenRepository(_get_database())


def get_permission_repository() -> PermissionRepository:
    from lpg.infrastructure.persistence.repositories.identity import (
        SqlAlchemyPermissionRepository,
    )

    return SqlAlchemyPermissionRepository(_get_database())


def get_tenant_slug_resolver() -> TenantSlugResolver:
    from lpg.infrastructure.identity.tenant_slug_resolver import SqlAlchemyTenantSlugResolver

    return SqlAlchemyTenantSlugResolver(_get_database())


def get_permission_checker(
    permission_repository: Annotated[
        PermissionRepository, Depends(get_permission_repository)
    ],
) -> PermissionChecker:
    from lpg.application.identity.authorize import PermissionChecker

    return PermissionChecker(permission_repository)
