"""API router for the `compliance` bounded context — Weighment Part 1 (scale
registry, `planning/features/20-regulatory-compliance` subsystem 1) and TDT
rating (subsystem 2)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException

from lpg.api.v1.dependencies.compliance import (
    get_live_tdt_projection_use_case,
    get_quarterly_tdt_rating_use_case,
    get_record_weighment_use_case,
    get_scale_repository,
    get_weighment_record_repository,
)
from lpg.api.v1.dependencies.identity import get_current_principal, require_permission
from lpg.api.v1.dependencies.order import get_file_storage
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.api.v1.schemas.compliance import (
    RecordWeighmentRequest,
    RegisterScaleRequest,
    ReplaceScaleCertificateRequest,
    ScaleListResponse,
    ScaleResponse,
    SetScaleStatusRequest,
    TdtBandDistributionResponse,
    TdtQuarterlyRatingResponse,
    WeighmentRecordListResponse,
    WeighmentRecordResponse,
)
from lpg.application.common.errors import ConflictError, NotFoundError
from lpg.application.common.ports import FileStorage, UnitOfWork
from lpg.application.compliance.ports import ScaleRepository, WeighmentRecordRepository
from lpg.application.compliance.queries.get_tdt_rating import (
    GetLiveTdtProjectionQuery,
    GetLiveTdtProjectionUseCase,
    GetQuarterlyTdtRatingQuery,
    GetQuarterlyTdtRatingUseCase,
    current_quarter_bounds,
)
from lpg.application.compliance.use_cases import (
    ListScalesQuery,
    ListScalesUseCase,
    ListWeighmentRecordsQuery,
    ListWeighmentRecordsUseCase,
    RecordWeighmentCommand,
    RecordWeighmentUseCase,
    RegisterScaleCommand,
    RegisterScaleUseCase,
    ReplaceScaleCertificateCommand,
    ReplaceScaleCertificateUseCase,
    SetScaleStatusCommand,
    SetScaleStatusUseCase,
)
from lpg.application.identity.ports import AuthenticatedPrincipal
from lpg.domain.common.base import DomainError

if TYPE_CHECKING:
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
