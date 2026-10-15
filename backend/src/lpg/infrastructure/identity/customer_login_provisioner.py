"""`SqlAlchemyCustomerLoginProvisioner` implements
`application/identity/ports.py::CustomerLoginProvisioner` (ADR-051).

Runs before authentication, so there is no request `UnitOfWork`: it opens its
own session scoped to the tenant the agency code resolved to, the same way
the `EmployeeRegistered` handler in `infrastructure/events/tenant_admin_handlers.py`
provisions a staff login. Creating the login and linking it to the customer
happen in that one transaction, so a failure leaves neither behind.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from lpg.application.common.tenant import RequestTenantContext
from lpg.config.logging import get_logger
from lpg.domain.identity.user import IdentityUser
from lpg.infrastructure.persistence.repositories.customer import SqlAlchemyCustomerRepository
from lpg.infrastructure.persistence.repositories.identity import insert_identity_user
from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

if TYPE_CHECKING:
    from lpg.application.customer.ports import FieldEncryptor
    from lpg.infrastructure.persistence.database import Database

_logger = get_logger(__name__)

_CUSTOMER_ROLE = "customer"


class SqlAlchemyCustomerLoginProvisioner:
    def __init__(self, database: Database, field_encryptor: FieldEncryptor) -> None:
        self._database = database
        self._field_encryptor = field_encryptor

    async def provision(self, tenant_id: uuid.UUID, phone_number: str) -> IdentityUser | None:
        async for session in self._database.open_session(tenant_id=tenant_id):
            tenant_context = RequestTenantContext(tenant_id=tenant_id)
            async with SqlAlchemyUnitOfWork(session, tenant_context) as uow:
                customers = SqlAlchemyCustomerRepository(uow, self._field_encryptor)
                customer = await customers.get_by_phone(phone_number)
                if customer is None or not customer.can_get_app_login:
                    return None

                user = IdentityUser(
                    uuid.uuid4(),
                    tenant_id=tenant_id,
                    branch_id=customer.branch_id,
                    email=None,
                    phone_number=phone_number,
                    password_hash=None,
                    role=_CUSTOMER_ROLE,
                )
                await insert_identity_user(session, user)
                customer.link_identity_user(user.id)
                await customers.save(customer)
                await uow.commit()
                _logger.info(
                    "customer_login_provisioned",
                    tenant_id=str(tenant_id),
                    customer_id=str(customer.id),
                    user_id=str(user.id),
                )
                return user

        raise RuntimeError("Unreachable")
