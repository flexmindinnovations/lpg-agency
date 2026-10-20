"""My Profile (QA finding DA-30): a signed-in staff member reads and edits
their own name and contact number, and changes their own password.

Before this the only way to change a password was the forgot-password email
flow, which needs email delivery an agency may not have configured. Changing
it here requires the current password, so a session left open on a shared
counter PC cannot be used to take the account over.

Operates through the tenant-scoped `StaffUserRepository` (RLS), so a user can
only ever reach their own row inside their own agency. Every change writes an
audit entry - never with the password or its hash.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command, Query
from lpg.application.common.errors import NotFoundError, ValidationError
from lpg.domain.common.base import InvariantViolation

if TYPE_CHECKING:
    import uuid

    from lpg.application.audit.ports import AuditTrail
    from lpg.application.identity.ports import PasswordHasher, StaffUserRepository
    from lpg.domain.identity.user import IdentityUser

_AUDIT_ENTITY = "identity_user"


async def _me(repository: StaffUserRepository, user_id: uuid.UUID) -> IdentityUser:
    user = await repository.get(user_id)
    if user is None:
        msg = "Your profile can't be edited here."
        raise NotFoundError(msg, user_id=str(user_id))
    return user


@dataclass(frozen=True, slots=True)
class GetMyProfileQuery(Query):
    user_id: uuid.UUID


class GetMyProfileUseCase:
    def __init__(self, repository: StaffUserRepository) -> None:
        self._repository = repository

    async def execute(self, query: GetMyProfileQuery) -> IdentityUser:
        return await _me(self._repository, query.user_id)


@dataclass(frozen=True, slots=True)
class UpdateMyProfileCommand(Command):
    user_id: uuid.UUID
    display_name: str | None
    contact_phone: str | None


class UpdateMyProfileUseCase:
    def __init__(self, repository: StaffUserRepository, audit: AuditTrail) -> None:
        self._repository = repository
        self._audit = audit

    async def execute(self, command: UpdateMyProfileCommand) -> IdentityUser:
        user = await _me(self._repository, command.user_id)
        before = {"display_name": user.display_name, "contact_phone": user.contact_phone}
        try:
            user.update_profile(
                display_name=command.display_name, contact_phone=command.contact_phone
            )
        except InvariantViolation as exc:
            raise ValidationError(exc.message, errors={"__root__": [exc.message]}) from exc
        after = {"display_name": user.display_name, "contact_phone": user.contact_phone}
        if before == after:
            return user
        await self._repository.save(user)
        await self._audit.record(
            action="update",
            entity_name=_AUDIT_ENTITY,
            entity_id=str(user.id),
            entity_display_name=user.display_name or user.email,
            details={"change": "own_profile"},
            before=dict(before),
            after=dict(after),
        )
        return user


@dataclass(frozen=True, slots=True)
class ChangeMyPasswordCommand(Command):
    user_id: uuid.UUID
    current_password: str
    new_password: str


class ChangeMyPasswordUseCase:
    def __init__(
        self,
        repository: StaffUserRepository,
        password_hasher: PasswordHasher,
        audit: AuditTrail,
        *,
        min_length: int,
    ) -> None:
        self._repository = repository
        self._password_hasher = password_hasher
        self._audit = audit
        self._min_length = min_length

    async def execute(self, command: ChangeMyPasswordCommand) -> None:
        user = await _me(self._repository, command.user_id)
        if user.password_hash is None or not self._password_hasher.verify(
            command.current_password, user.password_hash
        ):
            msg = "Your current password is not correct."
            raise ValidationError(msg, errors={"current_password": [msg]})
        if len(command.new_password) < self._min_length:
            msg = f"Use at least {self._min_length} characters."
            raise ValidationError(msg, errors={"new_password": [msg]})
        if command.new_password == command.current_password:
            msg = "Choose a password different from your current one."
            raise ValidationError(msg, errors={"new_password": [msg]})

        user.change_password_hash(self._password_hasher.hash(command.new_password))
        await self._repository.save(user)
        await self._audit.record(
            action="password_change",
            entity_name=_AUDIT_ENTITY,
            entity_id=str(user.id),
            entity_display_name=user.display_name or user.email,
            details={"change": "own_password"},
        )
