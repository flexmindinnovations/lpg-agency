"""`LogoutUseCase` — server-side refresh-token revocation.

Idempotent: logging out with an already-invalid/unknown token is not an
error — the caller's goal ("this session should no longer work") is already
satisfied.

**No `UnitOfWork`** — same reasoning as `login.py`'s module docstring.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command

if TYPE_CHECKING:
    from lpg.application.identity.ports import RefreshTokenRepository, TokenHasher


@dataclass(frozen=True, slots=True)
class LogoutCommand(Command):
    refresh_token: str


class LogoutUseCase:
    def __init__(
        self,
        refresh_token_repository: RefreshTokenRepository,
        token_hasher: TokenHasher,
    ) -> None:
        self._refresh_token_repository = refresh_token_repository
        self._token_hasher = token_hasher

    async def execute(self, command: LogoutCommand) -> None:
        token_hash = self._token_hasher.hash(command.refresh_token)
        token = await self._refresh_token_repository.get_by_token_hash(token_hash)

        if token is not None:
            token.revoke()
            await self._refresh_token_repository.save(token)
