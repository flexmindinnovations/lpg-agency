"""`InviteStaffUserUseCase` / `DeactivateStaffUserUseCase` /
`ReassignRoleUseCase` / `ListStaffUsersUseCase`.

Admin-side staff-account management (Phase 7) — the CRUD Phase 6 explicitly
deferred ("No staff/customer/driver user management CRUD — Roadmap Phase 7
owns that"). Lives in `application/identity/` rather than a new
`application/tenant/` indirection layer: these use cases operate directly on
the `IdentityUser` aggregate, so the aggregate boundary wins over the
feature-grouping the roadmap happens to file this under (decided ahead of
this plan, see `planning/features/07-administration-tenant-master-data/PLAN.md`).

`InviteStaffUserUseCase` creates the account with no password set and
reuses the **existing** password-reset-token mechanism (`PasswordResetToken`,
`PasswordResetTokenRepository`, `EmailSender`) as the "set your initial
password" flow — no new invite-token concept, no new email template
concept. `ConfirmPasswordResetUseCase` (`password_reset.py`, unchanged)
is what actually activates the account once the invited user follows the
link.
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command
from lpg.application.common.errors import NotFoundError
from lpg.domain.identity.password_reset_token import PasswordResetToken
from lpg.domain.identity.user import IdentityUser

if TYPE_CHECKING:
    from collections.abc import Sequence

    from lpg.application.identity.ports import (
        EmailSender,
        PasswordResetTokenRepository,
        RefreshTokenRepository,
        StaffUserRepository,
        TokenHasher,
    )

#: Roles a staff-management screen manages. Customer/Driver accounts have
#: their own future listing screens (Customer Management, Driver
#: Management) — this admin screen is for internal Dashboard staff only.
_STAFF_ROLES_EXCLUDED_FROM_LISTING = frozenset({"customer", "driver"})


@dataclass(frozen=True, slots=True)
class InviteStaffUserCommand(Command):
    tenant_id: uuid.UUID
    email: str
    role: str
    branch_id: uuid.UUID | None = None


class InviteStaffUserUseCase:
    def __init__(
        self,
        staff_user_repository: StaffUserRepository,
        reset_token_repository: PasswordResetTokenRepository,
        token_hasher: TokenHasher,
        email_sender: EmailSender,
        *,
        reset_token_ttl: timedelta,
    ) -> None:
        self._staff_user_repository = staff_user_repository
        self._reset_token_repository = reset_token_repository
        self._token_hasher = token_hasher
        self._email_sender = email_sender
        self._reset_token_ttl = reset_token_ttl

    async def execute(self, command: InviteStaffUserCommand) -> IdentityUser:
        user = IdentityUser(
            uuid.uuid4(),
            tenant_id=command.tenant_id,
            branch_id=command.branch_id,
            email=command.email,
            phone_number=None,
            password_hash=None,  # Already a valid state — OTP-only accounts work this way too.
            role=command.role,
        )
        await self._staff_user_repository.add(user)

        raw_token = secrets.token_urlsafe(32)
        reset_token = PasswordResetToken(
            uuid.uuid4(),
            user_id=user.id,
            token_hash=self._token_hasher.hash(raw_token),
            expires_at=datetime.now(UTC) + self._reset_token_ttl,
        )
        await self._reset_token_repository.save(reset_token)

        body = f"Set your password to activate your account: /reset-password?token={raw_token}"
        await self._email_sender.send(command.email, "You've been invited", body)

        return user


@dataclass(frozen=True, slots=True)
class DeactivateStaffUserCommand(Command):
    user_id: uuid.UUID


class DeactivateStaffUserUseCase:
    def __init__(
        self,
        staff_user_repository: StaffUserRepository,
        refresh_token_repository: RefreshTokenRepository,
    ) -> None:
        self._staff_user_repository = staff_user_repository
        self._refresh_token_repository = refresh_token_repository

    async def execute(self, command: DeactivateStaffUserCommand) -> None:
        user = await self._staff_user_repository.get(command.user_id)
        if user is None:
            msg = f"No staff user visible with id {command.user_id}."
            raise NotFoundError(msg, user_id=str(command.user_id))

        user.deactivate()
        await self._staff_user_repository.save(user)
        # Deactivating a user must end every session they're already in —
        # matches DeactivateStaffUserUseCase's plan-time spec and reuses the
        # exact method refresh-token-reuse detection already calls.
        await self._refresh_token_repository.revoke_all_for_user(user.id)


@dataclass(frozen=True, slots=True)
class ReassignRoleCommand(Command):
    user_id: uuid.UUID
    new_role: str


class ReassignRoleUseCase:
    def __init__(self, staff_user_repository: StaffUserRepository) -> None:
        self._staff_user_repository = staff_user_repository

    async def execute(self, command: ReassignRoleCommand) -> None:
        user = await self._staff_user_repository.get(command.user_id)
        if user is None:
            msg = f"No staff user visible with id {command.user_id}."
            raise NotFoundError(msg, user_id=str(command.user_id))

        user.change_role(command.new_role)
        await self._staff_user_repository.save(user)


@dataclass(frozen=True, slots=True)
class ListStaffUsersQuery:
    tenant_id: uuid.UUID


class ListStaffUsersUseCase:
    def __init__(self, staff_user_repository: StaffUserRepository) -> None:
        self._staff_user_repository = staff_user_repository

    async def execute(self, query: ListStaffUsersQuery) -> Sequence[IdentityUser]:
        return await self._staff_user_repository.list_for_tenant(
            query.tenant_id, exclude_roles=_STAFF_ROLES_EXCLUDED_FROM_LISTING
        )
