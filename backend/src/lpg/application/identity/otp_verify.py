"""`VerifyOtpUseCase` — Customer/Driver OTP login, step 2.

**Does not create accounts.** Phase 6 authenticates users that already
exist (seeded via `backend/scripts/seed_identity_users.py` for
verification); real customer/driver self-registration is Phase 8/11+
scope (`FR-CM-01`). Verifying a correct OTP for a phone number with no
matching account raises `InvalidCredentialsError` — the same generic
message `LoginUseCase` uses, so a probing client can't distinguish
"wrong code" from "no such account" from the response alone.

**No `UnitOfWork`** — same reasoning as `login.py`'s module docstring.
`get_by_phone_number` *is* tenant-scoped (the client supplies `tenant_id`
directly), but is still routed through the same `SECURITY DEFINER`-backed
repository as `get_by_email` for consistency and because the user isn't
resolved yet at the point of the OTP-store check.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command
from lpg.application.common.errors import (
    InvalidCredentialsError,
    LicenseExpiredError,
    LicenseNotActivatedError,
    OtpMismatchError,
    TenantSuspendedError,
)
from lpg.application.identity.otp_request import otp_store_key
from lpg.application.identity.tokens import TokenPair, issue_tokens
from lpg.domain.license.license import LicenseLifecycleState

if TYPE_CHECKING:
    import uuid
    from datetime import timedelta

    from lpg.application.identity.ports import (
        IdentityUserRepository,
        JwtSigner,
        OtpStore,
        PermissionRepository,
        RefreshTokenRepository,
        TokenHasher,
    )
    from lpg.application.license.ports import LicenseStatusChecker
    from lpg.application.tenant.status import TenantStatusChecker


@dataclass(frozen=True, slots=True)
class VerifyOtpCommand(Command):
    tenant_id: uuid.UUID
    phone_number: str
    code: str


class VerifyOtpUseCase:
    def __init__(
        self,
        otp_store: OtpStore,
        user_repository: IdentityUserRepository,
        refresh_token_repository: RefreshTokenRepository,
        permission_repository: PermissionRepository,
        token_hasher: TokenHasher,
        jwt_signer: JwtSigner,
        license_status_checker: LicenseStatusChecker,
        tenant_status_checker: TenantStatusChecker,
        *,
        refresh_token_ttl: timedelta,
    ) -> None:
        self._otp_store = otp_store
        self._user_repository = user_repository
        self._refresh_token_repository = refresh_token_repository
        self._permission_repository = permission_repository
        self._token_hasher = token_hasher
        self._jwt_signer = jwt_signer
        self._license_status_checker = license_status_checker
        self._tenant_status_checker = tenant_status_checker
        self._refresh_token_ttl = refresh_token_ttl

    async def execute(self, command: VerifyOtpCommand) -> TokenPair:
        key = otp_store_key(command.tenant_id, command.phone_number)
        matched = await self._otp_store.verify(key, command.code)
        if not matched:
            msg = "The OTP entered does not match."
            raise OtpMismatchError(msg)

        user = await self._user_repository.get_by_phone_number(
            command.tenant_id, command.phone_number
        )
        if user is None or not user.is_active:
            msg = "No account is associated with this number."
            raise InvalidCredentialsError(msg)

        tenant_status = await self._tenant_status_checker.get_status(command.tenant_id)
        if tenant_status in ("suspended", "closed"):
            msg = "This tenant's agency has been suspended."
            raise TenantSuspendedError(msg, tenant_id=str(command.tenant_id))

        license_status = await self._license_status_checker.get_status(command.tenant_id)
        if license_status is LicenseLifecycleState.PENDING_ACTIVATION:
            msg = "This tenant's license has not been activated."
            raise LicenseNotActivatedError(msg, tenant_id=str(command.tenant_id))
        if license_status in (LicenseLifecycleState.BLOCKED, LicenseLifecycleState.REVOKED):
            msg = "This tenant's license has expired."
            raise LicenseExpiredError(msg, tenant_id=str(command.tenant_id))

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
