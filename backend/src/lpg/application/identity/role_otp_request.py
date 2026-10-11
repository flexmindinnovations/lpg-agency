"""`RequestRoleOtpUseCase` — Driver/Customer App sign-in, step 1 of 2.

Like `RequestOtpUseCase`, but for one app's role only: it first confirms the
phone belongs to an active user of that role in the presented agency, then
issues and delivers the OTP and hands the plaintext code back. Step 2 is the existing
`VerifyOtpUseCase` (`POST /auth/otp/verify`), which is what issues tokens.

The code is returned so the router can echo it outside production only,
until an SMS provider exists (Phase 14); the router owns that environment
decision, not this use case.

Unlike the generic OTP request (which silently accepts any number), this
reveals whether a number is a registered user of that role, because the app needs a
visible code to show. The endpoint is rate limited at the router.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command
from lpg.application.common.errors import InvalidCredentialsError
from lpg.application.identity.otp_request import otp_store_key

if TYPE_CHECKING:
    import uuid

    from lpg.application.identity.ports import (
        IdentityUserRepository,
        OtpDeliveryPort,
        OtpStore,
    )


@dataclass(frozen=True, slots=True)
class RequestRoleOtpCommand(Command):
    tenant_id: uuid.UUID
    phone_number: str
    role: str


class RequestRoleOtpUseCase:
    def __init__(
        self,
        user_repository: IdentityUserRepository,
        otp_store: OtpStore,
        otp_delivery: OtpDeliveryPort,
    ) -> None:
        self._user_repository = user_repository
        self._otp_store = otp_store
        self._otp_delivery = otp_delivery

    async def execute(self, command: RequestRoleOtpCommand) -> str:
        user = await self._user_repository.get_by_phone_number(
            command.tenant_id, command.phone_number
        )
        if user is None or not user.is_active or user.role != command.role:
            msg = f"This number is not registered as a {command.role} for this agency."
            raise InvalidCredentialsError(msg)

        key = otp_store_key(command.tenant_id, command.phone_number)
        code = await self._otp_store.issue(key)
        await self._otp_delivery.send(command.phone_number, code)
        return code
