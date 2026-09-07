"""Use cases for the `compliance` bounded context — Weighment Part 1 (scale
registry: register / list / replace certificate / set status)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command, Query
from lpg.domain.compliance.scale import Scale

if TYPE_CHECKING:
    import uuid
    from datetime import date

    from lpg.application.common.ports import UnitOfWork
    from lpg.application.compliance.ports import ScaleRepository

# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RegisterScaleCommand(Command):
    tenant_id: uuid.UUID
    warehouse_id: uuid.UUID
    asset_tag: str
    least_count_grams: int
    certificate_ref: str
    certificate_expiry_date: date
    make: str | None = None
    model: str | None = None


class RegisterScaleUseCase:
    def __init__(self, repository: ScaleRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: RegisterScaleCommand) -> Scale:
        from lpg.application.common.errors import DuplicateScaleAssetTagError

        existing = await self._repository.get_by_warehouse_and_asset_tag(
            command.warehouse_id, command.asset_tag
        )
        if existing is not None:
            msg = f"A scale tagged '{command.asset_tag}' is already registered at this warehouse."
            raise DuplicateScaleAssetTagError(msg)

        scale = Scale(
            scale_id=self._repository.next_id(),
            tenant_id=command.tenant_id,
            warehouse_id=command.warehouse_id,
            asset_tag=command.asset_tag,
            least_count_grams=command.least_count_grams,
            certificate_ref=command.certificate_ref,
            certificate_expiry_date=command.certificate_expiry_date,
            make=command.make,
            model=command.model,
        )
        await self._repository.save(scale)
        await self._unit_of_work.commit()
        return scale


# ---------------------------------------------------------------------------
# Replace certificate (recalibration)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReplaceScaleCertificateCommand(Command):
    scale_id: uuid.UUID
    certificate_ref: str
    certificate_expiry_date: date


class ReplaceScaleCertificateUseCase:
    def __init__(self, repository: ScaleRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: ReplaceScaleCertificateCommand) -> Scale:
        from lpg.application.common.errors import NotFoundError

        scale = await self._repository.get_by_id(command.scale_id)
        if scale is None:
            msg = f"Scale {command.scale_id} not found."
            raise NotFoundError(msg)

        scale.replace_certificate(
            certificate_ref=command.certificate_ref,
            certificate_expiry_date=command.certificate_expiry_date,
        )
        await self._repository.save(scale)
        await self._unit_of_work.commit()
        return scale


# ---------------------------------------------------------------------------
# Set status (active/inactive)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SetScaleStatusCommand(Command):
    scale_id: uuid.UUID
    status: str


class SetScaleStatusUseCase:
    def __init__(self, repository: ScaleRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: SetScaleStatusCommand) -> Scale:
        from lpg.application.common.errors import NotFoundError

        scale = await self._repository.get_by_id(command.scale_id)
        if scale is None:
            msg = f"Scale {command.scale_id} not found."
            raise NotFoundError(msg)

        scale.set_status(command.status)
        await self._repository.save(scale)
        await self._unit_of_work.commit()
        return scale


# ---------------------------------------------------------------------------
# List / get
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ListScalesQuery(Query):
    status: str | None = None
    expiry: str | None = None
    skip: int = 0
    limit: int = 50


class ListScalesUseCase:
    def __init__(self, repository: ScaleRepository) -> None:
        self._repository = repository

    async def execute(self, query: ListScalesQuery) -> tuple[list[Scale], int]:
        scales = await self._repository.list_for_tenant(
            status=query.status, expiry=query.expiry, skip=query.skip, limit=query.limit
        )
        total = await self._repository.count_for_tenant(status=query.status, expiry=query.expiry)
        return scales, total
