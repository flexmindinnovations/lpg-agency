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

from sqlalchemy import select

from lpg.domain.platform.feature_flag import FeatureFlagOverride
from lpg.domain.tenant.branch import Branch
from lpg.domain.tenant.cylinder_type import CylinderType
from lpg.domain.tenant.price_list import PriceListEntry
from lpg.domain.tenant.tenant import Tenant
from lpg.domain.tenant.tenant_configuration import TenantConfiguration
from lpg.domain.tenant.warehouse import Warehouse
from lpg.infrastructure.persistence.models.tenant import (
    BranchModel,
    CylinderTypeModel,
    FeatureFlagOverrideModel,
    PriceListModel,
    TenantConfigurationModel,
    TenantModel,
    WarehouseModel,
)

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


class SqlAlchemyTenantRepository:
    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._uow = unit_of_work

    async def get(self, tenant_id: uuid.UUID) -> Tenant | None:
        row = await self._uow.session.get(TenantModel, tenant_id)
        if row is None:
            return None

        tenant = Tenant(
            row.id,
            row.name,
            row.slug,
            status=row.status,
            subscription_plan=row.subscription_plan,
            primary_contact_email=row.primary_contact_email,
            country=row.country,
            version=row.version,
        )
        self._uow.register_aggregate(tenant)
        return tenant

    async def save(self, tenant: Tenant) -> None:
        row = await self._uow.session.get(TenantModel, tenant.id)
        if row is None:
            msg = f"Cannot save tenant {tenant.id} — no matching row was loaded."
            raise LookupError(msg)

        row.name = tenant.name
        row.slug = tenant.slug
        row.status = tenant.status
        row.subscription_plan = tenant.subscription_plan
        row.primary_contact_email = tenant.primary_contact_email
        row.country = tenant.country


class SqlAlchemyBranchRepository:
    """Implements `BranchRepository` (`lpg.application.tenant.ports`)."""

    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._uow = unit_of_work

    async def get(self, branch_id: uuid.UUID) -> Branch | None:
        row = await self._uow.session.get(BranchModel, branch_id)
        if row is None:
            return None

        branch = Branch(row.id, row.tenant_id, row.name, row.region, version=row.version)
        self._uow.register_aggregate(branch)
        return branch

    async def list_for_tenant(self, tenant_id: uuid.UUID) -> Sequence[Branch]:
        # RLS already scopes this to the caller's own tenant; the explicit
        # filter is defense in depth, matching every other tenant-scoped
        # query in this codebase.
        result = await self._uow.session.execute(
            select(BranchModel)
            .where(BranchModel.tenant_id == tenant_id, BranchModel.is_deleted.is_(False))
            .order_by(BranchModel.name)
        )
        return [
            Branch(row.id, row.tenant_id, row.name, row.region, version=row.version)
            for row in result.scalars()
        ]

    async def add(self, branch: Branch) -> None:
        self._uow.session.add(
            BranchModel(
                id=branch.id,
                tenant_id=branch.tenant_id,
                name=branch.name,
                region=branch.region,
            )
        )
        self._uow.register_aggregate(branch)

    async def save(self, branch: Branch) -> None:
        row = await self._uow.session.get(BranchModel, branch.id)
        if row is None:
            msg = f"Cannot save branch {branch.id} — no matching row was loaded."
            raise LookupError(msg)

        row.name = branch.name
        row.region = branch.region


