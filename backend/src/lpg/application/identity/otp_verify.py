"""`VerifyOtpUseCase` — Customer/Driver OTP login, step 2.

**Creates a login only for an agency-registered customer.** When the OTP
matches and no login exists for the phone number, `CustomerLoginProvisioner`
creates one if the tenant has a customer with that number who may sign in
(`Customer.can_get_app_login`), so a customer added on the dashboard can sign
in to the Customer App straight away (ADR-051). Drivers and staff are never
created here, and open self-registration of unknown numbers is still
`FR-CM-01` scope. Verifying a correct OTP for a phone number with neither a
login nor an eligible customer raises `InvalidCredentialsError` — the same
generic message `LoginUseCase` uses, so a probing client can't distinguish
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

from lpg.application.audit import security_events as sec
from lpg.application.common.cqrs import Command
from lpg.application.common.errors import (
    InvalidCredentialsError,
    LicenseExpiredError,
    LicenseNotActivatedError,
    OtpMismatchError,
    TenantSuspendedError,
)
from lpg.application.identity.app_access import app_admits
from lpg.application.identity.otp_request import otp_store_key
from lpg.application.identity.tokens import TokenPair, issue_tokens
from lpg.domain.license.license import LicenseLifecycleState

if TYPE_CHECKING:
    import uuid
    from datetime import timedelta

    from lpg.application.audit.security_events import SecurityEventRecorder
    from lpg.application.identity.ports import (
        CustomerLoginProvisioner,
        IdentityUserRepository,
        JwtSigner,
        OtpStore,
        PermissionRepository,
        RefreshTokenRepository,
        TokenHasher,
    )
    from lpg.application.license.device_access import DeviceContext, DeviceSessionBinder
    from lpg.application.license.ports import LicenseStatusChecker
    from lpg.application.tenant.status import TenantStatusChecker


@dataclass(frozen=True, slots=True)
class VerifyOtpCommand(Command):
    tenant_id: uuid.UUID
    phone_number: str
    code: str
    #: The phone this sign-in comes from, when it is a Driver app.
    device: DeviceContext | None = None
    #: The mobile app signing in, when it says which one it is.
    app: str | None = None


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
        customer_login_provisioner: CustomerLoginProvisioner,
        refresh_token_ttl: timedelta,
        device_binder: DeviceSessionBinder | None = None,
        security_events: SecurityEventRecorder | None = None,
    ) -> None:
        self._security_events = security_events
        self._device_binder = device_binder
        self._otp_store = otp_store
        self._user_repository = user_repository
        self._refresh_token_repository = refresh_token_repository
        self._permission_repository = permission_repository
        self._token_hasher = token_hasher
        self._jwt_signer = jwt_signer
        self._license_status_checker = license_status_checker
        self._tenant_status_checker = tenant_status_checker
        self._customer_login_provisioner = customer_login_provisioner
        self._refresh_token_ttl = refresh_token_ttl

    async def _record(
        self,
        command: VerifyOtpCommand,
        outcome: str,
        user_id: uuid.UUID | None = None,
        reason: str | None = None,
    ) -> None:
        if self._security_events is None:
            return
        await self._security_events.record(
            sec.SecurityEvent(
                action=sec.OTP_LOGIN if outcome == "success" else sec.OTP_FAILED,
                outcome=outcome,
                tenant_id=command.tenant_id,
                user_id=user_id,
                subject=sec.mask_phone(command.phone_number),
                reason=reason,
            )
        )

    async def execute(self, command: VerifyOtpCommand) -> TokenPair:
        key = otp_store_key(command.tenant_id, command.phone_number)
        matched = await self._otp_store.verify(key, command.code)
        if not matched:
            await self._record(command, "failure", reason="otp_mismatch")
            msg = "The OTP entered does not match."
            raise OtpMismatchError(msg)

        user = await self._user_repository.get_by_phone_number(
            command.tenant_id, command.phone_number
        )
        # A first sign-in creates a customer login, so only an app that admits
        # customers may cause one.
        if user is None and app_admits(command.app, "customer"):
            user = await self._customer_login_provisioner.provision(
                command.tenant_id, command.phone_number
            )
        refusal = None
        if user is None or not user.is_active:
            refusal = "no_active_account"
        elif not app_admits(command.app, user.role):
            refusal = "wrong_app"
        if user is None or refusal is not None:
            # One answer for both (see `app_access`).
            await self._record(command, "failure", user.id if user else None, refusal)
            msg = "No account is associated with this number."
            raise InvalidCredentialsError(msg)

        tenant_status = await self._tenant_status_checker.get_status(command.tenant_id)
        if tenant_status in ("suspended", "closed"):
            await self._record(command, "failure", user.id, "tenant_suspended")
            msg = "This tenant's agency has been suspended."
            raise TenantSuspendedError(msg, tenant_id=str(command.tenant_id))

        license_status = await self._license_status_checker.get_status(command.tenant_id)
        if license_status is LicenseLifecycleState.PENDING_ACTIVATION:
            await self._record(command, "failure", user.id, "license_not_active")
            msg = "This tenant's license has not been activated."
            raise LicenseNotActivatedError(msg, tenant_id=str(command.tenant_id))
        if license_status in (LicenseLifecycleState.BLOCKED, LicenseLifecycleState.REVOKED):
            await self._record(command, "failure", user.id, "license_expired")
            msg = "This tenant's license has expired."
            raise LicenseExpiredError(msg, tenant_id=str(command.tenant_id))

        try:
            binding = (
                await self._device_binder.bind(user, command.device)
                if self._device_binder
                else None
            )
        except Exception as exc:
            await self._record(command, "failure", user.id, sec.reason_of(exc))
            raise

        user.record_successful_login()
        await self._user_repository.save(user)
        await self._record(command, "success", user.id)

        return await issue_tokens(
            user,
            refresh_token_repository=self._refresh_token_repository,
            permission_repository=self._permission_repository,
            token_hasher=self._token_hasher,
            jwt_signer=self._jwt_signer,
            refresh_token_ttl=self._refresh_token_ttl,
            device=binding,
        )
