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

from lpg.api.v1.dependencies.delivery import get_driver_repository, get_vehicle_repository
from lpg.api.v1.dependencies.identity import get_current_principal, require_permission
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.api.v1.schemas.delivery import (
    DriverPageResponse,
    DriverResponse,
    RegisterDriverRequest,
    RegisterVehicleRequest,
    UpdateDriverLicenseRequest,
    UpdateDriverStatusRequest,
    UpdateVehicleStatusRequest,
    VehiclePageResponse,
    VehicleResponse,
)
from lpg.application.common.errors import NotFoundError
from lpg.application.common.ports import UnitOfWork
from lpg.application.delivery.ports import DriverRepository, VehicleRepository
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
    UpdateDriverLicenseCommand,
    UpdateDriverLicenseUseCase,
    UpdateDriverStatusCommand,
    UpdateDriverStatusUseCase,
    UpdateVehicleStatusCommand,
    UpdateVehicleStatusUseCase,
)
from lpg.application.identity.ports import AuthenticatedPrincipal
from lpg.domain.common.base import DomainError

router = APIRouter(tags=["delivery"])


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
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> DriverResponse:
    """Register a new driver profile."""
    use_case = RegisterDriverUseCase(repository, unit_of_work)
    try:
        driver = await use_case.execute(
            RegisterDriverCommand(
                tenant_id=principal.tenant_id,
                branch_id=request.branch_id,
                employee_id=request.employee_id,
                license_number=request.license_number,
                license_expiry_date=request.license_expiry_date,
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
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> VehicleResponse:
    """Register a new vehicle."""
    use_case = RegisterVehicleUseCase(repository, unit_of_work)
    try:
        vehicle = await use_case.execute(
            RegisterVehicleCommand(
                tenant_id=principal.tenant_id,
                branch_id=request.branch_id,
                registration_number=request.registration_number,
                make=request.make,
                model=request.model,
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
