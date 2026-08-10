"""The `IdentityUser` aggregate — Phase 6's authentication principal.

Framework-free like every other domain aggregate (ADR-024): `password_hash`
is accepted as an already-hashed opaque string. Hashing itself is an
infrastructure concern (`application/identity/ports.py::PasswordHasher`) —
this aggregate never imports argon2, and never sees a plaintext password.

Lockout thresholds/durations are passed in by the caller (the use case layer,
reading `Settings`) rather than read from configuration here — the domain
layer has no config-loading capability, by design.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from lpg.domain.common.base import AggregateRoot, DomainEvent, InvariantViolation

if TYPE_CHECKING:
    import uuid


@dataclass(frozen=True, slots=True)
class IdentityUserLoggedIn(DomainEvent):
    """Recorded on a successful login — feeds D-39's audit requirement."""

    user_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class IdentityUserLoginFailed(DomainEvent):
    """Recorded on a failed login attempt (wrong password, inactive, locked)."""

    user_id: uuid.UUID | None = None
    reason: str = ""


@dataclass(frozen=True, slots=True)
class IdentityUserLocked(DomainEvent):
    """Recorded when repeated failures cross the lockout threshold."""

    user_id: uuid.UUID | None = None
    locked_until: datetime | None = None


class IdentityUser(AggregateRoot):
    """A platform principal: Dashboard staff (password) or Customer/Driver (OTP).

    `tenant_id` is nullable — null only for Super Admin, who operates above
    tenant scope (D-01). `email`/`phone_number`/`password_hash` are all
    nullable because the two auth methods populate different subsets: a
    password-only staff account has no `phone_number`, an OTP-only
    customer/driver account has no `password_hash`.
    """

    __slots__ = (
        "_branch_id",
        "_email",
        "_failed_login_count",
        "_is_active",
        "_locked_until",
        "_password_hash",
        "_phone_number",
        "_role",
        "_tenant_id",
    )

    def __init__(
        self,
        user_id: uuid.UUID,
        *,
        tenant_id: uuid.UUID | None,
        branch_id: uuid.UUID | None,
        email: str | None,
        phone_number: str | None,
        password_hash: str | None,
        role: str,
        is_active: bool = True,
        failed_login_count: int = 0,
        locked_until: datetime | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(user_id, version=version)
        self._tenant_id = tenant_id
        self._branch_id = branch_id
        self._email = email
        self._phone_number = phone_number
        self._password_hash = password_hash
        self._role = role
        self._is_active = is_active
        self._failed_login_count = failed_login_count
        self._locked_until = locked_until

    @property
    def tenant_id(self) -> uuid.UUID | None:
        return self._tenant_id

    @property
    def branch_id(self) -> uuid.UUID | None:
        return self._branch_id

    @property
    def email(self) -> str | None:
        return self._email

    @property
    def phone_number(self) -> str | None:
        return self._phone_number

    @property
    def password_hash(self) -> str | None:
        return self._password_hash

    @property
    def role(self) -> str:
        return self._role

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def failed_login_count(self) -> int:
        return self._failed_login_count

    @property
    def locked_until(self) -> datetime | None:
        return self._locked_until

    def is_locked(self, *, now: datetime | None = None) -> bool:
        moment = now or datetime.now(UTC)
        return self._locked_until is not None and self._locked_until > moment

    def record_successful_login(self) -> None:
        """Reset the failure counter and clear any lock, then record the event."""
        self._failed_login_count = 0
        self._locked_until = None
        self.record_event(IdentityUserLoggedIn(user_id=self.id))

    def record_failed_login(
        self,
        *,
        reason: str,
        lockout_threshold: int,
        lockout_duration: timedelta,
    ) -> None:
        """Increment the failure counter, locking the account once it crosses
        `lockout_threshold`. Always records `IdentityUserLoginFailed`; records
        `IdentityUserLocked` too on the attempt that crosses the threshold.
        """
        self._failed_login_count += 1
        self.record_event(IdentityUserLoginFailed(user_id=self.id, reason=reason))
        if self._failed_login_count >= lockout_threshold and not self.is_locked():
            self._locked_until = datetime.now(UTC) + lockout_duration
            self.record_event(IdentityUserLocked(user_id=self.id, locked_until=self._locked_until))

    def change_password_hash(self, new_password_hash: str) -> None:
        """Replace the stored hash. Accepts an already-hashed value only —
        the caller (a use case) is responsible for hashing and for verifying
        the new password isn't a reuse of the current one, if that policy
        applies.
        """
        if not new_password_hash:
            msg = "password_hash cannot be empty."
            raise InvariantViolation(msg, user_id=str(self.id))
        self._password_hash = new_password_hash

    def activate(self) -> None:
        self._is_active = True

    def deactivate(self) -> None:
        self._is_active = False