class SqlAlchemyWarehouseRepository:
    """Implements `WarehouseRepository` (`lpg.application.tenant.ports`)."""

    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._uow = unit_of_work

    async def get(self, warehouse_id: uuid.UUID) -> Warehouse | None:
        row = await self._uow.session.get(WarehouseModel, warehouse_id)
        if row is None:
            return None

        warehouse = Warehouse(
            row.id, row.tenant_id, row.branch_id, row.name, row.address_line, version=row.version
        )
        self._uow.register_aggregate(warehouse)
        return warehouse

    async def list_for_tenant(self, tenant_id: uuid.UUID) -> Sequence[Warehouse]:
        result = await self._uow.session.execute(
            select(WarehouseModel)
            .where(WarehouseModel.tenant_id == tenant_id, WarehouseModel.is_deleted.is_(False))
            .order_by(WarehouseModel.name)
        )
        return [
            Warehouse(
                row.id,
                row.tenant_id,
                row.branch_id,
                row.name,
                row.address_line,
                version=row.version,
            )
            for row in result.scalars()
        ]

    async def add(self, warehouse: Warehouse) -> None:
        self._uow.session.add(
            WarehouseModel(
                id=warehouse.id,
                tenant_id=warehouse.tenant_id,
                branch_id=warehouse.branch_id,
                name=warehouse.name,
                address_line=warehouse.address_line,
            )
        )
        self._uow.register_aggregate(warehouse)

    async def save(self, warehouse: Warehouse) -> None:
        row = await self._uow.session.get(WarehouseModel, warehouse.id)
        if row is None:
            msg = f"Cannot save warehouse {warehouse.id} — no matching row was loaded."
            raise LookupError(msg)

        row.name = warehouse.name
        row.address_line = warehouse.address_line


class SqlAlchemyCylinderTypeRepository:
    """Implements `CylinderTypeRepository` (`lpg.application.tenant.ports`)."""

    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._uow = unit_of_work

    async def get(self, cylinder_type_id: uuid.UUID) -> CylinderType | None:
        row = await self._uow.session.get(CylinderTypeModel, cylinder_type_id)
        if row is None:
            return None

        cylinder_type = CylinderType(
            row.id,
            row.tenant_id,
            row.name,
            row.weight_kg,
            is_active=row.is_active,
            version=row.version,
        )
        self._uow.register_aggregate(cylinder_type)
        return cylinder_type

    async def list_for_tenant(self, tenant_id: uuid.UUID) -> Sequence[CylinderType]:
        result = await self._uow.session.execute(
            select(CylinderTypeModel)
            .where(
                CylinderTypeModel.tenant_id == tenant_id, CylinderTypeModel.is_deleted.is_(False)
            )
            .order_by(CylinderTypeModel.name)
        )
        return [
            CylinderType(
                row.id,
                row.tenant_id,
                row.name,
                row.weight_kg,
                is_active=row.is_active,
                version=row.version,
            )
            for row in result.scalars()
        ]

    async def add(self, cylinder_type: CylinderType) -> None:
        self._uow.session.add(
            CylinderTypeModel(
                id=cylinder_type.id,
                tenant_id=cylinder_type.tenant_id,
                name=cylinder_type.name,
                weight_kg=cylinder_type.weight_kg,
                is_active=cylinder_type.is_active,
            )
        )
        self._uow.register_aggregate(cylinder_type)

    async def save(self, cylinder_type: CylinderType) -> None:
        row = await self._uow.session.get(CylinderTypeModel, cylinder_type.id)
        if row is None:
            msg = f"Cannot save cylinder type {cylinder_type.id} — no matching row was loaded."
            raise LookupError(msg)

        row.name = cylinder_type.name
        row.weight_kg = cylinder_type.weight_kg
        row.is_active = cylinder_type.is_active


class SqlAlchemyTenantConfigurationRepository:
    """Implements `TenantConfigurationRepository`
    (`lpg.application.tenant.ports`). Append-only — no `get`/`save`.
    """

    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._uow = unit_of_work

    async def list_for_tenant_and_key(
        self, tenant_id: uuid.UUID, config_key: str
    ) -> Sequence[TenantConfiguration]:
        result = await self._uow.session.execute(
            select(TenantConfigurationModel).where(
                TenantConfigurationModel.tenant_id == tenant_id,
                TenantConfigurationModel.config_key == config_key,
            )
        )
        return [
            TenantConfiguration(
                row.id, row.tenant_id, row.config_key, row.config_value, row.effective_from
            )
            for row in result.scalars()
        ]

    async def list_for_tenant(self, tenant_id: uuid.UUID) -> Sequence[TenantConfiguration]:
        result = await self._uow.session.execute(
            select(TenantConfigurationModel)
            .where(TenantConfigurationModel.tenant_id == tenant_id)
            .order_by(TenantConfigurationModel.config_key, TenantConfigurationModel.effective_from)
        )
        return [
            TenantConfiguration(
                row.id, row.tenant_id, row.config_key, row.config_value, row.effective_from
            )
            for row in result.scalars()
        ]

    async def add(self, config: TenantConfiguration) -> None:
        self._uow.session.add(
            TenantConfigurationModel(
                id=config.id,
                tenant_id=config.tenant_id,
                config_key=config.config_key,
                config_value=config.config_value,
                effective_from=config.effective_from,
            )
        )
        self._uow.register_aggregate(config)


