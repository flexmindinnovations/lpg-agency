"""API router for the `compliance` bounded context — Weighment Part 1 (scale
registry, `planning/features/20-regulatory-compliance` subsystem 1) and TDT
rating (subsystem 2)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException, Response

from lpg.api.v1.dependencies.admin import get_cylinder_type_repository
from lpg.api.v1.dependencies.compliance import (
    get_batch_move_cylinder_custody_use_case,
    get_change_cylinder_condition_status_use_case,
    get_cylinder_unit_repository,
    get_live_tdt_projection_use_case,
    get_lookup_cylinder_unit_use_case,
    get_move_cylinder_custody_use_case,
    get_quarterly_tdt_rating_use_case,
    get_receive_cylinder_unit_use_case,
    get_record_statutory_test_use_case,
    get_record_weighment_use_case,
    get_register_cylinder_unit_use_case,
    get_retire_cylinder_unit_use_case,
    get_scale_repository,
    get_suggest_statutory_test_due_date_use_case,
    get_weighment_record_repository,
)
from lpg.api.v1.dependencies.identity import get_current_principal, require_permission
from lpg.api.v1.dependencies.order import get_file_storage
from lpg.api.v1.dependencies.printing import get_printing_engine
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.api.v1.schemas.compliance import (
    BatchMoveCylinderCustodyRequest,
    BatchMoveCylinderCustodyResponse,
    ChangeCylinderConditionStatusRequest,
    CylinderUnitListResponse,
    CylinderUnitResponse,
    MoveCylinderCustodyRequest,
    ReceiveCylinderUnitRequest,
    RecordCylinderStatutoryTestRequest,
    RecordWeighmentRequest,
    RegisterCylinderUnitRequest,
    RegisterScaleRequest,
    ReplaceScaleCertificateRequest,
    ScaleListResponse,
    ScaleResponse,
    SetScaleStatusRequest,
    SuggestCylinderTestDueDateResponse,
    TdtBandDistributionResponse,
    TdtQuarterlyRatingResponse,
    WeighmentRecordListResponse,
    WeighmentRecordResponse,
)
from lpg.application.common.errors import ConflictError, NotFoundError
from lpg.application.common.ports import FileStorage, UnitOfWork
from lpg.application.compliance.ports import (
    CylinderUnitRepository,
    ScaleRepository,
    WeighmentRecordRepository,
)
from lpg.application.compliance.queries.get_tdt_rating import (
    GetLiveTdtProjectionQuery,
    GetLiveTdtProjectionUseCase,
    GetQuarterlyTdtRatingQuery,
    GetQuarterlyTdtRatingUseCase,
    current_quarter_bounds,
)
from lpg.application.compliance.use_cases import (
    BatchMoveCylinderCustodyCommand,
    BatchMoveCylinderCustodyUseCase,
    ChangeCylinderConditionStatusCommand,
    ChangeCylinderConditionStatusUseCase,
    GetCylinderUnitQuery,
    GetCylinderUnitUseCase,
    ListCylinderUnitsQuery,
    ListCylinderUnitsUseCase,
    ListScalesQuery,
    ListScalesUseCase,
    ListWeighmentRecordsQuery,
    ListWeighmentRecordsUseCase,
    LookupCylinderUnitQuery,
    LookupCylinderUnitUseCase,
    MoveCylinderCustodyCommand,
    MoveCylinderCustodyUseCase,
    ReceiveCylinderUnitCommand,
    ReceiveCylinderUnitUseCase,
    RecordStatutoryTestCommand,
    RecordStatutoryTestUseCase,
    RecordWeighmentCommand,
    RecordWeighmentUseCase,
    RegisterCylinderUnitCommand,
    RegisterCylinderUnitUseCase,
    RegisterScaleCommand,
    RegisterScaleUseCase,
    ReplaceScaleCertificateCommand,
    ReplaceScaleCertificateUseCase,
    RetireCylinderUnitCommand,
    RetireCylinderUnitUseCase,
    SetScaleStatusCommand,
    SetScaleStatusUseCase,
    SuggestStatutoryTestDueDateQuery,
    SuggestStatutoryTestDueDateUseCase,
)
from lpg.application.identity.ports import AuthenticatedPrincipal
from lpg.application.printing.ports import PrintingEngine
from lpg.application.tenant.ports import CylinderTypeRepository
from lpg.domain.common.base import DomainError

if TYPE_CHECKING:
    from lpg.domain.compliance.cylinder_unit import CylinderUnit
    from lpg.domain.compliance.scale import Scale
    from lpg.domain.compliance.tdt_rating import TdtQuarterlyRating
    from lpg.domain.compliance.weighment_record import WeighmentRecord

router = APIRouter(prefix="/scales", tags=["Compliance — Weighment"])

#: Weighment-record endpoints are nested under the GRN/route resource they
#: evidence (`/goods-receipt-notes/{grn_id}/weighment`,
#: `/routes/{route_id}/weighment`), not under `/scales` — a second router,
#: same file, both registered in `app.py`.
weighment_router = APIRouter(tags=["Compliance — Weighment"])

#: TDT rating endpoints — read-only, own `tdt:read` permission (no
#: `tdt:configure`: the band/fine-schedule reference data is written
#: through the existing `tenant:configure`-gated
#: `POST /admin/tenant-configuration`, not a dedicated endpoint here).
tdt_rating_router = APIRouter(prefix="/tdt-rating", tags=["Compliance — TDT Rating"])

#: Cylinder Identity endpoints (Phase 20 subsystem 3) — a narrow, additive
#: registry. `cylinder_units:manage` for every mutation, `cylinder_units:
#: read` (wider role list, includes dispatcher) for the registry/detail
#: reads.
cylinder_units_router = APIRouter(prefix="/cylinder-units", tags=["Compliance — Cylinder Identity"])


async def _to_response(scale: Scale, file_storage: FileStorage) -> ScaleResponse:
    certificate_url = (
        await file_storage.url(scale.certificate_ref) if scale.certificate_ref else None
    )
    return ScaleResponse(
        id=scale.id,
        warehouse_id=scale.warehouse_id,
        asset_tag=scale.asset_tag,
        make=scale.make,
        model=scale.model,
        least_count_grams=scale.least_count_grams,
        certificate_url=certificate_url,
        certificate_expiry_date=scale.certificate_expiry_date,
        status=scale.status,
        is_expired=scale.is_expired(),
    )


@router.post(
    "",
    response_model=ScaleResponse,
    status_code=201,
    dependencies=[Depends(require_permission("weighment:manage"))],
)
async def register_scale(
    request: RegisterScaleRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[ScaleRepository, Depends(get_scale_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    file_storage: Annotated[FileStorage, Depends(get_file_storage)],
) -> ScaleResponse:
    """Register a scale — MDG 2022 cl. 1.2(ii)(iii) requires least count
    <=10g and a valid calibration certificate; both are enforced as domain
    invariants on `Scale`, not just request validation."""
    use_case = RegisterScaleUseCase(repository, unit_of_work)
    try:
        scale = await use_case.execute(
            RegisterScaleCommand(
                tenant_id=principal.tenant_id,
                warehouse_id=request.warehouse_id,
                asset_tag=request.asset_tag,
                least_count_grams=request.least_count_grams,
                certificate_ref=request.certificate_ref,
                certificate_expiry_date=request.certificate_expiry_date,
                make=request.make,
                model=request.model,
            )
        )
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=exc.message) from exc
    except DomainError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    return await _to_response(scale, file_storage)


@router.get(
    "",
    response_model=ScaleListResponse,
    dependencies=[Depends(require_permission("weighment:record"))],
)
async def list_scales(
    repository: Annotated[ScaleRepository, Depends(get_scale_repository)],
    file_storage: Annotated[FileStorage, Depends(get_file_storage)],
    status: str | None = None,
    expiry: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> ScaleListResponse:
    """Tenant-wide scale registry for the dashboard — `expiry` is
    `expiring` (<=30 days) or `expired`, same semantics as
    `GET /compliance-documents`. Readable by anyone who can *record* a
    weighment check, not just manage the registry — a warehouse worker
    picking which scale to use doesn't need `weighment:manage`."""
    use_case = ListScalesUseCase(repository)
    scales, total = await use_case.execute(
        ListScalesQuery(status=status, expiry=expiry, skip=skip, limit=limit)
    )
    items = [await _to_response(s, file_storage) for s in scales]
    return ScaleListResponse(items=items, total=total)


