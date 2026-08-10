"""The `PasswordResetToken` entity.

Simpler than `RefreshToken`: no rotation chain, just single-use-before-expiry.
`token_hash` is SHA-256 via `TokenHasher` — the raw token is only ever
delivered by email (`EmailSender`), never persisted.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from lpg.domain.common.base import Entity, InvariantViolation

if TYPE_CHECKING:
    import uuid


class PasswordResetToken(Entity):
    __slots__ = ("_expires_at", "_token_hash", "_used_at", "_user_id")

    def __init__(
        self,
        token_id: uuid.UUID,
        *,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
        used_at: datetime | None = None,
    ) -> None:
        super().__init__(token_id)
        self._user_id = user_id
        self._token_hash = token_hash
        self._expires_at = expires_at
        self._used_at = used_at

    @property
    def user_id(self) -> uuid.UUID:
        return self._user_id

    @property
    def token_hash(self) -> str:
        return self._token_hash

    @property
    def expires_at(self) -> datetime:
        return self._expires_at

    @property
    def used_at(self) -> datetime | None:
        return self._used_at

    def is_expired(self, *, now: datetime | None = None) -> bool:
        return self._expires_at <= (now or datetime.now(UTC))

    def is_usable(self, *, now: datetime | None = None) -> bool:
        return self._used_at is None and not self.is_expired(now=now)

    def mark_used(self) -> None:
        if self._used_at is not None:
            msg = "Password reset token has already been used."
            raise InvariantViolation(msg, token_id=str(self.id))
        self._used_at = datetime.now(UTC)
