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

from lpg.application.common.cqrs import Command, Query
from lpg.application.common.errors import ConflictError, NotFoundError, ValidationError
from lpg.domain.identity.password_reset_token import PasswordResetToken
from lpg.domain.identity.user import IdentityUser

if TYPE_CHECKING:
    from collections.abc import Sequence

    from lpg.application.audit.ports import AuditTrail
    from lpg.application.identity.ports import (
        EmailSender,
        PasswordResetTokenRepository,
        PermissionRepository,
        RefreshTokenRepository,
        StaffUserRepository,
        TokenHasher,
    )

#: Roles a staff-management screen manages. Customer/Driver accounts have
#: their own future listing screens (Customer Management, Driver
#: Management) — this admin screen is for internal Dashboard staff only.
_STAFF_ROLES_EXCLUDED_FROM_LISTING = frozenset({"customer", "driver"})

#: The role that can manage staff. An agency must always keep at least one
#: active account with it, or nobody could ever reactivate anyone (DA-01).
AGENCY_ADMIN_ROLE = "agency_admin"

#: Roles an agency admin may give a staff account from Users & Roles.
#: `super_admin` is platform-level (D-01) and `customer`/`driver` accounts are
#: created by their own flows, so none of those can be assigned here.
ASSIGNABLE_STAFF_ROLES = frozenset(
    {"agency_admin", "manager", "warehouse_staff", "dispatcher", "accountant"}
)

#: Dashboard route that opens the "choose your password" form for a new
#: account. `/reset-password` (`password_reset.py`) is the same form worded for
#: a forgotten password; both take `?token=`.
SETUP_PASSWORD_PATH = "/set-password"  # noqa: S105 - a URL path, not a secret


def setup_password_path(raw_token: str) -> str:
    return f"{SETUP_PASSWORD_PATH}?token={raw_token}"


#: Audit entity name for identity accounts - the table name, matching what the
#: generic ORM audit hook writes for every other aggregate.
_AUDIT_ENTITY = "identity_user"


async def _get_staff_user(repository: StaffUserRepository, user_id: uuid.UUID) -> IdentityUser:
    user = await repository.get(user_id)
    if user is None or user.role in _STAFF_ROLES_EXCLUDED_FROM_LISTING:
        msg = f"No staff user visible with id {user_id}."
        raise NotFoundError(msg, user_id=str(user_id))
    return user


def _refuse_self(actor_id: uuid.UUID, user: IdentityUser, action: str) -> None:
    if actor_id == user.id:
        msg = f"You can't {action} your own account. Ask another admin to do it."
        raise ConflictError(msg, user_id=str(user.id))


async def _refuse_removing_last_admin(
    repository: StaffUserRepository, user: IdentityUser, action: str
) -> None:
    """An agency must keep one active `agency_admin`, or nobody can manage
    staff (or undo this) without direct database access."""
    if user.role != AGENCY_ADMIN_ROLE or not user.is_active:
        return
    if await repository.count_active_with_role(AGENCY_ADMIN_ROLE) <= 1:
        msg = (
            f"You can't {action} the last active agency admin. "
            "Make another user an agency admin first."
        )
        raise ConflictError(msg, user_id=str(user.id))


def _display_name(user: IdentityUser) -> str | None:
    return user.email or user.phone_number


@dataclass(frozen=True, slots=True)
class InviteStaffUserCommand(Command):
    tenant_id: uuid.UUID
    email: str
    role: str
    branch_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class SetupToken:
    """A freshly minted one-time token. `raw` exists only here - the database
    keeps just its hash."""

    raw: str
    expires_at: datetime


async def issue_setup_token(
    *,
    user_id: uuid.UUID,
    reset_token_repository: PasswordResetTokenRepository,
    token_hasher: TokenHasher,
    ttl: timedelta,
) -> SetupToken:
    """Create and persist a single-use password-setup token for `user_id`.

    The one place a setup/reset token is minted for a staff user - shared by
    `InviteStaffUserUseCase` and the Platform Console's re-issue path so both
    behave identically.
    """
    raw_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + ttl
    await reset_token_repository.save(
        PasswordResetToken(
            uuid.uuid4(),
            user_id=user_id,
            token_hash=token_hasher.hash(raw_token),
            expires_at=expires_at,
        )
    )
    return SetupToken(raw=raw_token, expires_at=expires_at)


@dataclass(frozen=True, slots=True)
class StaffInvitation:
    """An invited user plus the one-time setup token, for callers that must
    hand the link over themselves because email delivery is not wired up.
    The raw token exists only here — the database keeps just its hash."""

    user: IdentityUser
    setup_token: str
    setup_token_expires_at: datetime


