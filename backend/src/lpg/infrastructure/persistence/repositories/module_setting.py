"""`SqlAlchemyTenantModuleSettingRepository` — implements
`application/license/ports.py::TenantModuleSettingRepository` over
`platform.tenant_module_setting` (migration `c5a8f2d1b9e7`), RLS-scoped to the
unit of work's tenant."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select

from lpg.infrastructure.persistence.models.platform import TenantModuleSettingModel

if TYPE_CHECKING:
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


class SqlAlchemyTenantModuleSettingRepository:
    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._uow = unit_of_work

    async def disabled_keys(self) -> frozenset[str]:
        result = await self._uow.session.execute(
            select(TenantModuleSettingModel.module_key).where(
                TenantModuleSettingModel.enabled.is_(False)
            )
        )
        return frozenset(result.scalars())

    async def set_enabled(self, tenant_id: uuid.UUID, module_key: str, *, enabled: bool) -> None:
        result = await self._uow.session.execute(
            select(TenantModuleSettingModel).where(
                TenantModuleSettingModel.tenant_id == tenant_id,
                TenantModuleSettingModel.module_key == module_key,
            )
        )
        row = result.scalars().first()
        if row is None:
            self._uow.session.add(
                TenantModuleSettingModel(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    module_key=module_key,
                    enabled=enabled,
                )
            )
        else:
            row.enabled = enabled
