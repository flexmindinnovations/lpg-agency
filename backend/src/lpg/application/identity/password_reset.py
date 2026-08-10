"""`RequestPasswordResetUseCase` / `ConfirmPasswordResetUseCase`.

`RequestPasswordResetUseCase` always completes successfully regardless of
whether the email matches an account — the router returns the same generic
"if an account exists, an email was sent" response either way. No
user-enumeration through timing or response shape.

**No `UnitOfWork`** — same reasoning as `login.py`'s module docstring: both
use cases resolve identity from an as-yet-unauthenticated input (an email,
or a bare reset token), before any tenant context exists.
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command
from lpg.application.common.errors import ResetTokenExpiredError
from lpg.domain.identity.password_reset_token import PasswordResetToken

if TYPE_CHECKING:
    from lpg.application.identity.ports import (
        EmailSender,
        IdentityUserRepository,
        PasswordHasher,
        PasswordResetTokenRepository,
        TokenHasher,
    )


@dataclass(frozen=True, slots=True)
class RequestPasswordResetCommand(Command):
    email: str


class RequestPasswordResetUseCase:
    def __init__(
        self,
        user_repository: IdentityUserRepository,
        reset_token_repository: PasswordResetTokenRepository,
        token_hasher: TokenHasher,
        email_sender: EmailSender,
        *,
        reset_token_ttl: timedelta,
    ) -> None:
        self._user_repository = user_repository
        self._reset_token_repository = reset_token_repository
        self._token_hasher = token_hasher
        self._email_sender = email_sender
        self._reset_token_ttl = reset_token_ttl

    async def execute(self, command: RequestPasswordResetCommand) -> None:
        user = await self._user_repository.get_by_email(command.email)
        if user is None or user.password_hash is None:
            # No account, or an OTP-only account with no password to reset —
            # complete silently either way.
            return

        raw_token = secrets.token_urlsafe(32)
        now = datetime.now(UTC)
        reset_token = PasswordResetToken(
            uuid.uuid4(),
            user_id=user.id,
            token_hash=self._token_hasher.hash(raw_token),
            expires_at=now + self._reset_token_ttl,
        )
        await self._reset_token_repository.save(reset_token)

        body = f"Use this link to reset your password: /reset-password?token={raw_token}"
        await self._email_sender.send(command.email, "Reset your password", body)


@dataclass(frozen=True, slots=True)
class ConfirmPasswordResetCommand(Command):
    reset_token: str
    new_password: str


class ConfirmPasswordResetUseCase:
    def __init__(
        self,
        reset_token_repository: PasswordResetTokenRepository,
        user_repository: IdentityUserRepository,
        token_hasher: TokenHasher,
        password_hasher: PasswordHasher,
    ) -> None:
        self._reset_token_repository = reset_token_repository
        self._user_repository = user_repository
        self._token_hasher = token_hasher
        self._password_hasher = password_hasher

    async def execute(self, command: ConfirmPasswordResetCommand) -> None:
        token_hash = self._token_hasher.hash(command.reset_token)
        token = await self._reset_token_repository.get_by_token_hash(token_hash)

        if token is None or not token.is_usable():
            msg = "This password reset link has expired."
            raise ResetTokenExpiredError(msg)

        user = await self._user_repository.get(token.user_id)
        if user is None:
            msg = "This password reset link has expired."
            raise ResetTokenExpiredError(msg)

        token.mark_used()
        await self._reset_token_repository.save(token)

        user.change_password_hash(self._password_hasher.hash(command.new_password))
        await self._user_repository.save(user)