class InviteStaffUserUseCase:
    def __init__(
        self,
        staff_user_repository: StaffUserRepository,
        reset_token_repository: PasswordResetTokenRepository,
        token_hasher: TokenHasher,
        email_sender: EmailSender,
        *,
        reset_token_ttl: timedelta,
        link_base: str = "",
    ) -> None:
        self._staff_user_repository = staff_user_repository
        self._reset_token_repository = reset_token_repository
        self._token_hasher = token_hasher
        self._email_sender = email_sender
        self._reset_token_ttl = reset_token_ttl
        self._link_base = link_base.rstrip("/")

    async def execute(self, command: InviteStaffUserCommand) -> IdentityUser:
        return (await self.invite(command)).user

    async def invite(self, command: InviteStaffUserCommand) -> StaffInvitation:
        if command.role not in ASSIGNABLE_STAFF_ROLES:
            msg = f"'{command.role}' can't be assigned to a staff account."
            raise ValidationError(msg, errors={"role": [msg]})
        user = IdentityUser(
            uuid.uuid4(),
            tenant_id=command.tenant_id,
            branch_id=command.branch_id,
            email=command.email.strip().lower(),
            phone_number=None,
            password_hash=None,  # Already a valid state — OTP-only accounts work this way too.
            role=command.role,
        )
        await self._staff_user_repository.add(user)

        token = await issue_setup_token(
            user_id=user.id,
            reset_token_repository=self._reset_token_repository,
            token_hasher=self._token_hasher,
            ttl=self._reset_token_ttl,
        )

        link = f"{self._link_base}{setup_password_path(token.raw)}"
        body = f"Set your password to activate your account: {link}"
        await self._email_sender.send(user.email or command.email, "You've been invited", body)

        return StaffInvitation(
            user=user, setup_token=token.raw, setup_token_expires_at=token.expires_at
        )


@dataclass(frozen=True, slots=True)
class DeactivateStaffUserCommand(Command):
    user_id: uuid.UUID
    #: The admin doing it - an admin can never deactivate themselves.
    actor_id: uuid.UUID


class DeactivateStaffUserUseCase:
    def __init__(
        self,
        staff_user_repository: StaffUserRepository,
        refresh_token_repository: RefreshTokenRepository,
        audit: AuditTrail,
    ) -> None:
        self._staff_user_repository = staff_user_repository
        self._refresh_token_repository = refresh_token_repository
        self._audit = audit

    async def execute(self, command: DeactivateStaffUserCommand) -> None:
        user = await _get_staff_user(self._staff_user_repository, command.user_id)
        _refuse_self(command.actor_id, user, "deactivate")
        if not user.is_active:
            return  # Already deactivated - nothing changes, nothing to audit.
        await _refuse_removing_last_admin(self._staff_user_repository, user, "deactivate")

        user.deactivate()
        await self._staff_user_repository.save(user)
        # Deactivating a user must end every session they're already in —
        # matches DeactivateStaffUserUseCase's plan-time spec and reuses the
        # exact method refresh-token-reuse detection already calls.
        await self._refresh_token_repository.revoke_all_for_user(user.id)
        await self._audit.record(
            action="deactivate",
            entity_name=_AUDIT_ENTITY,
            entity_id=str(user.id),
            entity_display_name=_display_name(user),
            details={"role": user.role, "sessions_revoked": True},
            before={"is_active": True},
            after={"is_active": False},
        )


@dataclass(frozen=True, slots=True)
class ReactivateStaffUserCommand(Command):
    user_id: uuid.UUID
    actor_id: uuid.UUID


class ReactivateStaffUserUseCase:
    """Undo a deactivation (DA-01: before this, nothing could)."""

    def __init__(self, staff_user_repository: StaffUserRepository, audit: AuditTrail) -> None:
        self._staff_user_repository = staff_user_repository
        self._audit = audit

    async def execute(self, command: ReactivateStaffUserCommand) -> None:
        user = await _get_staff_user(self._staff_user_repository, command.user_id)
        if user.is_active:
            return
        user.activate()
        await self._staff_user_repository.save(user)
        await self._audit.record(
            action="reactivate",
            entity_name=_AUDIT_ENTITY,
            entity_id=str(user.id),
            entity_display_name=_display_name(user),
            details={"role": user.role},
            before={"is_active": False},
            after={"is_active": True},
        )


@dataclass(frozen=True, slots=True)
class ReassignRoleCommand(Command):
    user_id: uuid.UUID
    new_role: str
    actor_id: uuid.UUID


