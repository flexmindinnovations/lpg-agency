"""FastAPI router for the delivery bounded context.

Exposes Driver and Vehicle management endpoints under `/drivers` and
`/vehicles`. All endpoints require authentication (JWT) and are gated by
the narrowly-scoped permissions defined in
`docs/data/17-api-security.md` §6:

  drivers:read   — list / get drivers
  drivers:manage — register / update drivers
  vehicles:read  — list / get vehicles
  vehicles:manage — register / update vehicles
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from lpg.api.v1.dependencies.admin import get_employee_repository
from lpg.api.v1.dependencies.delivery import (
    get_compliance_document_repository,
    get_driver_repository,
    get_route_repository,
    get_vehicle_repository,
)
from lpg.api.v1.dependencies.identity import get_current_principal, require_permission
from lpg.api.v1.dependencies.order import get_file_storage
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.api.v1.schemas.delivery import (
    DriverMeResponse,
    DriverMeVehicle,
    DriverPageResponse,
    DriverResponse,
    RegisterDriverRequest,
    RegisterVehicleRequest,
    UpdateDriverAssignmentRequest,
    UpdateDriverLicenseRequest,
    UpdateDriverStatusRequest,
    UpdateVehicleDetailsRequest,
    UpdateVehicleStatusRequest,
    VehiclePageResponse,
    VehicleResponse,
)
from lpg.api.v1.schemas.document import (
    AddComplianceDocumentRequest,
    ComplianceDocumentListResponse,
    ComplianceDocumentResponse,
    ComplianceOwnerType,
    ReplaceComplianceDocumentRequest,
    VerifyComplianceDocumentRequest,
)
from lpg.application.common.errors import ConflictError, NotFoundError
from lpg.application.common.ports import FileStorage, UnitOfWork
from lpg.application.delivery.compliance_use_cases import (
    AddComplianceDocumentCommand,
    AddComplianceDocumentUseCase,
    ListComplianceDocumentsForOwnerQuery,
    ListComplianceDocumentsForOwnerUseCase,
    ListComplianceDocumentsQuery,
    ListComplianceDocumentsUseCase,
    ReplaceComplianceDocumentCommand,
    ReplaceComplianceDocumentUseCase,
    VerifyComplianceDocumentCommand,
    VerifyComplianceDocumentUseCase,
)
from lpg.application.delivery.ports import (
    ComplianceDocumentRepository,
    DriverRepository,
    RouteRepository,
    VehicleRepository,
)
from lpg.application.delivery.use_cases import (
    GetDriverQuery,
    GetDriverUseCase,
    GetVehicleQuery,
    GetVehicleUseCase,
    ListDriversQuery,
    ListDriversUseCase,
    ListVehiclesQuery,
    ListVehiclesUseCase,
    RegisterDriverCommand,
    RegisterDriverUseCase,
    RegisterVehicleCommand,
    RegisterVehicleUseCase,
    UpdateDriverAssignmentCommand,
    UpdateDriverAssignmentUseCase,
    UpdateDriverLicenseCommand,
    UpdateDriverLicenseUseCase,
    UpdateDriverStatusCommand,
    UpdateDriverStatusUseCase,
    UpdateVehicleDetailsCommand,
    UpdateVehicleDetailsUseCase,
    UpdateVehicleStatusCommand,
    UpdateVehicleStatusUseCase,
)
from lpg.application.identity.ports import AuthenticatedPrincipal
from lpg.application.tenant_admin.ports import EmployeeRepository
from lpg.domain.common.base import DomainError

router = APIRouter(tags=["Delivery"])


def _driver_to_response(driver: object) -> DriverResponse:
    """Map Driver domain object to DriverResponse schema."""
    from lpg.domain.delivery.driver import Driver

    assert isinstance(driver, Driver)
    return DriverResponse(
        id=driver.id,
        tenant_id=driver.tenant_id,
        branch_id=driver.branch_id,
        identity_user_id=driver.identity_user_id,
        employee_id=driver.employee_id,
        license_number=driver.license_number,
        license_expiry_date=driver.license_expiry_date,
        status=driver.status,
        version=driver.version,
    )


def _vehicle_to_response(vehicle: object) -> VehicleResponse:
    """Map Vehicle domain object to VehicleResponse schema."""
    from lpg.domain.delivery.vehicle import Vehicle

    assert isinstance(vehicle, Vehicle)
    return VehicleResponse(
        id=vehicle.id,
        tenant_id=vehicle.tenant_id,
        branch_id=vehicle.branch_id,
        registration_number=vehicle.registration_number,
        make=vehicle.make,
        model=vehicle.model,
        ownership_type=vehicle.ownership_type,
        capacity_units=vehicle.capacity_units,
        status=vehicle.status,
        version=vehicle.version,
    )


# ==========================================================================
# Driver endpoints
# ==========================================================================


@router.get(
    "/drivers/me",
    response_model=DriverMeResponse,
    summary="The calling driver's own profile",
    dependencies=[Depends(require_permission("drivers:read"))],
)
async def get_my_driver_profile(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    driver_repository: Annotated[DriverRepository, Depends(get_driver_repository)],
    employee_repository: Annotated[EmployeeRepository, Depends(get_employee_repository)],
    route_repository: Annotated[RouteRepository, Depends(get_route_repository)],
    vehicle_repository: Annotated[VehicleRepository, Depends(get_vehicle_repository)],
) -> DriverMeResponse:
    """The Driver App's Profile tab. Resolves the driver from the token (the
    same "no `driver_id` needed client-side" pattern as `GET /routes/active`):
    name/phone come from the linked employee, the current vehicle from the
    driver's active route (`null` when they have none). `404` if the caller
    isn't a driver. Declared before `GET /drivers/{driver_id}` so `me` isn't
    parsed as a UUID.
    """
    actor_id = principal.user_id
    driver = (
        await driver_repository.get_by_identity_user_id(actor_id) if actor_id is not None else None
    )
    if driver is None:
        raise HTTPException(status_code=404, detail="No driver profile for this account.")

    employee = await employee_repository.get_by_id(driver.employee_id)

    vehicle_info: DriverMeVehicle | None = None
    active_route = await route_repository.get_active_route_for_driver(driver.id)
    if active_route is not None:
        vehicle = await vehicle_repository.get_by_id(active_route.vehicle_id)
        if vehicle is not None:
            vehicle_info = DriverMeVehicle(
                registration_number=vehicle.registration_number,
                make=vehicle.make,
                model=vehicle.model,
            )

    return DriverMeResponse(
        driver_id=driver.id,
        name=(
            f"{employee.first_name} {employee.last_name}".strip()
            if employee is not None
            else "Driver"
        ),
        phone_number=employee.phone_number if employee is not None else "",
        license_number=driver.license_number,
        license_expiry_date=driver.license_expiry_date,
        status=driver.status,
        vehicle=vehicle_info,
    )


@router.post(
    "/drivers",
    response_model=DriverResponse,
    status_code=201,
    dependencies=[Depends(require_permission("drivers:manage"))],
)
async def register_driver(
    request: RegisterDriverRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[DriverRepository, Depends(get_driver_repository)],
    compliance_repository: Annotated[
        ComplianceDocumentRepository, Depends(get_compliance_document_repository)
    ],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> DriverResponse:
    """Register a new driver profile. A driving-licence scan is required — the
    driver and its `driving_licence` compliance document are created together."""
    use_case = RegisterDriverUseCase(repository, compliance_repository, unit_of_work)
    try:
        driver = await use_case.execute(
            RegisterDriverCommand(
                tenant_id=principal.tenant_id,
                branch_id=request.branch_id,
                employee_id=request.employee_id,
                license_number=request.license_number,
                license_expiry_date=request.license_expiry_date,
                licence_document_ref=request.licence_document_ref,
                licence_issue_date=request.licence_issue_date,
                identity_user_id=request.identity_user_id,
            )
        )
    except DomainError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    return _driver_to_response(driver)


@router.get(
    "/drivers",
    response_model=DriverPageResponse,
    dependencies=[Depends(require_permission("drivers:read"))],
)
async def list_drivers(
    repository: Annotated[DriverRepository, Depends(get_driver_repository)],
    skip: int = 0,
    limit: int = 50,
    search: str | None = None,
    status: str | None = None,
    branch_id: uuid.UUID | None = None,
) -> DriverPageResponse:
    """List drivers with optional search and filter."""
    use_case = ListDriversUseCase(repository)
    drivers, total = await use_case.execute(
        ListDriversQuery(
            skip=skip,
            limit=limit,
            search=search,
            status=status,
            branch_id=branch_id,
        )
    )
    page = (skip // limit) + 1 if limit else 1
    return DriverPageResponse(
        items=[_driver_to_response(d) for d in drivers],
        total=total,
        page=page,
        page_size=limit,
    )


@router.get(
    "/drivers/{driver_id}",
    response_model=DriverResponse,
    dependencies=[Depends(require_permission("drivers:read"))],
)
async def get_driver(
    driver_id: uuid.UUID,
    repository: Annotated[DriverRepository, Depends(get_driver_repository)],
) -> DriverResponse:
    """Retrieve a single driver by ID."""
    use_case = GetDriverUseCase(repository)
    try:
        driver = await use_case.execute(GetDriverQuery(driver_id=driver_id))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    return _driver_to_response(driver)


@router.patch(
    "/drivers/{driver_id}/status",
    response_model=DriverResponse,
    dependencies=[Depends(require_permission("drivers:manage"))],
)
async def update_driver_status(
    driver_id: uuid.UUID,
    request: UpdateDriverStatusRequest,
    repository: Annotated[DriverRepository, Depends(get_driver_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> DriverResponse:
    """Transition a driver to a new status."""
    use_case = UpdateDriverStatusUseCase(repository, unit_of_work)
    try:
        driver = await use_case.execute(
            UpdateDriverStatusCommand(
                driver_id=driver_id,
                new_status=request.status,
            )
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except DomainError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    return _driver_to_response(driver)


@router.patch(
    "/drivers/{driver_id}/license",
    response_model=DriverResponse,
    dependencies=[Depends(require_permission("drivers:manage"))],
)
async def update_driver_license(
    driver_id: uuid.UUID,
    request: UpdateDriverLicenseRequest,
    repository: Annotated[DriverRepository, Depends(get_driver_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> DriverResponse:
    """Update a driver's license information."""
    use_case = UpdateDriverLicenseUseCase(repository, unit_of_work)
    try:
        driver = await use_case.execute(
            UpdateDriverLicenseCommand(
                driver_id=driver_id,
                license_number=request.license_number,
                license_expiry_date=request.license_expiry_date,
            )
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except DomainError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    return _driver_to_response(driver)


@router.patch(
    "/drivers/{driver_id}/assignment",
    response_model=DriverResponse,
    dependencies=[Depends(require_permission("drivers:manage"))],
)
async def update_driver_assignment(
    driver_id: uuid.UUID,
    request: UpdateDriverAssignmentRequest,
    repository: Annotated[DriverRepository, Depends(get_driver_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> DriverResponse:
    """Relink a driver profile to a (possibly different) employee/branch."""
    use_case = UpdateDriverAssignmentUseCase(repository, unit_of_work)
    try:
        driver = await use_case.execute(
            UpdateDriverAssignmentCommand(
                driver_id=driver_id,
                employee_id=request.employee_id,
                branch_id=request.branch_id,
            )
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except DomainError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    return _driver_to_response(driver)


# ==========================================================================
# Vehicle endpoints
# ==========================================================================


@router.post(
    "/vehicles",
    response_model=VehicleResponse,
    status_code=201,
    dependencies=[Depends(require_permission("vehicles:manage"))],
)
async def register_vehicle(
    request: RegisterVehicleRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[VehicleRepository, Depends(get_vehicle_repository)],
    compliance_repository: Annotated[
        ComplianceDocumentRepository, Depends(get_compliance_document_repository)
    ],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> VehicleResponse:
    """Register a new vehicle. An RC scan is required — the vehicle and its
    `vehicle_rc` compliance document are created together."""
    use_case = RegisterVehicleUseCase(repository, compliance_repository, unit_of_work)
    try:
        vehicle = await use_case.execute(
            RegisterVehicleCommand(
                tenant_id=principal.tenant_id,
                branch_id=request.branch_id,
                registration_number=request.registration_number,
                make=request.make,
                model=request.model,
                rc_document_ref=request.rc_document_ref,
                rc_expiry_date=request.rc_expiry_date,
                rc_issue_date=request.rc_issue_date,
                ownership_type=request.ownership_type,
                capacity_units=request.capacity_units,
            )
        )
    except DomainError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    return _vehicle_to_response(vehicle)


@router.get(
    "/vehicles",
    response_model=VehiclePageResponse,
    dependencies=[Depends(require_permission("vehicles:read"))],
)
async def list_vehicles(
    repository: Annotated[VehicleRepository, Depends(get_vehicle_repository)],
    skip: int = 0,
    limit: int = 50,
    search: str | None = None,
    status: str | None = None,
    branch_id: uuid.UUID | None = None,
) -> VehiclePageResponse:
    """List vehicles with optional search and filter."""
    use_case = ListVehiclesUseCase(repository)
    vehicles, total = await use_case.execute(
        ListVehiclesQuery(
            skip=skip,
            limit=limit,
            search=search,
            status=status,
            branch_id=branch_id,
        )
    )
    page = (skip // limit) + 1 if limit else 1
    return VehiclePageResponse(
        items=[_vehicle_to_response(v) for v in vehicles],
        total=total,
        page=page,
        page_size=limit,
    )


@router.get(
    "/vehicles/{vehicle_id}",
    response_model=VehicleResponse,
    dependencies=[Depends(require_permission("vehicles:read"))],
)
async def get_vehicle(
    vehicle_id: uuid.UUID,
    repository: Annotated[VehicleRepository, Depends(get_vehicle_repository)],
) -> VehicleResponse:
    """Retrieve a single vehicle by ID."""
    use_case = GetVehicleUseCase(repository)
    try:
        vehicle = await use_case.execute(GetVehicleQuery(vehicle_id=vehicle_id))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    return _vehicle_to_response(vehicle)


@router.patch(
    "/vehicles/{vehicle_id}/status",
    response_model=VehicleResponse,
    dependencies=[Depends(require_permission("vehicles:manage"))],
)
async def update_vehicle_status(
    vehicle_id: uuid.UUID,
    request: UpdateVehicleStatusRequest,
    repository: Annotated[VehicleRepository, Depends(get_vehicle_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> VehicleResponse:
    """Transition a vehicle to a new status."""
    use_case = UpdateVehicleStatusUseCase(repository, unit_of_work)
    try:
        vehicle = await use_case.execute(
            UpdateVehicleStatusCommand(
                vehicle_id=vehicle_id,
                new_status=request.status,
            )
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except DomainError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    return _vehicle_to_response(vehicle)


@router.patch(
    "/vehicles/{vehicle_id}/details",
    response_model=VehicleResponse,
    dependencies=[Depends(require_permission("vehicles:manage"))],
)
async def update_vehicle_details(
    vehicle_id: uuid.UUID,
    request: UpdateVehicleDetailsRequest,
    repository: Annotated[VehicleRepository, Depends(get_vehicle_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> VehicleResponse:
    """Update a vehicle's make/model/ownership/capacity."""
    use_case = UpdateVehicleDetailsUseCase(repository, unit_of_work)
    try:
        vehicle = await use_case.execute(
            UpdateVehicleDetailsCommand(
                vehicle_id=vehicle_id,
                make=request.make,
                model=request.model,
                ownership_type=request.ownership_type,
                capacity_units=request.capacity_units,
            )
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except DomainError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    return _vehicle_to_response(vehicle)


# ==========================================================================
# Compliance document endpoints  (driver/vehicle statutory documents)
# ==========================================================================


async def _compliance_doc_to_response(
    doc: object, file_storage: FileStorage
) -> ComplianceDocumentResponse:
    from lpg.domain.delivery.compliance_document import ComplianceDocument

    assert isinstance(doc, ComplianceDocument)
    file_url = await file_storage.url(doc.file_ref) if doc.file_ref else None
    return ComplianceDocumentResponse(
        id=doc.id,
        owner_type=doc.owner_type,
        owner_id=doc.owner_id,
        doc_type=doc.doc_type,
        document_number=doc.document_number,
        file_url=file_url,
        issue_date=doc.issue_date,
        expiry_date=doc.expiry_date,
        verification_status=doc.verification_status,
        rejection_reason=doc.rejection_reason,
        verified_at=doc.verified_at,
    )


async def _list_owner_documents(
    owner_type: ComplianceOwnerType,
    owner_id: uuid.UUID,
    repository: ComplianceDocumentRepository,
    file_storage: FileStorage,
) -> ComplianceDocumentListResponse:
    use_case = ListComplianceDocumentsForOwnerUseCase(repository)
    docs = await use_case.execute(
        ListComplianceDocumentsForOwnerQuery(owner_type=owner_type, owner_id=owner_id)
    )
    items = [await _compliance_doc_to_response(d, file_storage) for d in docs]
    return ComplianceDocumentListResponse(items=items, total=len(items))


async def _add_owner_document(
    owner_type: ComplianceOwnerType,
    owner_id: uuid.UUID,
    request: AddComplianceDocumentRequest,
    principal: AuthenticatedPrincipal,
    repository: ComplianceDocumentRepository,
    unit_of_work: UnitOfWork,
    file_storage: FileStorage,
) -> ComplianceDocumentResponse:
    use_case = AddComplianceDocumentUseCase(repository, unit_of_work)
    try:
        doc = await use_case.execute(
            AddComplianceDocumentCommand(
                tenant_id=principal.tenant_id,
                owner_type=owner_type,
                owner_id=owner_id,
                doc_type=request.doc_type,
                document_number=request.document_number,
                file_ref=request.file_ref,
                issue_date=request.issue_date,
                expiry_date=request.expiry_date,
            )
        )
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=exc.message) from exc
    except DomainError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    return await _compliance_doc_to_response(doc, file_storage)


@router.get(
    "/drivers/{driver_id}/documents",
    response_model=ComplianceDocumentListResponse,
    dependencies=[Depends(require_permission("drivers:read"))],
)
async def list_driver_documents(
    driver_id: uuid.UUID,
    repository: Annotated[
        ComplianceDocumentRepository, Depends(get_compliance_document_repository)
    ],
    file_storage: Annotated[FileStorage, Depends(get_file_storage)],
) -> ComplianceDocumentListResponse:
    return await _list_owner_documents("driver", driver_id, repository, file_storage)


@router.post(
    "/drivers/{driver_id}/documents",
    response_model=ComplianceDocumentResponse,
    status_code=201,
    dependencies=[Depends(require_permission("drivers:manage"))],
)
async def add_driver_document(
    driver_id: uuid.UUID,
    request: AddComplianceDocumentRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[
        ComplianceDocumentRepository, Depends(get_compliance_document_repository)
    ],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    file_storage: Annotated[FileStorage, Depends(get_file_storage)],
) -> ComplianceDocumentResponse:
    return await _add_owner_document(
        "driver", driver_id, request, principal, repository, unit_of_work, file_storage
    )


@router.get(
    "/vehicles/{vehicle_id}/documents",
    response_model=ComplianceDocumentListResponse,
    dependencies=[Depends(require_permission("vehicles:read"))],
)
async def list_vehicle_documents(
    vehicle_id: uuid.UUID,
    repository: Annotated[
        ComplianceDocumentRepository, Depends(get_compliance_document_repository)
    ],
    file_storage: Annotated[FileStorage, Depends(get_file_storage)],
) -> ComplianceDocumentListResponse:
    return await _list_owner_documents("vehicle", vehicle_id, repository, file_storage)


@router.post(
    "/vehicles/{vehicle_id}/documents",
    response_model=ComplianceDocumentResponse,
    status_code=201,
    dependencies=[Depends(require_permission("vehicles:manage"))],
)
async def add_vehicle_document(
    vehicle_id: uuid.UUID,
    request: AddComplianceDocumentRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[
        ComplianceDocumentRepository, Depends(get_compliance_document_repository)
    ],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    file_storage: Annotated[FileStorage, Depends(get_file_storage)],
) -> ComplianceDocumentResponse:
    return await _add_owner_document(
        "vehicle", vehicle_id, request, principal, repository, unit_of_work, file_storage
    )


@router.put(
    "/compliance-documents/{document_id}",
    response_model=ComplianceDocumentResponse,
    dependencies=[Depends(require_permission("drivers:manage"))],
)
async def replace_compliance_document(
    document_id: uuid.UUID,
    request: ReplaceComplianceDocumentRequest,
    repository: Annotated[
        ComplianceDocumentRepository, Depends(get_compliance_document_repository)
    ],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    file_storage: Annotated[FileStorage, Depends(get_file_storage)],
) -> ComplianceDocumentResponse:
    """Supersede a document with a renewed one (same slot, verification resets
    to pending). Gated by `drivers:manage` — the same roles hold
    `vehicles:manage`."""
    use_case = ReplaceComplianceDocumentUseCase(repository, unit_of_work)
    try:
        doc = await use_case.execute(
            ReplaceComplianceDocumentCommand(
                document_id=document_id,
                document_number=request.document_number,
                file_ref=request.file_ref,
                issue_date=request.issue_date,
                expiry_date=request.expiry_date,
            )
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except DomainError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    return await _compliance_doc_to_response(doc, file_storage)


@router.post(
    "/compliance-documents/{document_id}/verify",
    response_model=ComplianceDocumentResponse,
    dependencies=[Depends(require_permission("compliance:verify"))],
)
async def verify_compliance_document(
    document_id: uuid.UUID,
    request: VerifyComplianceDocumentRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[
        ComplianceDocumentRepository, Depends(get_compliance_document_repository)
    ],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    file_storage: Annotated[FileStorage, Depends(get_file_storage)],
) -> ComplianceDocumentResponse:
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="An acting user is required.")
    use_case = VerifyComplianceDocumentUseCase(repository, unit_of_work)
    try:
        doc = await use_case.execute(
            VerifyComplianceDocumentCommand(
                document_id=document_id,
                verified_by=principal.user_id,
                status=request.status,
                rejection_reason=request.rejection_reason,
            )
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except DomainError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    return await _compliance_doc_to_response(doc, file_storage)


@router.get(
    "/compliance-documents",
    response_model=ComplianceDocumentListResponse,
    dependencies=[Depends(require_permission("drivers:read"))],
)
async def list_compliance_documents(
    repository: Annotated[
        ComplianceDocumentRepository, Depends(get_compliance_document_repository)
    ],
    file_storage: Annotated[FileStorage, Depends(get_file_storage)],
    owner_type: ComplianceOwnerType | None = None,
    status: str | None = None,
    expiry: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> ComplianceDocumentListResponse:
    """Tenant-wide compliance-document list for the drivers/vehicles pages —
    `expiry` is `expiring` (<=30 days) or `expired`."""
    use_case = ListComplianceDocumentsUseCase(repository)
    docs, total = await use_case.execute(
        ListComplianceDocumentsQuery(
            owner_type=owner_type,
            status=status,
            expiry=expiry,
            skip=skip,
            limit=limit,
        )
    )
    items = [await _compliance_doc_to_response(d, file_storage) for d in docs]
    return ComplianceDocumentListResponse(items=items, total=total)
