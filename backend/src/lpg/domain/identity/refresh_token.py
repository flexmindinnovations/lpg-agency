"""The `RefreshToken` entity — rotation-on-use, reuse-detection guard.

Not an `AggregateRoot`: it has no invariant worth recording domain events
over, just state transitions the application layer (Area B's
`RefreshTokenUseCase`) drives directly. `token_hash` is a SHA-256 hash
(`application/identity/ports.py::TokenHasher`), not the raw token — the raw
256-bit random value is never persisted.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from lpg.domain.common.base import Entity, InvariantViolation

if TYPE_CHECKING:
    import uuid


class RefreshToken(Entity):
    """One issued refresh token. `rotate()`/`revoke()` are one-way transitions."""

    __slots__ = (
        "_expires_at",
        "_issued_at",
        "_replaced_by_id",
        "_revoked_at",
        "_rotated_at",
        "_token_hash",
        "_user_id",
    )

    def __init__(
        self,
        token_id: uuid.UUID,
        *,
        user_id: uuid.UUID,
        token_hash: str,
        issued_at: datetime,
        expires_at: datetime,
        rotated_at: datetime | None = None,
        revoked_at: datetime | None = None,
        replaced_by_id: uuid.UUID | None = None,
    ) -> None:
        super().__init__(token_id)
        self._user_id = user_id
        self._token_hash = token_hash
        self._issued_at = issued_at
        self._expires_at = expires_at
        self._rotated_at = rotated_at
        self._revoked_at = revoked_at
        self._replaced_by_id = replaced_by_id

    @property
    def user_id(self) -> uuid.UUID:
        return self._user_id

    @property
    def token_hash(self) -> str:
        return self._token_hash

    @property
    def issued_at(self) -> datetime:
        return self._issued_at

    @property
    def expires_at(self) -> datetime:
        return self._expires_at

    @property
    def rotated_at(self) -> datetime | None:
        return self._rotated_at

    @property
    def revoked_at(self) -> datetime | None:
        return self._revoked_at

    @property
    def replaced_by_id(self) -> uuid.UUID | None:
        return self._replaced_by_id

    def is_expired(self, *, now: datetime | None = None) -> bool:
        return self._expires_at <= (now or datetime.now(UTC))

    def is_usable(self, *, now: datetime | None = None) -> bool:
        """A token can be redeemed for a new pair exactly once, before expiry."""
        return (
            self._rotated_at is None and self._revoked_at is None and not self.is_expired(now=now)
        )

    def rotate(self, replaced_by_id: uuid.UUID) -> None:
        """Mark this token consumed, recording which new token replaced it.

        Raises if already rotated or revoked — the domain-level guard behind
        reuse detection. A second `rotate()` call on the same token is exactly
        the "presented an already-rotated token" theft signal
        (`docs/data/17-api-security.md` §2); the application layer catches
        this and revokes the whole session, but the aggregate itself refuses
        to silently allow a double-rotation.
        """
        if self._rotated_at is not None:
            msg = "Refresh token has already been rotated."
            raise InvariantViolation(msg, token_id=str(self.id))
        if self._revoked_at is not None:
            msg = "Refresh token has already been revoked."
            raise InvariantViolation(msg, token_id=str(self.id))
        self._rotated_at = datetime.now(UTC)
        self._replaced_by_id = replaced_by_id

    def revoke(self) -> None:
        if self._revoked_at is not None:
            return
        self._revoked_at = datetime.now(UTC)
