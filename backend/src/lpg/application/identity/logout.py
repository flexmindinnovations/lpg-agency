"""`LogoutUseCase` — server-side refresh-token revocation.

Idempotent: logging out with an already-invalid/unknown token is not an
error — the caller's goal ("this session should no longer work") is already
satisfied.

**No `UnitOfWork`** — same reasoning as `login.py`'s module docstring.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.application.audit import security_events as sec
from lpg.application.common.cqrs import Command

if TYPE_CHECKING:
    from lpg.application.audit.security_events import SecurityEventRecorder
    from lpg.application.identity.ports import (
        IdentityUserRepository,
        RefreshTokenRepository,
        TokenHasher,
    )


@dataclass(frozen=True, slots=True)
class LogoutCommand(Command):
    refresh_token: str


class LogoutUseCase:
    def __init__(
        self,
        refresh_token_repository: RefreshTokenRepository,
        token_hasher: TokenHasher,
        security_events: SecurityEventRecorder | None = None,
        user_lookup: IdentityUserRepository | None = None,
    ) -> None:
        self._security_events = security_events
        self._user_lookup = user_lookup
        self._refresh_token_repository = refresh_token_repository
        self._token_hasher = token_hasher

    async def execute(self, command: LogoutCommand) -> None:
        token_hash = self._token_hasher.hash(command.refresh_token)
        token = await self._refresh_token_repository.get_by_token_hash(token_hash)

        if token is not None:
            token.revoke()
            await self._refresh_token_repository.save(token)
            if self._security_events is not None:
                user = await self._user_lookup.get(token.user_id) if self._user_lookup else None
                await self._security_events.record(
                    sec.SecurityEvent(
                        action=sec.LOGOUT,
                        outcome="success",
                        tenant_id=user.tenant_id if user else None,
                        user_id=token.user_id,
                    )
                )
