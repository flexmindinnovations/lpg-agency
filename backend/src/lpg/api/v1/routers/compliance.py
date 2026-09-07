"""API router for the `compliance` bounded context — Weighment Part 1 (scale
registry). `planning/features/20-regulatory-compliance` subsystem 1."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException

from lpg.api.v1.dependencies.compliance import get_scale_repository
from lpg.api.v1.dependencies.identity import get_current_principal, require_permission
from lpg.api.v1.dependencies.order import get_file_storage
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.api.v1.schemas.compliance import (
    RegisterScaleRequest,
    ReplaceScaleCertificateRequest,
    ScaleListResponse,
    ScaleResponse,
    SetScaleStatusRequest,
)
from lpg.application.common.errors import ConflictError, NotFoundError
from lpg.application.common.ports import FileStorage, UnitOfWork
from lpg.application.compliance.ports import ScaleRepository
from lpg.application.compliance.use_cases import (
    ListScalesQuery,
    ListScalesUseCase,
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

router = APIRouter(prefix="/scales", tags=["Compliance — Weighment"])


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
