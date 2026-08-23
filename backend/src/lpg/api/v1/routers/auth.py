"""Authentication endpoints — the first router this codebase mounts under
`settings.api_v1_prefix` (Phase 6, ADR-035).

Refresh-token delivery is client-dependent: the Dashboard (browser) gets it
via an `HttpOnly`/`Secure`/`SameSite=Strict` cookie so JavaScript never
touches it; mobile clients, which can't rely on a cookie the same way,
also receive it in the JSON body (`docs/data/17-api-security.md` §2). Both
forms are set/read on every endpoint that issues or consumes a refresh
token, never just one.

**Every type used inside `Annotated[X, Depends(...)]` below is a real
import, never `TYPE_CHECKING`-guarded** — found the hard way, by a failing
end-to-end test: with `from __future__ import annotations`, FastAPI
resolves a route function's annotations via `typing.get_type_hints()` at
request time. If any name in that function's signature only exists under
`TYPE_CHECKING`, resolution raises `NameError` for the *whole* function,
and FastAPI silently falls back to treating every parameter as a plain
(non-dependency) field — every dependency-injected argument then shows up
as "required" in the 422 response, with no explicit link back to the cause.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from lpg.api.v1.dependencies.identity import (
    get_current_principal,
    get_email_sender,
    get_identity_user_repository,
    get_jwt_signer,
    get_otp_delivery,
    get_otp_store,
    get_password_hasher,
    get_password_reset_token_repository,
    get_permission_repository,
    get_refresh_token_repository,
    get_tenant_slug_resolver,
    get_token_hasher,
    require_rate_limit,
)
from lpg.api.v1.dependencies.license import get_license_status_checker
from lpg.api.v1.schemas.identity import (
    LoginRequest,
    LogoutRequest,
    OtpRequestRequest,
    OtpVerifyRequest,
    PasswordForgotRequest,
    PasswordResetRequest,
    PrincipalResponse,
    RefreshRequest,
    TokenResponse,
)
from lpg.application.common.errors import RefreshTokenInvalidError
from lpg.application.identity.login import LoginCommand, LoginUseCase
from lpg.application.identity.logout import LogoutCommand, LogoutUseCase
from lpg.application.identity.otp_request import RequestOtpCommand, RequestOtpUseCase
from lpg.application.identity.otp_verify import VerifyOtpCommand, VerifyOtpUseCase
from lpg.application.identity.password_reset import (
    ConfirmPasswordResetCommand,
    ConfirmPasswordResetUseCase,
    RequestPasswordResetCommand,
    RequestPasswordResetUseCase,
)
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
from lpg.application.identity.refresh_token import RefreshTokenCommand, RefreshTokenUseCase
from lpg.application.identity.tokens import TokenPair
from lpg.application.license.ports import LicenseStatusChecker
from lpg.config.settings import Settings, get_settings

router = APIRouter(prefix="/auth", tags=["Authentication"])

_REFRESH_COOKIE_NAME = "lpg_refresh_token"


async def _resolve_tenant_id(raw: str, tenant_slug_resolver: TenantSlugResolver) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError:
        pass

    tenant_id = await tenant_slug_resolver.resolve(raw)
    if tenant_id is None:
        raise HTTPException(status_code=400, detail="Invalid agency code.")
    return tenant_id


def _set_refresh_cookie(response: Response, token_pair: TokenPair, settings: Settings) -> None:
    response.set_cookie(
        key=_REFRESH_COOKIE_NAME,
        value=token_pair.refresh_token,
        max_age=settings.refresh_token_ttl_days * 24 * 60 * 60,
        httponly=True,
        secure=not settings.is_local,
        samesite="strict",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=_REFRESH_COOKIE_NAME)


def _resolve_refresh_token(request: Request, body_token: str | None) -> str | None:
    """The cookie wins when both are present — a mobile client that also
    happened to receive a cookie (it shouldn't, but nothing prevents it)
    must not have its own explicit token silently ignored in favour of a
    stale cookie from a previous session on the same device.
    """
    return body_token or request.cookies.get(_REFRESH_COOKIE_NAME)


@router.post("/login", response_model=TokenResponse, summary="Dashboard staff login")
async def login(
    body: LoginRequest,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    user_repository: Annotated[IdentityUserRepository, Depends(get_identity_user_repository)],
    refresh_token_repository: Annotated[
        RefreshTokenRepository, Depends(get_refresh_token_repository)
    ],
    permission_repository: Annotated[PermissionRepository, Depends(get_permission_repository)],
    password_hasher: Annotated[PasswordHasher, Depends(get_password_hasher)],
    token_hasher: Annotated[TokenHasher, Depends(get_token_hasher)],
    jwt_signer: Annotated[JwtSigner, Depends(get_jwt_signer)],
    license_status_checker: Annotated[LicenseStatusChecker, Depends(get_license_status_checker)],
    _rate_limit: Annotated[
        None,
        Depends(require_rate_limit(key_prefix="auth:login", limit=10, window_seconds=60)),
    ],
) -> TokenResponse:
    use_case = LoginUseCase(
        user_repository,
        refresh_token_repository,
        permission_repository,
        password_hasher,
        token_hasher,
        jwt_signer,
        license_status_checker,
        lockout_threshold=settings.login_lockout_threshold,
        lockout_duration=timedelta(minutes=settings.login_lockout_duration_minutes),
        refresh_token_ttl=timedelta(days=settings.refresh_token_ttl_days),
    )
    token_pair = await use_case.execute(LoginCommand(email=body.email, password=body.password))
    _set_refresh_cookie(response, token_pair, settings)
    return TokenResponse(
        access_token=token_pair.access_token, refresh_token=token_pair.refresh_token
    )


@router.post("/otp/request", status_code=204, summary="Request an OTP for Customer/Driver login")
async def otp_request(
    body: OtpRequestRequest,
    otp_store: Annotated[OtpStore, Depends(get_otp_store)],
    otp_delivery: Annotated[OtpDeliveryPort, Depends(get_otp_delivery)],
    tenant_slug_resolver: Annotated[TenantSlugResolver, Depends(get_tenant_slug_resolver)],
    _rate_limit: Annotated[
        None,
        Depends(require_rate_limit(key_prefix="auth:otp_request", limit=5, window_seconds=3600)),
    ],
) -> None:
    tenant_uuid = await _resolve_tenant_id(body.tenant_id, tenant_slug_resolver)
    use_case = RequestOtpUseCase(otp_store, otp_delivery)
    await use_case.execute(RequestOtpCommand(tenant_id=tenant_uuid, phone_number=body.phone_number))


@router.post("/otp/verify", response_model=TokenResponse, summary="Verify an OTP and log in")
async def otp_verify(
    body: OtpVerifyRequest,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    otp_store: Annotated[OtpStore, Depends(get_otp_store)],
    user_repository: Annotated[IdentityUserRepository, Depends(get_identity_user_repository)],
    refresh_token_repository: Annotated[
        RefreshTokenRepository, Depends(get_refresh_token_repository)
    ],
    permission_repository: Annotated[PermissionRepository, Depends(get_permission_repository)],
    token_hasher: Annotated[TokenHasher, Depends(get_token_hasher)],
    jwt_signer: Annotated[JwtSigner, Depends(get_jwt_signer)],
    tenant_slug_resolver: Annotated[TenantSlugResolver, Depends(get_tenant_slug_resolver)],
    license_status_checker: Annotated[LicenseStatusChecker, Depends(get_license_status_checker)],
) -> TokenResponse:
    use_case = VerifyOtpUseCase(
        otp_store,
        user_repository,
        refresh_token_repository,
        permission_repository,
        token_hasher,
        jwt_signer,
        license_status_checker,
        refresh_token_ttl=timedelta(days=settings.refresh_token_ttl_days),
    )
    tenant_uuid = await _resolve_tenant_id(body.tenant_id, tenant_slug_resolver)
    token_pair = await use_case.execute(
        VerifyOtpCommand(tenant_id=tenant_uuid, phone_number=body.phone_number, code=body.code)
    )
    _set_refresh_cookie(response, token_pair, settings)
    return TokenResponse(
        access_token=token_pair.access_token, refresh_token=token_pair.refresh_token
    )


@router.post("/refresh", response_model=TokenResponse, summary="Exchange a refresh token")
async def refresh(
    body: RefreshRequest,
    request: Request,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    refresh_token_repository: Annotated[
        RefreshTokenRepository, Depends(get_refresh_token_repository)
    ],
    user_repository: Annotated[IdentityUserRepository, Depends(get_identity_user_repository)],
    permission_repository: Annotated[PermissionRepository, Depends(get_permission_repository)],
    token_hasher: Annotated[TokenHasher, Depends(get_token_hasher)],
    jwt_signer: Annotated[JwtSigner, Depends(get_jwt_signer)],
    license_status_checker: Annotated[LicenseStatusChecker, Depends(get_license_status_checker)],
) -> TokenResponse:
    raw_token = _resolve_refresh_token(request, body.refresh_token)
    if raw_token is None:
        msg = "Session expired or invalid. Please log in again."
        raise RefreshTokenInvalidError(msg)

    use_case = RefreshTokenUseCase(
        refresh_token_repository,
        user_repository,
        permission_repository,
        token_hasher,
        jwt_signer,
        license_status_checker,
        refresh_token_ttl=timedelta(days=settings.refresh_token_ttl_days),
    )
    token_pair = await use_case.execute(RefreshTokenCommand(refresh_token=raw_token))
    _set_refresh_cookie(response, token_pair, settings)
    return TokenResponse(
        access_token=token_pair.access_token, refresh_token=token_pair.refresh_token
    )


@router.post("/logout", status_code=204, summary="Revoke the current refresh token")
async def logout(
    body: LogoutRequest,
    request: Request,
    response: Response,
    refresh_token_repository: Annotated[
        RefreshTokenRepository, Depends(get_refresh_token_repository)
    ],
    token_hasher: Annotated[TokenHasher, Depends(get_token_hasher)],
) -> None:
    raw_token = _resolve_refresh_token(request, body.refresh_token)
    if raw_token is not None:
        use_case = LogoutUseCase(refresh_token_repository, token_hasher)
        await use_case.execute(LogoutCommand(refresh_token=raw_token))
    _clear_refresh_cookie(response)


@router.post("/password/forgot", status_code=204, summary="Request a password reset email")
async def password_forgot(
    body: PasswordForgotRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    user_repository: Annotated[IdentityUserRepository, Depends(get_identity_user_repository)],
    reset_token_repository: Annotated[
        PasswordResetTokenRepository, Depends(get_password_reset_token_repository)
    ],
    token_hasher: Annotated[TokenHasher, Depends(get_token_hasher)],
    email_sender: Annotated[EmailSender, Depends(get_email_sender)],
    _rate_limit: Annotated[
        None,
        Depends(
            require_rate_limit(key_prefix="auth:password_forgot", limit=5, window_seconds=3600)
        ),
    ],
) -> None:
    use_case = RequestPasswordResetUseCase(
        user_repository,
        reset_token_repository,
        token_hasher,
        email_sender,
        reset_token_ttl=timedelta(seconds=settings.password_reset_token_ttl_seconds),
    )
    # Always 204, regardless of whether the email matched an account — the
    # use case itself already guarantees no user-enumeration; the router
    # doesn't need its own branch to preserve that.
    await use_case.execute(RequestPasswordResetCommand(email=body.email))


@router.post("/password/reset", status_code=204, summary="Confirm a password reset")
async def password_reset(
    body: PasswordResetRequest,
    reset_token_repository: Annotated[
        PasswordResetTokenRepository, Depends(get_password_reset_token_repository)
    ],
    user_repository: Annotated[IdentityUserRepository, Depends(get_identity_user_repository)],
    token_hasher: Annotated[TokenHasher, Depends(get_token_hasher)],
    password_hasher: Annotated[PasswordHasher, Depends(get_password_hasher)],
) -> None:
    use_case = ConfirmPasswordResetUseCase(
        reset_token_repository, user_repository, token_hasher, password_hasher
    )
    await use_case.execute(
        ConfirmPasswordResetCommand(reset_token=body.reset_token, new_password=body.new_password)
    )


@router.get("/me", response_model=PrincipalResponse, summary="The current authenticated principal")
async def me(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    user_repository: Annotated[IdentityUserRepository, Depends(get_identity_user_repository)],
) -> PrincipalResponse:
    email = None
    if principal.user_id is not None:
        user = await user_repository.get(principal.user_id)
        email = user.email if user else None
    return PrincipalResponse(
        user_id=str(principal.user_id) if principal.user_id else "",
        tenant_id=str(principal.tenant_id),
        role=principal.role,
        permissions=sorted(principal.permission_codes),
        email=email,
    )
