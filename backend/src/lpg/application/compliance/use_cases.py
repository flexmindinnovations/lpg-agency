"""Use cases for the `compliance` bounded context — Weighment Part 1 (scale
registry: register / list / replace certificate / set status)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command, Query
from lpg.domain.compliance.cylinder_unit import CylinderUnit, default_test_due_date
from lpg.domain.compliance.scale import Scale
from lpg.domain.compliance.weighment_record import (
    WeighmentRecord,
    compute_weighment_result,
)

if TYPE_CHECKING:
    import uuid
    from datetime import date

    from lpg.application.common.ports import UnitOfWork
    from lpg.application.compliance.ports import (
        CylinderUnitRepository,
        ScaleRepository,
        WeighmentRecordRepository,
    )
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


# ---------------------------------------------------------------------------
# Cylinder Identity (Phase 20 subsystem 3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RegisterCylinderUnitCommand(Command):
    tenant_id: uuid.UUID
    cylinder_type_id: uuid.UUID
    serial_number: str
    condition_status: str
    custody_type: str
    qr_code: str | None = None
    custody_ref_id: uuid.UUID | None = None
    manufacture_date: date | None = None
    owner_omc: str | None = None


class RegisterCylinderUnitUseCase:
    def __init__(self, repository: CylinderUnitRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: RegisterCylinderUnitCommand) -> CylinderUnit:
        from lpg.application.common.errors import (
            DuplicateCylinderQRCodeError,
            DuplicateCylinderSerialNumberError,
        )

        existing = await self._repository.get_by_serial(command.serial_number)
        if existing is not None:
            msg = f"A cylinder unit with serial '{command.serial_number}' is already registered."
            raise DuplicateCylinderSerialNumberError(msg)

        qr_code = (
            command.qr_code.strip()
            if command.qr_code and command.qr_code.strip()
            else f"CYL-{command.serial_number}"
        )
        existing_qr = await self._repository.get_by_qr_code(qr_code)
        if existing_qr is not None:
            msg = f"A cylinder unit with QR code '{qr_code}' is already registered."
            raise DuplicateCylinderQRCodeError(msg)

        unit = CylinderUnit(
            cylinder_unit_id=self._repository.next_id(),
            tenant_id=command.tenant_id,
            cylinder_type_id=command.cylinder_type_id,
            serial_number=command.serial_number,
            qr_code=qr_code,
            condition_status=command.condition_status,
            custody_type=command.custody_type,
            custody_ref_id=command.custody_ref_id,
            manufacture_date=command.manufacture_date,
            owner_omc=command.owner_omc,
        )
        await self._repository.save(unit)
        await self._unit_of_work.commit()
        return unit


@dataclass(frozen=True, slots=True)
class RecordStatutoryTestCommand(Command):
    cylinder_unit_id: uuid.UUID
    tested_at: date
    due_date: date
    performed_by: uuid.UUID


class RecordStatutoryTestUseCase:
    """`due_date` is always the caller's own value — this use case never
    substitutes one. `suggest_due_date` (a separate read helper, not part
    of this command) is what a caller-facing form would call first to
    populate a suggested value the user can then confirm/override; see
    `SuggestStatutoryTestDueDateUseCase`."""

    def __init__(self, repository: CylinderUnitRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: RecordStatutoryTestCommand) -> CylinderUnit:
        from lpg.application.common.errors import NotFoundError

        unit = await self._repository.get_by_id(command.cylinder_unit_id)
        if unit is None:
            msg = f"Cylinder unit {command.cylinder_unit_id} not found."
            raise NotFoundError(msg)

        unit.record_statutory_test(
            tested_at=command.tested_at,
            due_date=command.due_date,
            performed_by=command.performed_by,
        )
        await self._repository.save(unit)
        await self._unit_of_work.commit()
        return unit


@dataclass(frozen=True, slots=True)
class SuggestStatutoryTestDueDateQuery(Query):
    """Not tied to any specific unit — a tenant-wide suggestion only, the
    caller applies it (or not) when submitting `RecordStatutoryTestCommand`."""

    tenant_id: uuid.UUID
    tested_at: date


class SuggestStatutoryTestDueDateUseCase:
    """Resolves `cylinder_statutory_test_interval_months` and returns a
    suggested due date — `None` if the tenant has never set the key (no
    guessed interval, ever). Never called by `RecordStatutoryTestUseCase`
    itself; a caller (typically the API layer, for a form's "suggest"
    action) uses this separately."""

    def __init__(self, tenant_config_repository: TenantConfigurationRepository) -> None:
        self._tenant_config_repository = tenant_config_repository

    async def execute(self, query: SuggestStatutoryTestDueDateQuery) -> date | None:
        from lpg.application.tenant.tenant_configuration import (
            GetEffectiveTenantConfigurationQuery,
            GetEffectiveTenantConfigurationUseCase,
        )

        config = await GetEffectiveTenantConfigurationUseCase(
            self._tenant_config_repository
        ).execute(
            GetEffectiveTenantConfigurationQuery(
                tenant_id=query.tenant_id, config_key="cylinder_statutory_test_interval_months"
            )
        )
        if config is None:
            return None
        try:
            interval_months = int(config.config_value)
        except (TypeError, ValueError):
            from lpg.config.logging import get_logger

            get_logger(__name__).warning(
                "cylinder_statutory_test_interval_months_invalid",
                tenant_id=str(query.tenant_id),
                value=config.config_value,
            )
            return None
        return default_test_due_date(query.tested_at, interval_months)


@dataclass(frozen=True, slots=True)
class MoveCylinderCustodyCommand(Command):
    cylinder_unit_id: uuid.UUID
    custody_type: str
    custody_ref_id: uuid.UUID | None
    performed_by: uuid.UUID


class MoveCylinderCustodyUseCase:
    def __init__(self, repository: CylinderUnitRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: MoveCylinderCustodyCommand) -> CylinderUnit:
        from lpg.application.common.errors import NotFoundError

        unit = await self._repository.get_by_id(command.cylinder_unit_id)
        if unit is None:
            msg = f"Cylinder unit {command.cylinder_unit_id} not found."
            raise NotFoundError(msg)

        unit.move_custody(
            custody_type=command.custody_type,
            custody_ref_id=command.custody_ref_id,
            performed_by=command.performed_by,
        )
        await self._repository.save(unit)
        await self._unit_of_work.commit()
        return unit


@dataclass(frozen=True, slots=True)
class ChangeCylinderConditionStatusCommand(Command):
    cylinder_unit_id: uuid.UUID
    new_status: str
    performed_by: uuid.UUID
    reason: str | None = None


class ChangeCylinderConditionStatusUseCase:
    def __init__(self, repository: CylinderUnitRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: ChangeCylinderConditionStatusCommand) -> CylinderUnit:
        from lpg.application.common.errors import NotFoundError

        unit = await self._repository.get_by_id(command.cylinder_unit_id)
        if unit is None:
            msg = f"Cylinder unit {command.cylinder_unit_id} not found."
            raise NotFoundError(msg)

        unit.change_condition_status(
            new_status=command.new_status,
            performed_by=command.performed_by,
            reason=command.reason,
        )
        await self._repository.save(unit)
        await self._unit_of_work.commit()
        return unit


@dataclass(frozen=True, slots=True)
class ReceiveCylinderUnitCommand(Command):
    cylinder_unit_id: uuid.UUID
    warehouse_id: uuid.UUID
    performed_by: uuid.UUID


class ReceiveCylinderUnitUseCase:
    """Rule 26, Gas Cylinders Rules 2016 — the actual regulatory block.
    Checks `is_due_for_test()` itself and raises
    `CylinderDueForStatutoryTestError` (409) *before* calling the domain's
    `receive()` command, which stays pure/clock-free. Matches
    `LoadVehicleForRouteUseCase`'s own precedent for an MDG-rule block
    (application-layer check, 409), not `Scale`/`InventoryLocation`'s
    domain-invariant pattern (422)."""

    def __init__(self, repository: CylinderUnitRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: ReceiveCylinderUnitCommand) -> CylinderUnit:
        from datetime import UTC, datetime

        from lpg.application.common.errors import CylinderDueForStatutoryTestError, NotFoundError

        unit = await self._repository.get_by_id(command.cylinder_unit_id)
        if unit is None:
            msg = f"Cylinder unit {command.cylinder_unit_id} not found."
            raise NotFoundError(msg)

        if unit.is_due_for_test(as_of=datetime.now(UTC).date()):
            msg = (
                f"Cylinder unit {unit.serial_number} is due for statutory retest "
                f"(due {unit.test_due_date}) and cannot be received into stock — "
                "segregate and return it to the bottling plant (MDG 2022 cl. 1.4(b))."
            )
            raise CylinderDueForStatutoryTestError(msg, cylinder_unit_id=str(unit.id))

        unit.receive(warehouse_id=command.warehouse_id, performed_by=command.performed_by)
        await self._repository.save(unit)
        await self._unit_of_work.commit()
        return unit


@dataclass(frozen=True, slots=True)
class RetireCylinderUnitCommand(Command):
    cylinder_unit_id: uuid.UUID
    performed_by: uuid.UUID


class RetireCylinderUnitUseCase:
    def __init__(self, repository: CylinderUnitRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: RetireCylinderUnitCommand) -> CylinderUnit:
        from lpg.application.common.errors import NotFoundError

        unit = await self._repository.get_by_id(command.cylinder_unit_id)
        if unit is None:
            msg = f"Cylinder unit {command.cylinder_unit_id} not found."
            raise NotFoundError(msg)

        unit.retire(performed_by=command.performed_by)
        await self._repository.save(unit)
        await self._unit_of_work.commit()
        return unit


@dataclass(frozen=True, slots=True)
class GetCylinderUnitQuery(Query):
    cylinder_unit_id: uuid.UUID


class GetCylinderUnitUseCase:
    def __init__(self, repository: CylinderUnitRepository) -> None:
        self._repository = repository

    async def execute(self, query: GetCylinderUnitQuery) -> CylinderUnit | None:
        return await self._repository.get_by_id(query.cylinder_unit_id)


@dataclass(frozen=True, slots=True)
class ListCylinderUnitsQuery(Query):
    due_status: str | None = None
    cylinder_type_id: uuid.UUID | None = None
    custody_type: str | None = None
    skip: int = 0
    limit: int = 50


class ListCylinderUnitsUseCase:
    def __init__(self, repository: CylinderUnitRepository) -> None:
        self._repository = repository

    async def execute(self, query: ListCylinderUnitsQuery) -> tuple[list[CylinderUnit], int]:
        units = await self._repository.list_for_tenant(
            due_status=query.due_status,
            cylinder_type_id=query.cylinder_type_id,
            custody_type=query.custody_type,
            skip=query.skip,
            limit=query.limit,
        )
        total = await self._repository.count_for_tenant(
            due_status=query.due_status,
            cylinder_type_id=query.cylinder_type_id,
            custody_type=query.custody_type,
        )
        return units, total


@dataclass(frozen=True, slots=True)
class LookupCylinderUnitQuery(Query):
    code: str


class LookupCylinderUnitUseCase:
    def __init__(self, repository: CylinderUnitRepository) -> None:
        self._repository = repository

    async def execute(self, query: LookupCylinderUnitQuery) -> CylinderUnit | None:
        return await self._repository.lookup_by_code(query.code.strip())


@dataclass(frozen=True, slots=True)
class BatchMoveCylinderCustodyCommand(Command):
    cylinder_unit_ids: list[uuid.UUID]
    custody_type: str
    custody_ref_id: uuid.UUID | None
    performed_by: uuid.UUID


class BatchMoveCylinderCustodyUseCase:
    def __init__(self, repository: CylinderUnitRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: BatchMoveCylinderCustodyCommand) -> list[CylinderUnit]:
        from lpg.application.common.errors import NotFoundError

        moved_units: list[CylinderUnit] = []
        for unit_id in command.cylinder_unit_ids:
            unit = await self._repository.get_by_id(unit_id)
            if unit is None:
                msg = f"Cylinder unit {unit_id} not found."
                raise NotFoundError(msg)
            unit.move_custody(
                custody_type=command.custody_type,
                custody_ref_id=command.custody_ref_id,
                performed_by=command.performed_by,
            )
            await self._repository.save(unit)
            moved_units.append(unit)

        await self._unit_of_work.commit()
        return moved_units
