"""`SetPriceUseCase` / `GetEffectivePriceUseCase` / `ListPricesUseCase`.

"Setting" a price always inserts a new historized row — see
`lpg.domain.tenant.price_list`'s module docstring.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command
from lpg.domain.tenant.price_list import EffectivePriceResolver, PriceListEntry

if TYPE_CHECKING:
    from decimal import Decimal

    from lpg.application.common.ports import UnitOfWork
    from lpg.application.tenant.ports import PriceListRepository


@dataclass(frozen=True, slots=True)
class SetPriceCommand(Command):
    tenant_id: uuid.UUID
    cylinder_type_id: uuid.UUID
    customer_type: str
    price: Decimal
    branch_id: uuid.UUID | None = None
    effective_from: datetime | None = None


class SetPriceUseCase:
    def __init__(self, repository: PriceListRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: SetPriceCommand) -> PriceListEntry:
        entry = PriceListEntry(
            uuid.uuid4(),
            command.tenant_id,
            command.cylinder_type_id,
            command.customer_type,
            command.price,
            command.effective_from or datetime.now(UTC),
            branch_id=command.branch_id,
        )
        await self._repository.add(entry)
        await self._unit_of_work.commit()
        return entry


@dataclass(frozen=True, slots=True)
class GetEffectivePriceQuery:
    tenant_id: uuid.UUID
    cylinder_type_id: uuid.UUID
    customer_type: str
    branch_id: uuid.UUID | None = None
    at: datetime | None = None


class GetEffectivePriceUseCase:
    def __init__(self, repository: PriceListRepository) -> None:
        self._repository = repository

    async def execute(self, query: GetEffectivePriceQuery) -> PriceListEntry | None:
        entries = await self._repository.list_for_tenant_and_cylinder_type(
            query.tenant_id, query.cylinder_type_id, query.customer_type
        )
        return EffectivePriceResolver.resolve(
            entries,
            cylinder_type_id=query.cylinder_type_id,
            customer_type=query.customer_type,
            branch_id=query.branch_id,
            at=query.at or datetime.now(UTC),
        )


@dataclass(frozen=True, slots=True)
class ListPricesQuery:
    tenant_id: uuid.UUID


class ListPricesUseCase:
    def __init__(self, repository: PriceListRepository) -> None:
        self._repository = repository

    async def execute(self, query: ListPricesQuery) -> list[PriceListEntry]:
        return list(await self._repository.list_for_tenant(query.tenant_id))
