"""`RefreshTokenUseCase` — exchange a refresh token for a new access+refresh pair.

Reuse-of-an-already-rotated-token detection mirrors
`IdempotencyService`'s claim/replay/conflict shape: a token presented a
second time after it was already rotated is the theft signal
`docs/data/17-api-security.md` §2 describes, and the response is the same
either way (`RefreshTokenInvalidError`) — a client cannot distinguish
"never valid" from "valid but reused," and shouldn't be able to.

**No `UnitOfWork`** — same reasoning as `login.py`'s module docstring. A
presented refresh token is, by definition, evaluated before any tenant
context can be resolved from it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command
from lpg.application.common.errors import (
    LicenseExpiredError,
    LicenseNotActivatedError,
    RefreshTokenInvalidError,
)
from lpg.application.identity.tokens import TokenPair, issue_tokens
from lpg.domain.license.license import LicenseLifecycleState

if TYPE_CHECKING:
    from datetime import timedelta

    from lpg.application.identity.ports import (
        IdentityUserRepository,
        JwtSigner,
        PermissionRepository,
        RefreshTokenRepository,
        TokenHasher,
    )
    from lpg.application.license.ports import LicenseStatusChecker


@dataclass(frozen=True, slots=True)
class RefreshTokenCommand(Command):
    refresh_token: str


class RefreshTokenUseCase:
    def __init__(
        self,
        refresh_token_repository: RefreshTokenRepository,
        user_repository: IdentityUserRepository,
        permission_repository: PermissionRepository,
        token_hasher: TokenHasher,
        jwt_signer: JwtSigner,
        license_status_checker: LicenseStatusChecker,
        *,
        refresh_token_ttl: timedelta,
    ) -> None:
        self._refresh_token_repository = refresh_token_repository
        self._user_repository = user_repository
        self._permission_repository = permission_repository
        self._token_hasher = token_hasher
        self._jwt_signer = jwt_signer
        self._license_status_checker = license_status_checker
        self._refresh_token_ttl = refresh_token_ttl

    async def execute(self, command: RefreshTokenCommand) -> TokenPair:
        token_hash = self._token_hasher.hash(command.refresh_token)
        token = await self._refresh_token_repository.get_by_token_hash(token_hash)

        if token is None:
            msg = "Session expired or invalid. Please log in again."
            raise RefreshTokenInvalidError(msg)

        if token.rotated_at is not None:
            # Reuse of an already-rotated token — treat as theft, revoke the
            # whole session, not just this one token.
            await self._refresh_token_repository.revoke_all_for_user(token.user_id)
            msg = "Session expired or invalid. Please log in again."
            raise RefreshTokenInvalidError(msg)

        if not token.is_usable():
            msg = "Session expired or invalid. Please log in again."
            raise RefreshTokenInvalidError(msg)

        user = await self._user_repository.get(token.user_id)
        if user is None or not user.is_active:
            msg = "Session expired or invalid. Please log in again."
            raise RefreshTokenInvalidError(msg)

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

        new_pair = await issue_tokens(
            user,
            refresh_token_repository=self._refresh_token_repository,
            permission_repository=self._permission_repository,
            token_hasher=self._token_hasher,
            jwt_signer=self._jwt_signer,
            refresh_token_ttl=self._refresh_token_ttl,
        )
        token.rotate(new_pair.refresh_token_id)
        await self._refresh_token_repository.save(token)

        return new_pair
