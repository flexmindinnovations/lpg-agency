"""`ProvisionTenantUseCase` — a Super Admin creating a new agency.

Two steps that cannot share one transaction, because they run through
different seams: the tenant row goes in through the platform Unit of Work
(`tenant.tenant_provision()`, a `SECURITY DEFINER` function — RLS forbids a
plain INSERT), while the first admin is created by `InviteStaffUserUseCase`,
whose repositories open their own tenant-scoped sessions. The tenant must be
committed before those sessions can reference it.

So the order is: cheap pre-checks -> commit the tenant -> invite the admin.
If the invite fails after the tenant is durable, `abort_provisioning` closes
the half-created tenant so it is not left as an admin-less shell; the error
is then re-raised. The only thing that stays behind is the (closed) slug.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command
from lpg.application.common.errors import ConflictError
from lpg.application.identity.staff_user import InviteStaffUserCommand
from lpg.domain.tenant.tenant import Tenant

if TYPE_CHECKING:
    import uuid
    from collections.abc import Awaitable, Callable
    from datetime import datetime

    from lpg.application.common.ports import UnitOfWork
    from lpg.application.identity.ports import IdentityUserRepository
    from lpg.application.identity.staff_user import InviteStaffUserUseCase
    from lpg.application.tenant.ports import TenantRepository
    from lpg.domain.identity.user import IdentityUser

#: The role of an agency's first user — full control of that agency.
FIRST_ADMIN_ROLE = "agency_admin"


@dataclass(frozen=True, slots=True)
class ProvisionTenantCommand(Command):
    name: str
    slug: str
    primary_contact_email: str
    admin_email: str
    subscription_plan: str = "standard"
    country: str = "IN"


@dataclass(frozen=True, slots=True)
class ProvisionedTenant:
    tenant: Tenant
    admin: IdentityUser
    setup_token: str
    setup_token_expires_at: datetime


class ProvisionTenantUseCase:
    def __init__(
        self,
        tenant_repository: TenantRepository,
        unit_of_work: UnitOfWork,
        user_repository: IdentityUserRepository,
        invite_use_case_factory: Callable[[uuid.UUID], InviteStaffUserUseCase],
        abort_provisioning: Callable[[uuid.UUID], Awaitable[None]],
    ) -> None:
        self._tenants = tenant_repository
        self._unit_of_work = unit_of_work
        self._users = user_repository
        # A factory, not an instance: the staff-user repository is bound to a
        # tenant id, and this tenant's id only exists once `Tenant.provision` runs.
        self._invite_for = invite_use_case_factory
        self._abort_provisioning = abort_provisioning

    async def execute(self, command: ProvisionTenantCommand) -> ProvisionedTenant:
        # Validates every field (raises `InvariantViolation`) before anything is written.
        tenant = Tenant.provision(
            name=command.name,
            slug=command.slug,
            primary_contact_email=command.primary_contact_email,
            subscription_plan=command.subscription_plan,
            country=command.country,
        )

        # Email is globally unique across agencies; checking now avoids
        # creating a tenant we already know cannot get its admin.
        admin_email = command.admin_email.strip().lower()
        if await self._users.get_by_email(admin_email) is not None:
            msg = f"A user with email '{admin_email}' already exists."
            raise ConflictError(msg)

        await self._tenants.add(tenant)
        await self._unit_of_work.commit()

        try:
            invitation = await self._invite_for(tenant.id).invite(
                InviteStaffUserCommand(
                    tenant_id=tenant.id, email=admin_email, role=FIRST_ADMIN_ROLE
                )
            )
        except Exception:
            await self._abort_provisioning(tenant.id)
            raise

        return ProvisionedTenant(
            tenant=tenant,
            admin=invitation.user,
            setup_token=invitation.setup_token,
            setup_token_expires_at=invitation.setup_token_expires_at,
        )
