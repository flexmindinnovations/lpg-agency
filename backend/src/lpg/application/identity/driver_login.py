"""Driver App two-step sign-in: password first, then an OTP.

Step 1 (`StartDriverLoginUseCase`) checks the driver's email and password
exactly as `LoginUseCase` does (same lockout rules, same generic
`InvalidCredentialsError`), but issues **no tokens**. It issues an OTP for
the driver's phone number instead, under a Redis key that only this step
ever writes (`driver_login_otp_key`). Step 2 (`VerifyDriverLoginUseCase`)
redeems that OTP for tokens. Because the OTP key is private to step 1, a
valid code is proof that the password step succeeded — step 2 needs no
second password and no separate challenge record.

The OTP the customer-facing `/auth/otp/*` flow issues lives under a
different key (`otp_store_key`), so the two flows cannot be used to satisfy
each other.

Like `login.py`/`otp_verify.py` this uses no `UnitOfWork`: it is
pre-authentication, so no tenant context exists yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command
from lpg.application.common.errors import (
    AccountLockedError,
    InvalidCredentialsError,
    LicenseExpiredError,
    LicenseNotActivatedError,
    OtpMismatchError,
    TenantSuspendedError,
)
from lpg.application.identity.tokens import TokenPair, issue_tokens
from lpg.domain.license.license import LicenseLifecycleState

if TYPE_CHECKING:
    import uuid
    from datetime import timedelta

    from lpg.application.identity.ports import (
        IdentityUserRepository,
        JwtSigner,
        OtpDeliveryPort,
        OtpStore,
        PasswordHasher,
        PermissionRepository,
        RefreshTokenRepository,
        TokenHasher,
    )
    from lpg.application.license.ports import LicenseStatusChecker
    from lpg.application.tenant.status import TenantStatusChecker
    from lpg.domain.identity.user import IdentityUser

_DRIVER_ROLE = "driver"
_BAD_CREDENTIALS = "Email or password is incorrect."


def driver_login_otp_key(tenant_id: uuid.UUID, user_id: uuid.UUID) -> str:
    """Redis key for the step-1 OTP. Keyed by user, not phone number, and in
    its own namespace so it never collides with `otp_store_key`.
    """
    return f"tenant:{tenant_id}:driver-login-otp:{user_id}"


def mask_phone_number(phone_number: str) -> str:
    """`+919999900099` -> `**********0099`: enough for the driver to
    recognise the number, not enough to disclose it.
    """
    return "*" * max(len(phone_number) - 4, 0) + phone_number[-4:]


async def _ensure_tenant_can_sign_in(
    tenant_id: uuid.UUID,
    tenant_status_checker: TenantStatusChecker,
    license_status_checker: LicenseStatusChecker,
) -> None:
    tenant_status = await tenant_status_checker.get_status(tenant_id)
    if tenant_status in ("suspended", "closed"):
        msg = "This tenant's agency has been suspended."
        raise TenantSuspendedError(msg, tenant_id=str(tenant_id))

    license_status = await license_status_checker.get_status(tenant_id)
    if license_status is LicenseLifecycleState.PENDING_ACTIVATION:
        msg = "This tenant's license has not been activated."
        raise LicenseNotActivatedError(msg, tenant_id=str(tenant_id))
    if license_status in (LicenseLifecycleState.BLOCKED, LicenseLifecycleState.REVOKED):
        msg = "This tenant's license has expired."
        raise LicenseExpiredError(msg, tenant_id=str(tenant_id))


def _require_active_driver(user: IdentityUser | None) -> tuple[IdentityUser, uuid.UUID]:
    # Not-a-driver reports the same as unknown-email: this endpoint must not
    # reveal which accounts exist or what role they hold.
    if user is None or user.role != _DRIVER_ROLE or user.tenant_id is None or not user.is_active:
        raise InvalidCredentialsError(_BAD_CREDENTIALS)
    return user, user.tenant_id


@dataclass(frozen=True, slots=True)
class StartDriverLoginCommand(Command):
    email: str
    password: str


@dataclass(frozen=True, slots=True)
class DriverLoginChallenge:
    """What step 1 hands back. `code` is the plaintext OTP; the API layer
    decides whether it may be shown to the client (dev mode only).
    """

    phone_hint: str
    code: str


class StartDriverLoginUseCase:
    def __init__(
        self,
        user_repository: IdentityUserRepository,
        password_hasher: PasswordHasher,
        otp_store: OtpStore,
        otp_delivery: OtpDeliveryPort,
        license_status_checker: LicenseStatusChecker,
        tenant_status_checker: TenantStatusChecker,
        *,
        lockout_threshold: int,
        lockout_duration: timedelta,
    ) -> None:
        self._user_repository = user_repository
        self._password_hasher = password_hasher
        self._otp_store = otp_store
        self._otp_delivery = otp_delivery
        self._license_status_checker = license_status_checker
        self._tenant_status_checker = tenant_status_checker
        self._lockout_threshold = lockout_threshold
        self._lockout_duration = lockout_duration

    async def execute(self, command: StartDriverLoginCommand) -> DriverLoginChallenge:
        user = await self._user_repository.get_by_email(command.email)
        if user is None or user.password_hash is None or user.role != _DRIVER_ROLE:
            raise InvalidCredentialsError(_BAD_CREDENTIALS)

        if user.is_locked():
            msg = "Account temporarily locked due to repeated failed login attempts."
            raise AccountLockedError(msg, user_id=str(user.id))

        if not self._password_hasher.verify(command.password, user.password_hash):
            user.record_failed_login(
                reason="bad_password",
                lockout_threshold=self._lockout_threshold,
                lockout_duration=self._lockout_duration,
            )
            await self._user_repository.save(user)
            raise InvalidCredentialsError(_BAD_CREDENTIALS)

        user, tenant_id = _require_active_driver(user)

        # The password is correct, so it is now safe to say what is wrong
        # with the account rather than a generic message.
        if not user.phone_number:
            msg = "This driver account has no phone number on file for the OTP."
            raise InvalidCredentialsError(msg)

        await _ensure_tenant_can_sign_in(
            tenant_id, self._tenant_status_checker, self._license_status_checker
        )

        code = await self._otp_store.issue(driver_login_otp_key(tenant_id, user.id))
        await self._otp_delivery.send(user.phone_number, code)
        return DriverLoginChallenge(phone_hint=mask_phone_number(user.phone_number), code=code)


@dataclass(frozen=True, slots=True)
class VerifyDriverLoginCommand(Command):
    email: str
    code: str


class VerifyDriverLoginUseCase:
    def __init__(
        self,
        user_repository: IdentityUserRepository,
        otp_store: OtpStore,
        refresh_token_repository: RefreshTokenRepository,
        permission_repository: PermissionRepository,
        token_hasher: TokenHasher,
        jwt_signer: JwtSigner,
        license_status_checker: LicenseStatusChecker,
        tenant_status_checker: TenantStatusChecker,
        *,
        refresh_token_ttl: timedelta,
    ) -> None:
        self._user_repository = user_repository
        self._otp_store = otp_store
        self._refresh_token_repository = refresh_token_repository
        self._permission_repository = permission_repository
        self._token_hasher = token_hasher
        self._jwt_signer = jwt_signer
        self._license_status_checker = license_status_checker
        self._tenant_status_checker = tenant_status_checker
        self._refresh_token_ttl = refresh_token_ttl

    async def execute(self, command: VerifyDriverLoginCommand) -> TokenPair:
        user, tenant_id = _require_active_driver(
            await self._user_repository.get_by_email(command.email)
        )

        matched = await self._otp_store.verify(
            driver_login_otp_key(tenant_id, user.id), command.code
        )
        if not matched:
            msg = "The OTP entered does not match."
            raise OtpMismatchError(msg)

        await _ensure_tenant_can_sign_in(
            tenant_id, self._tenant_status_checker, self._license_status_checker
        )

        user.record_successful_login()
        await self._user_repository.save(user)

        return await issue_tokens(
            user,
            refresh_token_repository=self._refresh_token_repository,
            permission_repository=self._permission_repository,
            token_hasher=self._token_hasher,
            jwt_signer=self._jwt_signer,
            refresh_token_ttl=self._refresh_token_ttl,
        )