@router.put(
    "/{scale_id}/certificate",
    response_model=ScaleResponse,
    dependencies=[Depends(require_permission("weighment:manage"))],
)
async def replace_scale_certificate(
    scale_id: uuid.UUID,
    request: ReplaceScaleCertificateRequest,
    repository: Annotated[ScaleRepository, Depends(get_scale_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    file_storage: Annotated[FileStorage, Depends(get_file_storage)],
) -> ScaleResponse:
    """Recalibration — a renewed certificate supersedes the old one in
    place, same asset. MDG has no assumed reverification interval to check
    against here; this just records the new validity window."""
    use_case = ReplaceScaleCertificateUseCase(repository, unit_of_work)
    try:
        scale = await use_case.execute(
            ReplaceScaleCertificateCommand(
                scale_id=scale_id,
                certificate_ref=request.certificate_ref,
                certificate_expiry_date=request.certificate_expiry_date,
            )
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except DomainError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    return await _to_response(scale, file_storage)


def _weighment_to_response(record: WeighmentRecord) -> WeighmentRecordResponse:
    return WeighmentRecordResponse(
        id=record.id,
        scale_id=record.scale_id,
        context=record.context,
        reference_type=record.reference_type,
        reference_id=record.reference_id,
        cylinder_type_id=record.cylinder_type_id,
        total_cylinders_in_batch=record.total_cylinders_in_batch,
        cylinders_checked=record.cylinders_checked,
        underweight_cylinder_count=record.underweight_cylinder_count,
        tolerance_grams_applied=record.tolerance_grams_applied,
        result=record.result,
        recorded_by=record.recorded_by,
        recorded_at=record.recorded_at,
    )


@weighment_router.post(
    "/goods-receipt-notes/{grn_id}/weighment",
    response_model=WeighmentRecordResponse,
    status_code=201,
    dependencies=[Depends(require_permission("weighment:record"))],
)
async def record_goods_receipt_weighment(
    grn_id: uuid.UUID,
    request: RecordWeighmentRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    use_case: Annotated[RecordWeighmentUseCase, Depends(get_record_weighment_use_case)],
) -> WeighmentRecordResponse:
    """MDG 2022 cl. 1.2(iv) — 10% of filled cylinders weighed randomly on
    receipt. Non-blocking: this records evidence a sample was checked, it
    does not gate `POST .../goods-receipt-notes` itself (weighing the
    physical sample happens after the truck is logged in, not atomically
    with it)."""
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="An acting user is required.")
    try:
        record = await use_case.execute(
            RecordWeighmentCommand(
                tenant_id=principal.tenant_id,
                scale_id=request.scale_id,
                context="goods_receipt_sample",
                reference_type="grn",
                reference_id=grn_id,
                cylinder_type_id=request.cylinder_type_id,
                total_cylinders_in_batch=request.total_cylinders_in_batch,
                cylinders_checked=request.cylinders_checked,
                underweight_cylinder_count=request.underweight_cylinder_count,
                recorded_by=principal.user_id,
            )
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except DomainError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    return _weighment_to_response(record)


@weighment_router.get(
    "/goods-receipt-notes/{grn_id}/weighment",
    response_model=WeighmentRecordListResponse,
    dependencies=[Depends(require_permission("weighment:record"))],
)
async def list_goods_receipt_weighments(
    grn_id: uuid.UUID,
    repository: Annotated[WeighmentRecordRepository, Depends(get_weighment_record_repository)],
) -> WeighmentRecordListResponse:
    use_case = ListWeighmentRecordsUseCase(repository)
    records = await use_case.execute(
        ListWeighmentRecordsQuery(reference_type="grn", reference_id=grn_id)
    )
    return WeighmentRecordListResponse(items=[_weighment_to_response(r) for r in records])


@weighment_router.post(
    "/routes/{route_id}/weighment",
    response_model=WeighmentRecordResponse,
    status_code=201,
    dependencies=[Depends(require_permission("weighment:record"))],
)
async def record_route_load_out_weighment(
    route_id: uuid.UUID,
    request: RecordWeighmentRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    use_case: Annotated[RecordWeighmentUseCase, Depends(get_record_weighment_use_case)],
) -> WeighmentRecordResponse:
    """MDG 2022 cl. 1.4(c)(d) — 100% of cylinders checked before load-out.
    Record this (`cylinders_checked` must equal `total_cylinders_in_batch`
    — enforced as a domain invariant) *before* calling
    `POST /routes/{route_id}/load`, which will 409 with
    `WEIGHMENT_CHECK_REQUIRED` if a passing check isn't on file yet for
    every cylinder type on the load manifest."""
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="An acting user is required.")
    try:
        record = await use_case.execute(
            RecordWeighmentCommand(
                tenant_id=principal.tenant_id,
                scale_id=request.scale_id,
                context="load_out_full_check",
                reference_type="route",
                reference_id=route_id,
                cylinder_type_id=request.cylinder_type_id,
                total_cylinders_in_batch=request.total_cylinders_in_batch,
                cylinders_checked=request.cylinders_checked,
                underweight_cylinder_count=request.underweight_cylinder_count,
                recorded_by=principal.user_id,
            )
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except DomainError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    return _weighment_to_response(record)


@weighment_router.get(
    "/routes/{route_id}/weighment",
    response_model=WeighmentRecordListResponse,
    dependencies=[Depends(require_permission("weighment:record"))],
)
async def list_route_weighments(
    route_id: uuid.UUID,
    repository: Annotated[WeighmentRecordRepository, Depends(get_weighment_record_repository)],
) -> WeighmentRecordListResponse:
    use_case = ListWeighmentRecordsUseCase(repository)
    records = await use_case.execute(
        ListWeighmentRecordsQuery(reference_type="route", reference_id=route_id)
    )
    return WeighmentRecordListResponse(items=[_weighment_to_response(r) for r in records])


@router.put(
    "/{scale_id}/status",
    response_model=ScaleResponse,
    dependencies=[Depends(require_permission("weighment:manage"))],
)
async def set_scale_status(
    scale_id: uuid.UUID,
    request: SetScaleStatusRequest,
    repository: Annotated[ScaleRepository, Depends(get_scale_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    file_storage: Annotated[FileStorage, Depends(get_file_storage)],
) -> ScaleResponse:
    use_case = SetScaleStatusUseCase(repository, unit_of_work)
    try:
        scale = await use_case.execute(
            SetScaleStatusCommand(scale_id=scale_id, status=request.status)
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except DomainError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    return await _to_response(scale, file_storage)


def _tdt_to_response(
    rating: TdtQuarterlyRating, *, quarter_start: date, quarter_end: date
) -> TdtQuarterlyRatingResponse:
    return TdtQuarterlyRatingResponse(
        overall_stars=rating.overall_stars,
        total_orders=rating.total_orders,
        distribution=[
            TdtBandDistributionResponse(stars=entry.stars, order_count=entry.order_count)
            for entry in rating.distribution
        ],
        quarter_start=quarter_start,
        quarter_end=quarter_end,
    )


@tdt_rating_router.get(
    "/quarterly",
    response_model=TdtQuarterlyRatingResponse,
    dependencies=[Depends(require_permission("tdt:read"))],
)
async def get_quarterly_tdt_rating(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    use_case: Annotated[GetQuarterlyTdtRatingUseCase, Depends(get_quarterly_tdt_rating_use_case)],
    quarter_start: date,
    quarter_end: date,
    branch_id: uuid.UUID | None = None,
) -> TdtQuarterlyRatingResponse:
    """`quarter_start` is inclusive, `quarter_end` is the **exclusive**
    upper bound — pass the first day of the quarter *after* the one you
    want (e.g. `2026-01-01`/`2026-04-01` for Q1 2026), not its last day."""
    rating = await use_case.execute(
        GetQuarterlyTdtRatingQuery(
            tenant_id=principal.tenant_id,
            quarter_start=quarter_start,
            quarter_end=quarter_end,
            branch_id=branch_id,
        )
    )
    return _tdt_to_response(rating, quarter_start=quarter_start, quarter_end=quarter_end)


@tdt_rating_router.get(
    "/live-projection",
    response_model=TdtQuarterlyRatingResponse,
    dependencies=[Depends(require_permission("tdt:read"))],
)
async def get_live_tdt_projection(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    use_case: Annotated[GetLiveTdtProjectionUseCase, Depends(get_live_tdt_projection_use_case)],
    branch_id: uuid.UUID | None = None,
) -> TdtQuarterlyRatingResponse:
    """The current, still-open calendar quarter's rating so far — "so the
    distributor can still act" (source plan), rather than only finding out
    once the quarter has already closed."""
    quarter_start, quarter_end = current_quarter_bounds(datetime.now(UTC).date())
    rating = await use_case.execute(
        GetLiveTdtProjectionQuery(tenant_id=principal.tenant_id, branch_id=branch_id)
    )
    return _tdt_to_response(rating, quarter_start=quarter_start, quarter_end=quarter_end)


def _cylinder_unit_to_response(unit: CylinderUnit) -> CylinderUnitResponse:
    return CylinderUnitResponse(
        id=unit.id,
        cylinder_type_id=unit.cylinder_type_id,
        serial_number=unit.serial_number,
        qr_code=unit.qr_code,
        manufacture_date=unit.manufacture_date,
        owner_omc=unit.owner_omc,
        condition_status=unit.condition_status,
        custody_type=unit.custody_type,
        custody_ref_id=unit.custody_ref_id,
        last_tested_at=unit.last_tested_at,
        test_due_date=unit.test_due_date,
        is_due_for_test=unit.is_due_for_test(as_of=datetime.now(UTC).date()),
        is_retired=unit.is_retired,
    )


@cylinder_units_router.post(
    "",
    response_model=CylinderUnitResponse,
    status_code=201,
    dependencies=[Depends(require_permission("cylinder_units:manage"))],
)
async def register_cylinder_unit(
    request: RegisterCylinderUnitRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    use_case: Annotated[RegisterCylinderUnitUseCase, Depends(get_register_cylinder_unit_use_case)],
) -> CylinderUnitResponse:
    """Cylinder Identity (Phase 20 subsystem 3) — registers one physical
    cylinder. A narrow, additive registry; does not touch bulk inventory
    balances."""
    try:
        unit = await use_case.execute(
            RegisterCylinderUnitCommand(
                tenant_id=principal.tenant_id,
                cylinder_type_id=request.cylinder_type_id,
                serial_number=request.serial_number,
                condition_status=request.condition_status,
                custody_type=request.custody_type,
                qr_code=request.qr_code,
                custody_ref_id=request.custody_ref_id,
                manufacture_date=request.manufacture_date,
                owner_omc=request.owner_omc,
            )
        )
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=exc.message) from exc
    except DomainError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    return _cylinder_unit_to_response(unit)


@cylinder_units_router.get(
    "",
    response_model=CylinderUnitListResponse,
    dependencies=[Depends(require_permission("cylinder_units:read"))],
)
async def list_cylinder_units(
    repository: Annotated[CylinderUnitRepository, Depends(get_cylinder_unit_repository)],
    due_status: str | None = None,
    cylinder_type_id: uuid.UUID | None = None,
    custody_type: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> CylinderUnitListResponse:
    """`due_status` is `due_soon` (<=30 days) or `overdue` — same idiom as
    the Scale registry's own `expiry` filter."""
    use_case = ListCylinderUnitsUseCase(repository)
    units, total = await use_case.execute(
        ListCylinderUnitsQuery(
            due_status=due_status,
            cylinder_type_id=cylinder_type_id,
            custody_type=custody_type,
            skip=skip,
            limit=limit,
        )
    )
    return CylinderUnitListResponse(
        items=[_cylinder_unit_to_response(u) for u in units], total=total
    )


@cylinder_units_router.get(
    "/suggest-test-due-date",
    response_model=SuggestCylinderTestDueDateResponse,
    dependencies=[Depends(require_permission("cylinder_units:read"))],
)
async def suggest_cylinder_test_due_date(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    use_case: Annotated[
        SuggestStatutoryTestDueDateUseCase, Depends(get_suggest_statutory_test_due_date_use_case)
    ],
    tested_at: date,
) -> SuggestCylinderTestDueDateResponse:
    """A read-only convenience helper for a "record test" form — `null`
    when the tenant has no `cylinder_statutory_test_interval_months`
    configured. Registered before `/{cylinder_unit_id}` so this literal
    path is matched first."""
    suggestion = await use_case.execute(
        SuggestStatutoryTestDueDateQuery(tenant_id=principal.tenant_id, tested_at=tested_at)
    )
    return SuggestCylinderTestDueDateResponse(suggested_due_date=suggestion)


@cylinder_units_router.get(
    "/lookup",
    response_model=CylinderUnitResponse,
    dependencies=[Depends(require_permission("cylinder_units:read"))],
)
async def lookup_cylinder_unit(
    code: str,
    use_case: Annotated[LookupCylinderUnitUseCase, Depends(get_lookup_cylinder_unit_use_case)],
) -> CylinderUnitResponse:
    """Quick lookup for cylinder tracking — resolves unit by QR code or serial number."""
    unit = await use_case.execute(LookupCylinderUnitQuery(code=code))
    if unit is None:
        raise HTTPException(status_code=404, detail=f"Cylinder unit with code '{code}' not found.")
    return _cylinder_unit_to_response(unit)


@cylinder_units_router.post(
    "/batch-custody",
    response_model=BatchMoveCylinderCustodyResponse,
    dependencies=[Depends(require_permission("cylinder_units:manage"))],
)
async def batch_move_cylinder_custody(
    request: BatchMoveCylinderCustodyRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    use_case: Annotated[
        BatchMoveCylinderCustodyUseCase, Depends(get_batch_move_cylinder_custody_use_case)
    ],
) -> BatchMoveCylinderCustodyResponse:
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="An acting user is required.")
    try:
        moved = await use_case.execute(
            BatchMoveCylinderCustodyCommand(
                cylinder_unit_ids=request.cylinder_unit_ids,
                custody_type=request.custody_type,
                custody_ref_id=request.custody_ref_id,
                performed_by=principal.user_id,
            )
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except DomainError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    return BatchMoveCylinderCustodyResponse(
        updated_count=len(moved),
        items=[_cylinder_unit_to_response(u) for u in moved],
    )


@cylinder_units_router.get(
    "/{cylinder_unit_id}",
    response_model=CylinderUnitResponse,
    dependencies=[Depends(require_permission("cylinder_units:read"))],
)
async def get_cylinder_unit(
    cylinder_unit_id: uuid.UUID,
    repository: Annotated[CylinderUnitRepository, Depends(get_cylinder_unit_repository)],
) -> CylinderUnitResponse:
    use_case = GetCylinderUnitUseCase(repository)
    unit = await use_case.execute(GetCylinderUnitQuery(cylinder_unit_id=cylinder_unit_id))
    if unit is None:
        raise HTTPException(status_code=404, detail=f"Cylinder unit {cylinder_unit_id} not found.")
    return _cylinder_unit_to_response(unit)


@cylinder_units_router.post(
    "/{cylinder_unit_id}/test",
    response_model=CylinderUnitResponse,
    dependencies=[Depends(require_permission("cylinder_units:manage"))],
)
async def record_cylinder_statutory_test(
    cylinder_unit_id: uuid.UUID,
    request: RecordCylinderStatutoryTestRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    use_case: Annotated[RecordStatutoryTestUseCase, Depends(get_record_statutory_test_use_case)],
) -> CylinderUnitResponse:
    """`due_date` is the caller's own value — never computed server-side
    from an assumed interval (see `GET .../suggest-test-due-date` for the
    optional, explicitly-opt-in suggestion)."""
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="An acting user is required.")
    try:
        unit = await use_case.execute(
            RecordStatutoryTestCommand(
                cylinder_unit_id=cylinder_unit_id,
                tested_at=request.tested_at,
                due_date=request.due_date,
                performed_by=principal.user_id,
            )
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except DomainError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    return _cylinder_unit_to_response(unit)


@cylinder_units_router.post(
    "/{cylinder_unit_id}/custody",
    response_model=CylinderUnitResponse,
    dependencies=[Depends(require_permission("cylinder_units:manage"))],
)
async def move_cylinder_custody(
    cylinder_unit_id: uuid.UUID,
    request: MoveCylinderCustodyRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    use_case: Annotated[MoveCylinderCustodyUseCase, Depends(get_move_cylinder_custody_use_case)],
) -> CylinderUnitResponse:
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="An acting user is required.")
    try:
        unit = await use_case.execute(
            MoveCylinderCustodyCommand(
                cylinder_unit_id=cylinder_unit_id,
                custody_type=request.custody_type,
                custody_ref_id=request.custody_ref_id,
                performed_by=principal.user_id,
            )
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except DomainError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    return _cylinder_unit_to_response(unit)


@cylinder_units_router.post(
    "/{cylinder_unit_id}/condition",
    response_model=CylinderUnitResponse,
    dependencies=[Depends(require_permission("cylinder_units:manage"))],
)
async def change_cylinder_condition_status(
    cylinder_unit_id: uuid.UUID,
    request: ChangeCylinderConditionStatusRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    use_case: Annotated[
        ChangeCylinderConditionStatusUseCase,
        Depends(get_change_cylinder_condition_status_use_case),
    ],
) -> CylinderUnitResponse:
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="An acting user is required.")
    try:
        unit = await use_case.execute(
            ChangeCylinderConditionStatusCommand(
                cylinder_unit_id=cylinder_unit_id,
                new_status=request.new_status,
                performed_by=principal.user_id,
                reason=request.reason,
            )
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except DomainError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    return _cylinder_unit_to_response(unit)


@cylinder_units_router.post(
    "/{cylinder_unit_id}/receive",
    response_model=CylinderUnitResponse,
    dependencies=[Depends(require_permission("cylinder_units:manage"))],
)
async def receive_cylinder_unit(
    cylinder_unit_id: uuid.UUID,
    request: ReceiveCylinderUnitRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    use_case: Annotated[ReceiveCylinderUnitUseCase, Depends(get_receive_cylinder_unit_use_case)],
) -> CylinderUnitResponse:
    """Rule 26, Gas Cylinders Rules 2016 — 409 `CYLINDER_DUE_FOR_STATUTORY_
    TEST` if this unit's retest is due; segregate and return it to the
    bottling plant instead (MDG 2022 cl. 1.4(b))."""
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="An acting user is required.")
    try:
        unit = await use_case.execute(
            ReceiveCylinderUnitCommand(
                cylinder_unit_id=cylinder_unit_id,
                warehouse_id=request.warehouse_id,
                performed_by=principal.user_id,
            )
        )
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=exc.message) from exc
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except DomainError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    return _cylinder_unit_to_response(unit)


@cylinder_units_router.post(
    "/{cylinder_unit_id}/retire",
    response_model=CylinderUnitResponse,
    dependencies=[Depends(require_permission("cylinder_units:manage"))],
)
async def retire_cylinder_unit(
    cylinder_unit_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    use_case: Annotated[RetireCylinderUnitUseCase, Depends(get_retire_cylinder_unit_use_case)],
) -> CylinderUnitResponse:
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="An acting user is required.")
    try:
        unit = await use_case.execute(
            RetireCylinderUnitCommand(
                cylinder_unit_id=cylinder_unit_id, performed_by=principal.user_id
            )
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except DomainError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    return _cylinder_unit_to_response(unit)


@cylinder_units_router.post(
    "/{cylinder_unit_id}/label",
    dependencies=[Depends(require_permission("cylinder_units:read"))],
)
async def print_cylinder_unit_label(
    cylinder_unit_id: uuid.UUID,
    repository: Annotated[CylinderUnitRepository, Depends(get_cylinder_unit_repository)],
    cylinder_type_repo: Annotated[CylinderTypeRepository, Depends(get_cylinder_type_repository)],
    printing_engine: Annotated[PrintingEngine, Depends(get_printing_engine)],
) -> Response:
    """Render and download thermal sticker PDF with 2D QR code for this cylinder."""
    unit = await repository.get_by_id(cylinder_unit_id)
    if unit is None:
        raise HTTPException(status_code=404, detail=f"Cylinder unit {cylinder_unit_id} not found.")

    cylinder_type = await cylinder_type_repo.get(unit.cylinder_type_id)
    type_name: str | None = None
    if cylinder_type:
        if "kg" in cylinder_type.name.lower():
            type_name = cylinder_type.name
        else:
            type_name = f"{cylinder_type.name} ({cylinder_type.weight_kg} kg)"

    pdf_bytes = printing_engine.render_cylinder_label_pdf(unit, cylinder_type_name=type_name)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="cylinder-label-{unit.serial_number}.pdf"',
        },
    )
