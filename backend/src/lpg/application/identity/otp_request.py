"""`RequestOtpUseCase` — Customer/Driver OTP login, step 1.

Rate limiting for this endpoint is enforced one layer up, at the API
dependency chain (`RateLimiter`'s existing infrastructure, whose docstring
already names "OTP requests" as an intended call site) — this use case's own
job is just generate-and-deliver.

Scoping note: `phone_number` is unique **per tenant**
(`docs/data/03-database-schema.md`), unlike email's global uniqueness — so a
tenant identifier is required here, unlike `LoginCommand`. How the mobile
app knows which tenant it belongs to is a client-bootstrapping concern
outside this use case's scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command

if TYPE_CHECKING:
    import uuid

    from lpg.application.identity.ports import OtpDeliveryPort, OtpStore


@dataclass(frozen=True, slots=True)
class RequestOtpCommand(Command):
    tenant_id: uuid.UUID
    phone_number: str


def otp_store_key(tenant_id: uuid.UUID, phone_number: str) -> str:
    """Shared by `RequestOtpUseCase` and `VerifyOtpUseCase` so both sides
    agree on the same Redis key convention (`tenant:{id}:otp:{phone}`,
    matching `IdempotencyService`/`RateLimiter`'s tenant-scoped convention).
    """
    return f"tenant:{tenant_id}:otp:{phone_number}"


class RequestOtpUseCase:
    def __init__(self, otp_store: OtpStore, otp_delivery: OtpDeliveryPort) -> None:
        self._otp_store = otp_store
        self._otp_delivery = otp_delivery

    async def execute(self, command: RequestOtpCommand) -> None:
        key = otp_store_key(command.tenant_id, command.phone_number)
        code = await self._otp_store.issue(key)
        await self._otp_delivery.send(command.phone_number, code)
