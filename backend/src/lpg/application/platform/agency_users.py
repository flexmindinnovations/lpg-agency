"""Super Admin management of an agency's users (Platform Console, Phase 31).

`POST /platform/agencies` creates an agency and its first admin, but until
these use cases existed a Super Admin could do nothing else with an agency's
users - and because setup links are single-use, time-limited and there is no
email provider, an agency whose first admin missed the link was locked out with
no recovery path.

Three use cases: list an agency's staff, add another `agency_admin`, and issue a
fresh one-time setup link for an existing `agency_admin`. Every write is
recorded through `PlatformAuditTrail` against the target agency.

Recovery is deliberately limited to `agency_admin` accounts: other staff are
recovered by their agency's admins, which keeps a Super Admin's reach to the
smallest set that still un-sticks an agency. The Platform Console was designed
to keep the Super Admin out of agency business data (D-01); minting an admin or
a reset link is an indirect way in, accepted because it is the only recovery
path, audited, and visible to the agency (ADR-049).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command, Query
from lpg.application.common.errors import ConflictError, NotFoundError
from lpg.application.identity.staff_user import InviteStaffUserCommand, issue_setup_token

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence
    from datetime import datetime, timedelta

    from lpg.application.identity.ports import (
        IdentityUserRepository,
        PasswordResetTokenRepository,
        StaffUserRepository,
        TokenHasher,
    )
    from lpg.application.identity.staff_user import InviteStaffUserUseCase
    from lpg.application.platform.ports import PlatformAuditTrail
    from lpg.application.tenant.ports import TenantRepository
    from lpg.domain.identity.user import IdentityUser
    from lpg.domain.tenant.tenant import Tenant

#: The one role a Super Admin may add or recover.
AGENCY_ADMIN_ROLE = "agency_admin"

#: Same exclusion the tenant-side staff listing applies: customer and driver
#: accounts have their own screens and are not "staff".
_NON_STAFF_ROLES = frozenset({"customer", "driver"})


async def _get_agency(tenants: TenantRepository, tenant_id: uuid.UUID) -> Tenant:
    tenant = await tenants.get(tenant_id)
    if tenant is None:
        msg = f"No agency visible with id {tenant_id}."
        raise NotFoundError(msg, tenant_id=str(tenant_id))
    return tenant


def _require_open(tenant: Tenant) -> None:
    if tenant.status == "closed":
        msg = "This agency is closed; its users can no longer be managed."
        raise ConflictError(msg, tenant_id=str(tenant.id))


# -- List ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ListAgencyUsersQuery(Query):
    tenant_id: uuid.UUID


class ListAgencyUsersUseCase:
    def __init__(self, tenants: TenantRepository, staff: StaffUserRepository) -> None:
        self._tenants = tenants
        self._staff = staff

    async def execute(self, query: ListAgencyUsersQuery) -> Sequence[IdentityUser]:
        # A closed agency's users stay visible (read-only) - only the writes refuse.
        await _get_agency(self._tenants, query.tenant_id)
        return await self._staff.list_for_tenant(query.tenant_id, exclude_roles=_NON_STAFF_ROLES)


# -- Add an admin ----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AddAgencyAdminCommand(Command):
    tenant_id: uuid.UUID
    email: str


@dataclass(frozen=True, slots=True)
class IssuedSetupLink:
    """The user plus the one-time link secret. Returned once, never stored raw."""

    user: IdentityUser
    setup_token: str
    setup_token_expires_at: datetime


class AddAgencyAdminUseCase:
    def __init__(
        self,
        tenants: TenantRepository,
        users: IdentityUserRepository,
        invite: InviteStaffUserUseCase,
        audit: PlatformAuditTrail,
    ) -> None:
        self._tenants = tenants
        self._users = users
        self._invite = invite
        self._audit = audit

    async def execute(self, command: AddAgencyAdminCommand) -> IssuedSetupLink:
        tenant = await _get_agency(self._tenants, command.tenant_id)
        _require_open(tenant)

        email = command.email.strip().lower()
        # Email is unique across every agency, so check globally before creating.
        if await self._users.get_by_email(email) is not None:
            msg = f"A user with email '{email}' already exists."
            raise ConflictError(msg)

        invitation = await self._invite.invite(
            InviteStaffUserCommand(tenant_id=tenant.id, email=email, role=AGENCY_ADMIN_ROLE)
        )
        await self._audit.record(
            action="platform.agency_admin_added",
            entity_name="identity_user",
            entity_id=str(invitation.user.id),
            entity_display_name=email,
            details={
                "agency": tenant.slug,
                "role": AGENCY_ADMIN_ROLE,
                "setup_link_expires_at": invitation.setup_token_expires_at.isoformat(),
            },
        )
        return IssuedSetupLink(
            user=invitation.user,
            setup_token=invitation.setup_token,
            setup_token_expires_at=invitation.setup_token_expires_at,
        )


# -- Re-issue a setup link ---------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IssueSetupLinkCommand(Command):
    tenant_id: uuid.UUID
    user_id: uuid.UUID


class IssueSetupLinkUseCase:
    def __init__(
        self,
        tenants: TenantRepository,
        staff: StaffUserRepository,
        reset_tokens: PasswordResetTokenRepository,
        token_hasher: TokenHasher,
        audit: PlatformAuditTrail,
        *,
        link_ttl: timedelta,
    ) -> None:
        self._tenants = tenants
        self._staff = staff
        self._reset_tokens = reset_tokens
        self._token_hasher = token_hasher
        self._audit = audit
        self._link_ttl = link_ttl

    async def execute(self, command: IssueSetupLinkCommand) -> IssuedSetupLink:
        tenant = await _get_agency(self._tenants, command.tenant_id)
        _require_open(tenant)

        # The staff repository is tenant-scoped (RLS): another agency's user is
        # simply not visible, so it is a 404 - never a hint that it exists.
        user = await self._staff.get(command.user_id)
        if user is None or user.tenant_id != tenant.id:
            msg = f"No user {command.user_id} in agency {tenant.id}."
            raise NotFoundError(msg, tenant_id=str(tenant.id))
        if user.role != AGENCY_ADMIN_ROLE:
            msg = "A setup link can only be issued for an agency admin."
            raise ConflictError(msg, user_id=str(user.id))
        if not user.is_active:
            msg = "This user is deactivated; reactivate the account before issuing a link."
            raise ConflictError(msg, user_id=str(user.id))

        # Older unused links die the moment a new one exists, so a link that was
        # sent to the wrong place cannot be used later.
        await self._reset_tokens.invalidate_unused_for_user(user.id)
        token = await issue_setup_token(
            user_id=user.id,
            reset_token_repository=self._reset_tokens,
            token_hasher=self._token_hasher,
            ttl=self._link_ttl,
        )
        await self._audit.record(
            action="platform.setup_link_issued",
            entity_name="identity_user",
            entity_id=str(user.id),
            entity_display_name=user.email,
            details={
                "agency": tenant.slug,
                "role": user.role,
                "setup_link_expires_at": token.expires_at.isoformat(),
            },
        )
        return IssuedSetupLink(
            user=user, setup_token=token.raw, setup_token_expires_at=token.expires_at
        )
