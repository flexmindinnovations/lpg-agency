"""Domain-event handlers for the tenant_admin bounded context.

Provisions the `IdentityUser` and role-specific aggregates (like `Driver`)
when an `Employee` is registered.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from lpg.domain.tenant_admin.employee import EmployeeRegistered

if TYPE_CHECKING:
    from lpg.domain.common.base import DomainEvent
    from lpg.infrastructure.events.dispatcher import DomainEventDispatcher
    from lpg.infrastructure.persistence.database import Database

_SYSTEM_ACTOR_ID = uuid.UUID(int=0)


def register_tenant_admin_handlers(dispatcher: DomainEventDispatcher, database: Database) -> None:
    async def _on_employee_registered(event: DomainEvent) -> None:
        assert isinstance(event, EmployeeRegistered)
        await _provision_auth_and_roles(database, event)

    dispatcher.register(EmployeeRegistered, _on_employee_registered)


async def _provision_auth_and_roles(database: Database, event: EmployeeRegistered) -> None:
    from lpg.application.common.tenant import RequestTenantContext
    from lpg.domain.delivery.driver import Driver
    from lpg.domain.identity.user import IdentityUser
    from lpg.infrastructure.persistence.repositories.driver import SqlAlchemyDriverRepository
    from lpg.infrastructure.persistence.repositories.identity import SqlAlchemyStaffUserRepository
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

    async for session in database.open_session(tenant_id=event.tenant_id):
        tenant_context = RequestTenantContext(tenant_id=event.tenant_id)
        async with SqlAlchemyUnitOfWork(session, tenant_context) as uow:
            identity_repo = SqlAlchemyStaffUserRepository(database, event.tenant_id)
            driver_repo = SqlAlchemyDriverRepository(uow)

            # 1. Create IdentityUser
            # Using the same ID as the employee for simplicity and 1:1 linkage,
            # or we could generate a new one. We'll generate a new one to keep
            # the domain boundaries strictly decoupled, but store it in driver.
            identity_user_id = uuid.uuid4()
            user = IdentityUser(
                user_id=identity_user_id,
                tenant_id=event.tenant_id,
                branch_id=event.branch_id,
                email=event.email,
                phone_number=event.phone_number,
                password_hash=None,
                role=event.role,
                is_active=True,
            )
            await identity_repo.add(user)

            # 2. Provision role-specific aggregates if necessary
            if event.role == "driver":
                # Create a Driver extension for the employee
                driver = Driver(
                    driver_id=driver_repo.next_id(),
                    tenant_id=event.tenant_id,
                    branch_id=event.branch_id,
                    employee_id=event.employee_id,
                    license_number="PENDING",  # Needs to be updated later by staff
                    license_expiry_date=None,
                    identity_user_id=identity_user_id,
                )
                await driver_repo.save(driver)

            await uow.commit()
