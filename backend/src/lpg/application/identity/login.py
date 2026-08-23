"""`LoginUseCase` — Dashboard staff username/password authentication.

**Does not use a `UnitOfWork`**, unlike `application/tenant/rename_tenant.py`
— and that's a deliberate, documented divergence, not an oversight. Every
`identity_user`/`refresh_token` access here goes through repository methods
backed by `SECURITY DEFINER` SQL functions (`migrations/versions/
fa52b77ec442_*.py`, `10a62de534be_*.py`), because login is exactly the
request that *establishes* tenant context — there is no JWT yet to resolve
one from, so the normal `get_tenant_context` → `get_unit_of_work` seam
(which Phase 6 makes tenant-mandatory, closing DW-12) structurally cannot
apply to this endpoint. Each repository write commits its own single
statement; a login attempt recording a failed count and a login attempt
issuing a token are independent pieces of state, not a multi-aggregate
transaction requiring the same atomicity BR-29's delivery-confirmation
example does.

Email is globally unique across tenants (`docs/data/03-database-schema.md`'s
`identity.identity_user.email` — a unique partial index with no per-tenant
qualifier, unlike `phone_number` which explicitly is per-tenant), so a login
by email needs no separate tenant identifier: the account found *is* the
tenant.
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
)
from lpg.application.identity.tokens import TokenPair, issue_tokens
from lpg.domain.license.license import LicenseLifecycleState

if TYPE_CHECKING:
    from datetime import timedelta

    from lpg.application.identity.ports import (
        IdentityUserRepository,
        JwtSigner,
        PasswordHasher,
        PermissionRepository,
        RefreshTokenRepository,
        TokenHasher,
    )
    from lpg.application.license.ports import LicenseStatusChecker


@dataclass(frozen=True, slots=True)
class LoginCommand(Command):
    email: str
    password: str


class LoginUseCase:
    def __init__(
        self,
        user_repository: IdentityUserRepository,
        refresh_token_repository: RefreshTokenRepository,
        permission_repository: PermissionRepository,
        password_hasher: PasswordHasher,
        token_hasher: TokenHasher,
        jwt_signer: JwtSigner,
        license_status_checker: LicenseStatusChecker,
        *,
        lockout_threshold: int,
        lockout_duration: timedelta,
        refresh_token_ttl: timedelta,
    ) -> None:
        self._user_repository = user_repository
        self._refresh_token_repository = refresh_token_repository
        self._permission_repository = permission_repository
        self._password_hasher = password_hasher
        self._token_hasher = token_hasher
        self._jwt_signer = jwt_signer
        self._license_status_checker = license_status_checker
        self._lockout_threshold = lockout_threshold
        self._lockout_duration = lockout_duration
        self._refresh_token_ttl = refresh_token_ttl

    async def execute(self, command: LoginCommand) -> TokenPair:
        user = await self._user_repository.get_by_email(command.email)

        if user is None or user.password_hash is None:
            # No user-enumeration: an unknown email and a known email with a
            # wrong password report identically.
            msg = "Email or password is incorrect."
            raise InvalidCredentialsError(msg)

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
            msg = "Email or password is incorrect."
            raise InvalidCredentialsError(msg)

        if not user.is_active:
            msg = "Email or password is incorrect."
            raise InvalidCredentialsError(msg)

        if self._password_hasher.needs_rehash(user.password_hash):
            user.change_password_hash(self._password_hasher.hash(command.password))

        # `user.tenant_id is None` is a `super_admin` account (D-01: operates
        # above tenant scope) — no single tenant's license applies to it.
        if user.tenant_id is not None:
            license_status = await self._license_status_checker.get_status(user.tenant_id)
            if license_status is LicenseLifecycleState.PENDING_ACTIVATION:
                msg = "This tenant's license has not been activated."
                raise LicenseNotActivatedError(msg, tenant_id=str(user.tenant_id))
            if license_status in (LicenseLifecycleState.BLOCKED, LicenseLifecycleState.REVOKED):
                msg = "This tenant's license has expired."
                raise LicenseExpiredError(msg, tenant_id=str(user.tenant_id))

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
