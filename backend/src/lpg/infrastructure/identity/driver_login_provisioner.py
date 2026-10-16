"""`SqlAlchemyDriverLoginProvisioner` implements
`application/tenant_admin/ports.py::DriverLoginProvisioner`.

Mirrors what the `EmployeeRegistered` handler in
`infrastructure/events/tenant_admin_handlers.py` does for a *new* driver
employee, but for one that already exists: it opens one session scoped to the
tenant and, in that single transaction, creates (or adopts) the phone login
and links it to the driver profile, so a failure leaves neither half behind.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select

from lpg.application.common.errors import ConflictError
from lpg.application.common.tenant import RequestTenantContext
from lpg.application.tenant_admin.ports import DriverLoginResult
from lpg.config.logging import get_logger
from lpg.domain.delivery.driver import Driver
from lpg.domain.identity.user import IdentityUser
from lpg.infrastructure.persistence.models.identity import IdentityUserModel
from lpg.infrastructure.persistence.repositories.driver import SqlAlchemyDriverRepository
from lpg.infrastructure.persistence.repositories.identity import insert_identity_user
from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from lpg.domain.tenant_admin.employee import Employee
    from lpg.infrastructure.persistence.database import Database

_logger = get_logger(__name__)

_DRIVER_ROLE = "driver"


class SqlAlchemyDriverLoginProvisioner:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def enable(self, tenant_id: uuid.UUID, employee: Employee) -> DriverLoginResult:
        async for session in self._database.open_session(tenant_id=tenant_id):
            tenant_context = RequestTenantContext(tenant_id=tenant_id)
            async with SqlAlchemyUnitOfWork(session, tenant_context) as uow:
                drivers = SqlAlchemyDriverRepository(uow)
                driver = await drivers.get_by_employee_id(employee.id)

                existing = await _find_login(session, tenant_id, employee.phone_number)
                login_created = existing is None
                if existing is None:
                    user = IdentityUser(
                        uuid.uuid4(),
                        tenant_id=tenant_id,
                        branch_id=employee.branch_id,
                        email=employee.email,
                        phone_number=employee.phone_number,
                        password_hash=None,
                        role=_DRIVER_ROLE,
                    )
                    await insert_identity_user(session, user)
                    user_id = user.id
                else:
                    _require_usable_driver_login(existing, employee)
                    user_id = existing.id
                    holder = await drivers.get_by_identity_user_id(user_id)
                    if holder is not None and (driver is None or holder.id != driver.id):
                        msg = (
                            f"The login for {employee.phone_number} is already linked to another "
                            "driver. Remove the duplicate driver before enabling this one."
                        )
                        raise ConflictError(msg, employee_id=str(employee.id))

                driver_created = driver is None
                driver_changed = driver_created
                if driver is None:
                    driver = Driver(
                        driver_id=drivers.next_id(),
                        tenant_id=tenant_id,
                        branch_id=employee.branch_id,
                        employee_id=employee.id,
                        license_number="PENDING",  # Staff complete the licence later
                        license_expiry_date=None,
                        identity_user_id=user_id,
                    )
                elif driver.identity_user_id is None:
                    driver.link_identity_user(user_id)
                    driver_changed = True
                elif driver.identity_user_id != user_id:
                    msg = "This driver is already linked to a different login."
                    raise ConflictError(msg, employee_id=str(employee.id))

                # A repeat call (login and link already in place) writes nothing.
                if driver_changed:
                    await drivers.save(driver)
                await uow.commit()
                _logger.info(
                    "driver_login_enabled",
                    tenant_id=str(tenant_id),
                    employee_id=str(employee.id),
                    user_id=str(user_id),
                    login_created=login_created,
                    driver_created=driver_created,
                )
                return DriverLoginResult(
                    user_id=user_id,
                    driver_id=driver.id,
                    login_created=login_created,
                    driver_created=driver_created,
                )

        raise RuntimeError("Unreachable")


async def _find_login(
    session: AsyncSession, tenant_id: uuid.UUID, phone_number: str
) -> IdentityUserModel | None:
    result = await session.execute(
        select(IdentityUserModel).where(
            IdentityUserModel.tenant_id == tenant_id,
            IdentityUserModel.phone_number == phone_number,
            IdentityUserModel.is_deleted.is_(False),
        )
    )
    return result.scalar_one_or_none()


def _require_usable_driver_login(existing: IdentityUserModel, employee: Employee) -> None:
    if existing.role != _DRIVER_ROLE:
        msg = (
            f"The phone number {employee.phone_number} already has a '{existing.role}' login, "
            "so it cannot also be a driver login."
        )
        raise ConflictError(msg, employee_id=str(employee.id))
    if not existing.is_active:
        msg = (
            f"The login for {employee.phone_number} is deactivated. "
            "Reactivate it under Users & Roles first."
        )
        raise ConflictError(msg, employee_id=str(employee.id))