class SqlAlchemyPriceListRepository:
    """Implements `PriceListRepository` (`lpg.application.tenant.ports`).
    Append-only — no `get`/`save`.
    """

    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._uow = unit_of_work

    async def list_for_tenant_and_cylinder_type(
        self, tenant_id: uuid.UUID, cylinder_type_id: uuid.UUID, customer_type: str
    ) -> Sequence[PriceListEntry]:
        result = await self._uow.session.execute(
            select(PriceListModel).where(
                PriceListModel.tenant_id == tenant_id,
                PriceListModel.cylinder_type_id == cylinder_type_id,
                PriceListModel.customer_type == customer_type,
            )
        )
        return [self._to_domain(row) for row in result.scalars()]

    async def list_for_tenant(self, tenant_id: uuid.UUID) -> Sequence[PriceListEntry]:
        result = await self._uow.session.execute(
            select(PriceListModel)
            .where(PriceListModel.tenant_id == tenant_id)
            .order_by(PriceListModel.effective_from)
        )
        return [self._to_domain(row) for row in result.scalars()]

    async def add(self, entry: PriceListEntry) -> None:
        self._uow.session.add(
            PriceListModel(
                id=entry.id,
                tenant_id=entry.tenant_id,
                cylinder_type_id=entry.cylinder_type_id,
                customer_type=entry.customer_type,
                branch_id=entry.branch_id,
                price=entry.price,
                effective_from=entry.effective_from,
            )
        )
        self._uow.register_aggregate(entry)

    @staticmethod
    def _to_domain(row: PriceListModel) -> PriceListEntry:
        return PriceListEntry(
            row.id,
            row.tenant_id,
            row.cylinder_type_id,
            row.customer_type,
            row.price,
            row.effective_from,
            branch_id=row.branch_id,
        )


class SqlAlchemyFeatureFlagOverrideRepository:
    """Implements `FeatureFlagOverrideRepository`
    (`lpg.application.platform.ports`). Lives here, not
    `repositories/platform.py`, for the same persistence-schema-boundary
    reason `FeatureFlagOverrideModel` does (see that model's docstring).
    """

    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._uow = unit_of_work

    async def get_for_tenant_and_flag(
        self, tenant_id: uuid.UUID, flag_key: str
    ) -> FeatureFlagOverride | None:
        result = await self._uow.session.execute(
            select(FeatureFlagOverrideModel).where(
                FeatureFlagOverrideModel.tenant_id == tenant_id,
                FeatureFlagOverrideModel.flag_key == flag_key,
            )
        )
        row = result.scalars().first()
        if row is None:
            return None

        override = self._to_domain(row)
        self._uow.register_aggregate(override)
        return override

    async def list_for_tenant(self, tenant_id: uuid.UUID) -> Sequence[FeatureFlagOverride]:
        result = await self._uow.session.execute(
            select(FeatureFlagOverrideModel).where(FeatureFlagOverrideModel.tenant_id == tenant_id)
        )
        return [self._to_domain(row) for row in result.scalars()]

    async def add(self, override: FeatureFlagOverride) -> None:
        self._uow.session.add(
            FeatureFlagOverrideModel(
                id=override.id,
                tenant_id=override.tenant_id,
                flag_key=override.flag_key,
                is_enabled=override.is_enabled,
            )
        )
        self._uow.register_aggregate(override)

    async def save(self, override: FeatureFlagOverride) -> None:
        row = await self._uow.session.get(FeatureFlagOverrideModel, override.id)
        if row is None:
            msg = f"Cannot save feature flag override {override.id} — no matching row was loaded."
            raise LookupError(msg)

        row.is_enabled = override.is_enabled

    @staticmethod
    def _to_domain(row: FeatureFlagOverrideModel) -> FeatureFlagOverride:
        return FeatureFlagOverride(
            row.id, row.tenant_id, row.flag_key, is_enabled=row.is_enabled, version=row.version
        )
