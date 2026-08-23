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
    UpdateDriverAssignmentCommand,
    UpdateDriverAssignmentUseCase,
    UpdateDriverStatusCommand,
    UpdateDriverStatusUseCase,
    UpdateVehicleDetailsCommand,
    UpdateVehicleDetailsUseCase,
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
    repo.get_by_employee_id = AsyncMock(return_value=None)
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
        employee_id=uuid.uuid4(),
        license_number="DL-12345",
    )
    driver = await use_case.execute(command)

    assert driver.employee_id == command.employee_id
    assert driver.status == "active"
    mock_driver_repo.save.assert_called_once_with(driver)
    mock_uow.commit.assert_called_once()


async def test_register_driver_duplicate_employee_id(
    mock_driver_repo: MagicMock, mock_uow: MagicMock
) -> None:
    mock_driver_repo.get_by_employee_id.return_value = MagicMock(spec=Driver)
    use_case = RegisterDriverUseCase(mock_driver_repo, mock_uow)
    command = RegisterDriverCommand(
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        employee_id=uuid.uuid4(),
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
        employee_id=uuid.uuid4(),
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
        employee_id=uuid.uuid4(),
        license_number="DL-12345",
        status="inactive",
    )
    driver.clear_events()
    mock_driver_repo.get_by_id.return_value = driver

    use_case = UpdateDriverStatusUseCase(mock_driver_repo, mock_uow)
    with pytest.raises(InvariantViolation):
        await use_case.execute(UpdateDriverStatusCommand(driver_id=driver.id, new_status="active"))


async def test_update_driver_assignment_success(
    mock_driver_repo: MagicMock, mock_uow: MagicMock
) -> None:
    driver = Driver(
        driver_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        employee_id=uuid.uuid4(),
        license_number="DL-12345",
    )
    driver.clear_events()
    mock_driver_repo.get_by_id.return_value = driver
    mock_driver_repo.get_by_employee_id.return_value = None

    new_employee_id = uuid.uuid4()
    new_branch_id = uuid.uuid4()
    use_case = UpdateDriverAssignmentUseCase(mock_driver_repo, mock_uow)
    updated = await use_case.execute(
        UpdateDriverAssignmentCommand(
            driver_id=driver.id, employee_id=new_employee_id, branch_id=new_branch_id
        )
    )

    assert updated.employee_id == new_employee_id
    assert updated.branch_id == new_branch_id
    mock_driver_repo.save.assert_called_once()
    mock_uow.commit.assert_called_once()


async def test_update_driver_assignment_not_found(
    mock_driver_repo: MagicMock, mock_uow: MagicMock
) -> None:
    mock_driver_repo.get_by_id.return_value = None
    use_case = UpdateDriverAssignmentUseCase(mock_driver_repo, mock_uow)
    with pytest.raises(NotFoundError):
        await use_case.execute(
            UpdateDriverAssignmentCommand(
                driver_id=uuid.uuid4(), employee_id=uuid.uuid4(), branch_id=uuid.uuid4()
            )
        )


async def test_update_driver_assignment_duplicate_employee_id(
    mock_driver_repo: MagicMock, mock_uow: MagicMock
) -> None:
    driver = Driver(
        driver_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        employee_id=uuid.uuid4(),
        license_number="DL-12345",
    )
    driver.clear_events()
    mock_driver_repo.get_by_id.return_value = driver
    # A *different* driver already has the target employee_id.
    mock_driver_repo.get_by_employee_id.return_value = MagicMock(spec=Driver)

    use_case = UpdateDriverAssignmentUseCase(mock_driver_repo, mock_uow)
    with pytest.raises(DuplicateEmployeeCodeError):
        await use_case.execute(
            UpdateDriverAssignmentCommand(
                driver_id=driver.id, employee_id=uuid.uuid4(), branch_id=uuid.uuid4()
            )
        )


async def test_update_driver_assignment_same_employee_id_skips_duplicate_check(
    mock_driver_repo: MagicMock, mock_uow: MagicMock
) -> None:
    """Reassigning only the branch (employee_id unchanged) must not trip the
    duplicate-employee check against the driver's own existing record."""
    employee_id = uuid.uuid4()
    driver = Driver(
        driver_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        employee_id=employee_id,
        license_number="DL-12345",
    )
    driver.clear_events()
    mock_driver_repo.get_by_id.return_value = driver

    new_branch_id = uuid.uuid4()
    use_case = UpdateDriverAssignmentUseCase(mock_driver_repo, mock_uow)
    updated = await use_case.execute(
        UpdateDriverAssignmentCommand(
            driver_id=driver.id, employee_id=employee_id, branch_id=new_branch_id
        )
    )

    assert updated.branch_id == new_branch_id
    mock_driver_repo.get_by_employee_id.assert_not_called()


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


async def test_update_vehicle_details_success(
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

    use_case = UpdateVehicleDetailsUseCase(mock_vehicle_repo, mock_uow)
    updated = await use_case.execute(
        UpdateVehicleDetailsCommand(
            vehicle_id=vehicle.id,
            make="Ashok Leyland",
            model="Dost+",
            ownership_type="rental",
            capacity_units=25,
        )
    )

    assert updated.make == "Ashok Leyland"
    assert updated.model == "Dost+"
    assert updated.ownership_type == "rental"
    assert updated.capacity_units == 25
    mock_vehicle_repo.save.assert_called_once()
    mock_uow.commit.assert_called_once()


async def test_update_vehicle_details_not_found(
    mock_vehicle_repo: MagicMock, mock_uow: MagicMock
) -> None:
    mock_vehicle_repo.get_by_id.return_value = None
    use_case = UpdateVehicleDetailsUseCase(mock_vehicle_repo, mock_uow)
    with pytest.raises(NotFoundError):
        await use_case.execute(
            UpdateVehicleDetailsCommand(
                vehicle_id=uuid.uuid4(),
                make="Tata",
                model="Ace",
                ownership_type="owned",
                capacity_units=10,
            )
        )


async def test_update_vehicle_details_invalid_ownership_type(
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

    use_case = UpdateVehicleDetailsUseCase(mock_vehicle_repo, mock_uow)
    with pytest.raises(InvariantViolation):
        await use_case.execute(
            UpdateVehicleDetailsCommand(
                vehicle_id=vehicle.id,
                make="Tata",
                model="Ace",
                ownership_type="leased",
                capacity_units=10,
            )
        )
