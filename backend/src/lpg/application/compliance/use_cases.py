"""Use cases for the `compliance` bounded context — Weighment Part 1 (scale
registry: register / list / replace certificate / set status)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command, Query
from lpg.domain.compliance.scale import Scale
from lpg.domain.compliance.weighment_record import (
    WeighmentRecord,
    compute_weighment_result,
)

if TYPE_CHECKING:
    import uuid
    from datetime import date

    from lpg.application.common.ports import UnitOfWork
    from lpg.application.compliance.ports import ScaleRepository, WeighmentRecordRepository
    from lpg.application.tenant.ports import TenantConfigurationRepository

#: Fallback when a tenant has no `weighment_tolerance_grams` configuration
#: entry of its own. Legal Metrology (Packaged Commodities) Rules, 2011 —
#: 150 g permissible shortage on a 14.2 kg domestic cylinder. A **new
#: finding** from this session's own research, not previously in this
#: repo's `docs/research/feature-gap-analysis.md` (§7.5 said this "was not
#: retrieved as a numeric value") — confirm against the tenant's own OMC
#: before relying on this default at go-live, same as every other number in
#: this subsystem.
DEFAULT_WEIGHMENT_TOLERANCE_GRAMS = 150

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


# ---------------------------------------------------------------------------
# Record a weighment check (goods-receipt sample or load-out full check)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RecordWeighmentCommand(Command):
    tenant_id: uuid.UUID
    scale_id: uuid.UUID
    context: str
    reference_type: str
    reference_id: uuid.UUID
    cylinder_type_id: uuid.UUID
    total_cylinders_in_batch: int
    cylinders_checked: int
    underweight_cylinder_count: int
    recorded_by: uuid.UUID


class RecordWeighmentUseCase:
    """Resolves the tenant's `weighment_tolerance_grams` (falling back to
    `DEFAULT_WEIGHMENT_TOLERANCE_GRAMS`) and snapshots it onto the record —
    the same fallback-and-snapshot pattern `check_compliance_expiry`
    (`infrastructure/jobs/compliance_jobs.py`) already established for
    `compliance_expiry_lead_days`."""

    def __init__(
        self,
        weighment_repository: WeighmentRecordRepository,
        scale_repository: ScaleRepository,
        tenant_config_repository: TenantConfigurationRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._weighment_repository = weighment_repository
        self._scale_repository = scale_repository
        self._tenant_config_repository = tenant_config_repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: RecordWeighmentCommand) -> WeighmentRecord:
        from datetime import UTC, datetime

        from lpg.application.common.errors import NotFoundError
        from lpg.application.tenant.tenant_configuration import (
            GetEffectiveTenantConfigurationQuery,
            GetEffectiveTenantConfigurationUseCase,
        )

        scale = await self._scale_repository.get_by_id(command.scale_id)
        if scale is None:
            msg = f"Scale {command.scale_id} not found."
            raise NotFoundError(msg)

        tolerance_grams = DEFAULT_WEIGHMENT_TOLERANCE_GRAMS
        config = await GetEffectiveTenantConfigurationUseCase(
            self._tenant_config_repository
        ).execute(
            GetEffectiveTenantConfigurationQuery(
                tenant_id=command.tenant_id, config_key="weighment_tolerance_grams"
            )
        )
        if config is not None:
            try:
                tolerance_grams = int(config.config_value)
            except (TypeError, ValueError):
                from lpg.config.logging import get_logger

                get_logger(__name__).warning(
                    "weighment_tolerance_grams_invalid",
                    tenant_id=str(command.tenant_id),
                    value=config.config_value,
                )

        record = WeighmentRecord(
            id=self._weighment_repository.next_id(),
            tenant_id=command.tenant_id,
            scale_id=command.scale_id,
            context=command.context,
            reference_type=command.reference_type,
            reference_id=command.reference_id,
            cylinder_type_id=command.cylinder_type_id,
            total_cylinders_in_batch=command.total_cylinders_in_batch,
            cylinders_checked=command.cylinders_checked,
            underweight_cylinder_count=command.underweight_cylinder_count,
            tolerance_grams_applied=tolerance_grams,
            result=compute_weighment_result(command.underweight_cylinder_count),
            recorded_by=command.recorded_by,
            recorded_at=datetime.now(UTC),
        )
        await self._weighment_repository.add(record)
        await self._unit_of_work.commit()
        return record


@dataclass(frozen=True, slots=True)
class ListWeighmentRecordsQuery(Query):
    reference_type: str
    reference_id: uuid.UUID


class ListWeighmentRecordsUseCase:
    def __init__(self, repository: WeighmentRecordRepository) -> None:
        self._repository = repository

    async def execute(self, query: ListWeighmentRecordsQuery) -> list[WeighmentRecord]:
        return await self._repository.list_for_reference(query.reference_type, query.reference_id)
