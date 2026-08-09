"""`SqlAlchemyTenantRepository` — implements `TenantRepository`
(`lpg.application.tenant.ports`).

Constructed from a `SqlAlchemyUnitOfWork`, not a raw session: this is what
lets `get()` register the loaded aggregate with the Unit of Work
(`03-backend-architecture.md` §3.1's "no repository constructor takes a raw
engine", extended here to "no repository loads an aggregate the Unit of Work
doesn't know about" — otherwise `collect_events()` would miss it).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lpg.domain.tenant.tenant import Tenant
from lpg.infrastructure.persistence.models.tenant import TenantModel

if TYPE_CHECKING:
    import uuid

    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


class SqlAlchemyTenantRepository:
    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._uow = unit_of_work

    async def get(self, tenant_id: uuid.UUID) -> Tenant | None:
        row = await self._uow.session.get(TenantModel, tenant_id)
        if row is None:
            return None

        tenant = Tenant(row.id, row.name, row.slug, version=row.version)
        self._uow.register_aggregate(tenant)
        return tenant

    async def save(self, tenant: Tenant) -> None:
        row = await self._uow.session.get(TenantModel, tenant.id)
        if row is None:
            msg = f"Cannot save tenant {tenant.id} — no matching row was loaded."
            raise LookupError(msg)

        row.name = tenant.name
        row.slug = tenant.slug
