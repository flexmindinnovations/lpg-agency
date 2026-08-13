"""Unit tests for Driver and Vehicle use cases.

Uses mocked repositories and UoW — no database required.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from lpg.application.common.errors import (
    DuplicateEmployeeCodeError,
    DuplicateRegistrationNumberError,
    NotFoundError,
)
from lpg.application.delivery.use_cases import (
    GetDriverQuery,
    GetDriverUseCase,
    ListDriversQuery,
    ListDriversUseCase,
    RegisterDriverCommand,
    RegisterDriverUseCase,
    RegisterVehicleCommand,
    RegisterVehicleUseCase,
    UpdateDriverStatusCommand,
    UpdateDriverStatusUseCase,
    UpdateVehicleStatusCommand,
    UpdateVehicleStatusUseCase,
)
from lpg.domain.common.base import InvariantViolation
from lpg.domain.delivery.driver import Driver
from lpg.domain.delivery.vehicle import Vehicle


@pytest.fixture
def mock_uow() -> MagicMock:
    uow = MagicMock()
    uow.commit = AsyncMock()
    uow.register_aggregate = MagicMock()
    return uow


@pytest.fixture
def mock_driver_repo() -> MagicMock:
    repo = MagicMock()
    repo.next_id = MagicMock(return_value=uuid.uuid4())
    repo.save = AsyncMock()
    repo.get_by_employee_code = AsyncMock(return_value=None)
    repo.get_by_id = AsyncMock(return_value=None)
    repo.list_drivers = AsyncMock(return_value=[])
    repo.count_drivers = AsyncMock(return_value=0)
    return repo


@pytest.fixture
def mock_vehicle_repo() -> MagicMock:
    repo = MagicMock()
    repo.next_id = MagicMock(return_value=uuid.uuid4())
    repo.save = AsyncMock()
    repo.get_by_registration_number = AsyncMock(return_value=None)
    repo.get_by_id = AsyncMock(return_value=None)
    repo.list_vehicles = AsyncMock(return_value=[])
    repo.count_vehicles = AsyncMock(return_value=0)
    return repo


# ==========================================================================
# Driver use case tests
# ==========================================================================


async def test_register_driver_success(mock_driver_repo: MagicMock, mock_uow: MagicMock) -> None:
    use_case = RegisterDriverUseCase(mock_driver_repo, mock_uow)
    command = RegisterDriverCommand(
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        employee_code="EMP-001",
        license_number="DL-12345",
    )
    driver = await use_case.execute(command)

    assert driver.employee_code == "EMP-001"
    assert driver.status == "active"
    mock_driver_repo.save.assert_called_once_with(driver)
    mock_uow.commit.assert_called_once()


async def test_register_driver_duplicate_employee_code(
    mock_driver_repo: MagicMock, mock_uow: MagicMock
) -> None:
    mock_driver_repo.get_by_employee_code.return_value = MagicMock(spec=Driver)
    use_case = RegisterDriverUseCase(mock_driver_repo, mock_uow)
    command = RegisterDriverCommand(
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        employee_code="EMP-001",
        license_number="DL-12345",
    )
    with pytest.raises(DuplicateEmployeeCodeError):
        await use_case.execute(command)


async def test_update_driver_status_success(
    mock_driver_repo: MagicMock, mock_uow: MagicMock
) -> None:
    driver = Driver(
        driver_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        employee_code="EMP-001",
        license_number="DL-12345",
        status="active",
    )
    driver.clear_events()
    mock_driver_repo.get_by_id.return_value = driver

    use_case = UpdateDriverStatusUseCase(mock_driver_repo, mock_uow)
    command = UpdateDriverStatusCommand(driver_id=driver.id, new_status="on_leave")
    updated = await use_case.execute(command)

    assert updated.status == "on_leave"
    mock_driver_repo.save.assert_called_once()
    mock_uow.commit.assert_called_once()


async def test_update_driver_status_not_found(
    mock_driver_repo: MagicMock, mock_uow: MagicMock
) -> None:
    mock_driver_repo.get_by_id.return_value = None
    use_case = UpdateDriverStatusUseCase(mock_driver_repo, mock_uow)
    with pytest.raises(NotFoundError):
        await use_case.execute(
            UpdateDriverStatusCommand(driver_id=uuid.uuid4(), new_status="on_leave")
        )


async def test_update_driver_status_invalid_transition(
    mock_driver_repo: MagicMock, mock_uow: MagicMock
) -> None:
    driver = Driver(
        driver_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        employee_code="EMP-001",
        license_number="DL-12345",
        status="inactive",
    )
    driver.clear_events()
    mock_driver_repo.get_by_id.return_value = driver

    use_case = UpdateDriverStatusUseCase(mock_driver_repo, mock_uow)
    with pytest.raises(InvariantViolation):
        await use_case.execute(UpdateDriverStatusCommand(driver_id=driver.id, new_status="active"))


async def test_get_driver_not_found(mock_driver_repo: MagicMock) -> None:
    use_case = GetDriverUseCase(mock_driver_repo)
    with pytest.raises(NotFoundError):
        await use_case.execute(GetDriverQuery(driver_id=uuid.uuid4()))


async def test_list_drivers_empty(mock_driver_repo: MagicMock) -> None:
    use_case = ListDriversUseCase(mock_driver_repo)
    drivers, total = await use_case.execute(ListDriversQuery())
    assert drivers == []
    assert total == 0


# ==========================================================================
# Vehicle use case tests
# ==========================================================================


async def test_register_vehicle_success(mock_vehicle_repo: MagicMock, mock_uow: MagicMock) -> None:
    use_case = RegisterVehicleUseCase(mock_vehicle_repo, mock_uow)
    command = RegisterVehicleCommand(
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        registration_number="MH12AB1234",
        make="Tata",
        model="Ace",
        capacity_units=10,
    )
    vehicle = await use_case.execute(command)

    assert vehicle.registration_number == "MH12AB1234"
    assert vehicle.status == "active"
    mock_vehicle_repo.save.assert_called_once_with(vehicle)
    mock_uow.commit.assert_called_once()


async def test_register_vehicle_duplicate_registration(
    mock_vehicle_repo: MagicMock, mock_uow: MagicMock
) -> None:
    mock_vehicle_repo.get_by_registration_number.return_value = MagicMock(spec=Vehicle)
    use_case = RegisterVehicleUseCase(mock_vehicle_repo, mock_uow)
    command = RegisterVehicleCommand(
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        registration_number="MH12AB1234",
        make="Tata",
        model="Ace",
        capacity_units=10,
    )
    with pytest.raises(DuplicateRegistrationNumberError):
        await use_case.execute(command)


async def test_update_vehicle_status_success(
    mock_vehicle_repo: MagicMock, mock_uow: MagicMock
) -> None:
    vehicle = Vehicle(
        vehicle_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        registration_number="MH12AB1234",
        make="Tata",
        model="Ace",
        capacity_units=10,
        status="active",
    )
    vehicle.clear_events()
    mock_vehicle_repo.get_by_id.return_value = vehicle

    use_case = UpdateVehicleStatusUseCase(mock_vehicle_repo, mock_uow)
    updated = await use_case.execute(
        UpdateVehicleStatusCommand(vehicle_id=vehicle.id, new_status="maintenance")
    )

    assert updated.status == "maintenance"
    mock_vehicle_repo.save.assert_called_once()
    mock_uow.commit.assert_called_once()