class ReassignRoleUseCase:
    """Change a staff user's role and reset their permissions to that role's.

    Permissions are materialised per user (`identity_user_permission`), so a
    role change that left them alone would keep every permission of the old
    role - a dispatcher made accountant would still dispatch. The new role's
    defaults replace them; an admin can then fine-tune in the permission
    editor as before.
    """

    def __init__(
        self,
        staff_user_repository: StaffUserRepository,
        permission_repository: PermissionRepository,
        audit: AuditTrail,
    ) -> None:
        self._staff_user_repository = staff_user_repository
        self._permission_repository = permission_repository
        self._audit = audit

    async def execute(self, command: ReassignRoleCommand) -> None:
        if command.new_role not in ASSIGNABLE_STAFF_ROLES:
            msg = f"'{command.new_role}' can't be assigned to a staff account."
            raise ValidationError(msg, errors={"new_role": [msg]})

        user = await _get_staff_user(self._staff_user_repository, command.user_id)
        if user.role == command.new_role:
            return
        _refuse_self(command.actor_id, user, "change the role of")
        await _refuse_removing_last_admin(self._staff_user_repository, user, "change the role of")

        old_role = user.role
        user.change_role(command.new_role)
        await self._staff_user_repository.save(user)
        role_permissions = await self._permission_repository.get_permission_codes_for_role(
            command.new_role
        )
        await self._permission_repository.set_permissions_for_user(user.id, set(role_permissions))
        await self._audit.record(
            action="update",
            entity_name=_AUDIT_ENTITY,
            entity_id=str(user.id),
            entity_display_name=_display_name(user),
            details={"change": "role", "permissions_reset_to_role_defaults": True},
            before={"role": old_role},
            after={"role": command.new_role},
        )


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


@dataclass(frozen=True, slots=True)
class GetStaffUserPermissionsQuery:
    user_id: uuid.UUID


class GetStaffUserPermissionsUseCase:
    def __init__(
        self,
        staff_user_repository: StaffUserRepository,
        permission_repository: PermissionRepository,
    ) -> None:
        self._staff_user_repository = staff_user_repository
        self._permission_repository = permission_repository

    async def execute(self, query: GetStaffUserPermissionsQuery) -> frozenset[str]:
        user = await self._staff_user_repository.get(query.user_id)
        if user is None:
            msg = f"No staff user visible with id {query.user_id}."
            raise NotFoundError(msg, user_id=str(query.user_id))

        return await self._permission_repository.get_permission_codes_for_user(query.user_id)


@dataclass(frozen=True, slots=True)
class UpdateStaffUserPermissionsCommand(Command):
    user_id: uuid.UUID
    permission_codes: set[str]
    actor_id: uuid.UUID


class UpdateStaffUserPermissionsUseCase:
    def __init__(
        self,
        staff_user_repository: StaffUserRepository,
        permission_repository: PermissionRepository,
        audit: AuditTrail,
    ) -> None:
        self._staff_user_repository = staff_user_repository
        self._permission_repository = permission_repository
        self._audit = audit

    async def execute(self, command: UpdateStaffUserPermissionsCommand) -> None:
        user = await _get_staff_user(self._staff_user_repository, command.user_id)
        # Editing your own permission set is how an admin would lock
        # themselves out of this very screen.
        _refuse_self(command.actor_id, user, "change the permissions of")

        known = await self._permission_repository.get_all_permission_codes()
        unknown = sorted(command.permission_codes - known)
        if unknown:
            msg = f"Unknown permission(s): {', '.join(unknown)}."
            raise ValidationError(msg, errors={"permission_codes": [msg]})

        before = await self._permission_repository.get_permission_codes_for_user(user.id)
        after = frozenset(command.permission_codes)
        if before == after:
            return
        await self._permission_repository.set_permissions_for_user(
            command.user_id, command.permission_codes
        )
        await self._audit.record(
            action="update",
            entity_name=_AUDIT_ENTITY,
            entity_id=str(user.id),
            entity_display_name=_display_name(user),
            details={
                "change": "permissions",
                "granted": sorted(after - before),
                "revoked": sorted(before - after),
            },
            before={"permissions": sorted(before)},
            after={"permissions": sorted(after)},
        )


@dataclass(frozen=True, slots=True)
class ListPermissionsQuery(Query):
    pass


class ListPermissionsUseCase:
    def __init__(self, permission_repository: PermissionRepository) -> None:
        self._permission_repository = permission_repository

    async def execute(self, _query: ListPermissionsQuery) -> frozenset[str]:
        return await self._permission_repository.get_all_permission_codes()
