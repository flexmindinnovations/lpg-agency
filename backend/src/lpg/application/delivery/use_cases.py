"""Application use cases for the delivery bounded context.

Implements Driver and Vehicle management: registration, status transitions,
license updates, and read queries.

All commands follow the pattern established in Phase 8 (customer use cases):
- Check application-layer uniqueness before delegating to the domain.
- Delegate all business invariant checks to the aggregate.
- Persist via the repository, commit via the Unit of Work.
- Unit of Work dispatches domain events after commit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date  # noqa: TC003
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command, Query
from lpg.application.common.errors import (
    DuplicateEmployeeCodeError,
    DuplicateRegistrationNumberError,
    DuplicateRouteAssignmentError,
    NotFoundError,
    RouteReconciliationPendingError,
)
from lpg.application.inventory.use_cases import GetOrCreateInventoryLocationUseCase
from lpg.domain.delivery.driver import Driver
from lpg.domain.delivery.route import Route
from lpg.domain.delivery.vehicle import Vehicle
from lpg.domain.order.vehicle_capacity_checker import VehicleCapacityChecker

if TYPE_CHECKING:
    import datetime
    import uuid

    from lpg.application.common.ports import UnitOfWork
    from lpg.application.delivery.ports import (
        DriverRepository,
        RouteRepository,
        VehicleRepository,
    )
    from lpg.application.inventory.ports import (
        InventoryLocationRepository,
        ReconciliationRecordRepository,
    )
    from lpg.application.order.ports import OrderRepository
    from lpg.domain.order.order import Order


# ==========================================================================
# Driver Commands & Queries
# ==========================================================================


@dataclass(frozen=True, slots=True)
class RegisterDriverCommand(Command):
    tenant_id: uuid.UUID
    branch_id: uuid.UUID
    employee_id: uuid.UUID
    license_number: str
    license_expiry_date: date | None = None
    identity_user_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class UpdateDriverStatusCommand(Command):
    driver_id: uuid.UUID
    new_status: str


@dataclass(frozen=True, slots=True)
class UpdateDriverLicenseCommand(Command):
    driver_id: uuid.UUID
    license_number: str
    license_expiry_date: date | None


@dataclass(frozen=True, slots=True)
class UpdateDriverAssignmentCommand(Command):
    driver_id: uuid.UUID
    employee_id: uuid.UUID
    branch_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class GetDriverQuery(Query):
    driver_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class ListDriversQuery(Query):
    skip: int = 0
    limit: int = 50
    search: str | None = None
    status: str | None = None
    branch_id: uuid.UUID | None = None


# ==========================================================================
# Driver Use Cases
# ==========================================================================


class RegisterDriverUseCase:
    def __init__(
        self,
        repository: DriverRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: RegisterDriverCommand) -> Driver:
        existing = await self._repository.get_by_employee_id(command.employee_id)
        if existing is not None:
            msg = f"Driver with employee ID '{command.employee_id}' already exists for this tenant."
            raise DuplicateEmployeeCodeError(msg)

        driver = Driver(
            driver_id=self._repository.next_id(),
            tenant_id=command.tenant_id,
            branch_id=command.branch_id,
            employee_id=command.employee_id,
            license_number=command.license_number,
            license_expiry_date=command.license_expiry_date,
            identity_user_id=command.identity_user_id,
        )

        await self._repository.save(driver)
        await self._unit_of_work.commit()
        return driver


class UpdateDriverStatusUseCase:
    def __init__(
        self,
        repository: DriverRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: UpdateDriverStatusCommand) -> Driver:
        driver = await self._repository.get_by_id(command.driver_id)
        if driver is None:
            msg = f"Driver '{command.driver_id}' not found."
            raise NotFoundError(msg, driver_id=str(command.driver_id))

        driver.change_status(command.new_status)
        await self._repository.save(driver)
        await self._unit_of_work.commit()
        return driver


class UpdateDriverLicenseUseCase:
    def __init__(
        self,
        repository: DriverRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: UpdateDriverLicenseCommand) -> Driver:
        driver = await self._repository.get_by_id(command.driver_id)
        if driver is None:
            msg = f"Driver '{command.driver_id}' not found."
            raise NotFoundError(msg, driver_id=str(command.driver_id))

        driver.update_license(command.license_number, command.license_expiry_date)
        await self._repository.save(driver)
        await self._unit_of_work.commit()
        return driver


class UpdateDriverAssignmentUseCase:
    """Relinks a driver profile to a (possibly different) employee/branch.

    Mirrors `RegisterDriverUseCase`'s duplicate-employee check — except a
    driver reassigned onto its *own current* employee_id (only the branch
    changing) is not a duplicate, so the check is skipped when the employee
    isn't actually changing.
    """

    def __init__(
        self,
        repository: DriverRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: UpdateDriverAssignmentCommand) -> Driver:
        driver = await self._repository.get_by_id(command.driver_id)
        if driver is None:
            msg = f"Driver '{command.driver_id}' not found."
            raise NotFoundError(msg, driver_id=str(command.driver_id))

        if command.employee_id != driver.employee_id:
            existing = await self._repository.get_by_employee_id(command.employee_id)
            if existing is not None:
                msg = (
                    f"Driver with employee ID '{command.employee_id}' "
                    "already exists for this tenant."
                )
                raise DuplicateEmployeeCodeError(msg)

        driver.reassign(command.employee_id, command.branch_id)
        await self._repository.save(driver)
        await self._unit_of_work.commit()
        return driver


class GetDriverUseCase:
    def __init__(self, repository: DriverRepository) -> None:
        self._repository = repository

    async def execute(self, query: GetDriverQuery) -> Driver:
        driver = await self._repository.get_by_id(query.driver_id)
        if driver is None:
            msg = f"Driver '{query.driver_id}' not found."
            raise NotFoundError(msg, driver_id=str(query.driver_id))
        return driver


class ListDriversUseCase:
    def __init__(self, repository: DriverRepository) -> None:
        self._repository = repository

    async def execute(self, query: ListDriversQuery) -> tuple[list[Driver], int]:
        drivers = await self._repository.list_drivers(
            skip=query.skip,
            limit=query.limit,
            search=query.search,
            status=query.status,
            branch_id=query.branch_id,
        )
        total = await self._repository.count_drivers(
            search=query.search,
            status=query.status,
            branch_id=query.branch_id,
        )
        return drivers, total


# ==========================================================================
# Vehicle Commands & Queries
# ==========================================================================


@dataclass(frozen=True, slots=True)
class RegisterVehicleCommand(Command):
    tenant_id: uuid.UUID
    branch_id: uuid.UUID
    registration_number: str
    make: str
    model: str
    ownership_type: str = "owned"
    capacity_units: int = 1


@dataclass(frozen=True, slots=True)
class UpdateVehicleStatusCommand(Command):
    vehicle_id: uuid.UUID
    new_status: str


@dataclass(frozen=True, slots=True)
class UpdateVehicleDetailsCommand(Command):
    vehicle_id: uuid.UUID
    make: str
    model: str
    ownership_type: str
    capacity_units: int


@dataclass(frozen=True, slots=True)
class GetVehicleQuery(Query):
    vehicle_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class ListVehiclesQuery(Query):
    skip: int = 0
    limit: int = 50
    search: str | None = None
    status: str | None = None
    branch_id: uuid.UUID | None = None


# ==========================================================================
# Vehicle Use Cases
# ==========================================================================


class RegisterVehicleUseCase:
    def __init__(
        self,
        repository: VehicleRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: RegisterVehicleCommand) -> Vehicle:
        existing = await self._repository.get_by_registration_number(command.registration_number)
        if existing is not None:
            msg = (
                f"Vehicle with registration number "
                f"'{command.registration_number}' already exists for this tenant."
            )
            raise DuplicateRegistrationNumberError(
                msg, registration_number=command.registration_number
            )

        vehicle = Vehicle(
            vehicle_id=self._repository.next_id(),
            tenant_id=command.tenant_id,
            branch_id=command.branch_id,
            registration_number=command.registration_number,
            make=command.make,
            model=command.model,
            ownership_type=command.ownership_type,
            capacity_units=command.capacity_units,
        )

        await self._repository.save(vehicle)
        await self._unit_of_work.commit()
        return vehicle


class UpdateVehicleStatusUseCase:
    def __init__(
        self,
        repository: VehicleRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: UpdateVehicleStatusCommand) -> Vehicle:
        vehicle = await self._repository.get_by_id(command.vehicle_id)
        if vehicle is None:
            msg = f"Vehicle '{command.vehicle_id}' not found."
            raise NotFoundError(msg, vehicle_id=str(command.vehicle_id))

        vehicle.change_status(command.new_status)
        await self._repository.save(vehicle)
        await self._unit_of_work.commit()
        return vehicle


class UpdateVehicleDetailsUseCase:
    def __init__(
        self,
        repository: VehicleRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: UpdateVehicleDetailsCommand) -> Vehicle:
        vehicle = await self._repository.get_by_id(command.vehicle_id)
        if vehicle is None:
            msg = f"Vehicle '{command.vehicle_id}' not found."
            raise NotFoundError(msg, vehicle_id=str(command.vehicle_id))

        vehicle.update_details(
            command.make, command.model, command.ownership_type, command.capacity_units
        )
        await self._repository.save(vehicle)
        await self._unit_of_work.commit()
        return vehicle


class GetVehicleUseCase:
    def __init__(self, repository: VehicleRepository) -> None:
        self._repository = repository

    async def execute(self, query: GetVehicleQuery) -> Vehicle:
        vehicle = await self._repository.get_by_id(query.vehicle_id)
        if vehicle is None:
            msg = f"Vehicle '{query.vehicle_id}' not found."
            raise NotFoundError(msg, vehicle_id=str(query.vehicle_id))
        return vehicle


class ListVehiclesUseCase:
    def __init__(self, repository: VehicleRepository) -> None:
        self._repository = repository

    async def execute(self, query: ListVehiclesQuery) -> tuple[list[Vehicle], int]:
        vehicles = await self._repository.list_vehicles(
            skip=query.skip,
            limit=query.limit,
            search=query.search,
            status=query.status,
            branch_id=query.branch_id,
        )
        total = await self._repository.count_vehicles(
            search=query.search,
            status=query.status,
            branch_id=query.branch_id,
        )
        return vehicles, total


@dataclass(frozen=True, slots=True)
class PlanRouteCommand:
    tenant_id: uuid.UUID
    branch_id: uuid.UUID
    driver_id: uuid.UUID
    vehicle_id: uuid.UUID
    route_date: datetime.datetime | None = None


@dataclass(frozen=True, slots=True)
class AssignOrderToRouteCommand:
    route_id: uuid.UUID
    order_id: uuid.UUID
    changed_by: uuid.UUID


@dataclass(frozen=True, slots=True)
class AssignOrderToRouteResult:
    route: Route
    order: Order


@dataclass(frozen=True, slots=True)
class LoadVehicleLine:
    cylinder_type_id: uuid.UUID
    quantity: int


@dataclass(frozen=True, slots=True)
class LoadVehicleForRouteCommand:
    route_id: uuid.UUID
    warehouse_id: uuid.UUID
    lines: list[LoadVehicleLine]
    performed_by: uuid.UUID


@dataclass(frozen=True, slots=True)
class CompleteRouteReconciliationCommand:
    route_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class UpdateRouteStatusCommand:
    route_id: uuid.UUID
    new_status: str


@dataclass(frozen=True, slots=True)
class ListRoutesQuery:
    skip: int = 0
    limit: int = 50
    status: str | None = None
    branch_id: uuid.UUID | None = None
    date_from: datetime.date | None = None
    date_to: datetime.date | None = None


@dataclass(frozen=True, slots=True)
class GetRouteQuery:
    route_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class GetActiveRouteForDriverQuery:
    driver_id: uuid.UUID


# ---------------------------------------------------------------------------
# Use Cases
# ---------------------------------------------------------------------------


class PlanRouteUseCase:
    """Creates a new route assignment for a driver and vehicle."""

    def __init__(self, repository: RouteRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: PlanRouteCommand) -> Route:
        route = Route(
            route_id=self._repository.next_id(),
            tenant_id=command.tenant_id,
            branch_id=command.branch_id,
            driver_id=command.driver_id,
            vehicle_id=command.vehicle_id,
            route_date=command.route_date,
            status="planned",
            stops=[],
        )
        route.record_planned()
        await self._repository.save(route)
        await self._unit_of_work.commit()
        return route


class AssignOrderToRouteUseCase:
    """Assigns an order to an existing `planned`/`loaded` route — atomic:
    `Route` (new `RouteStop`) + `Order` (line reservations, `route_stop_id`,
    `confirmed -> assigned`) + the vehicle's `InventoryLocation`. Exact copy
    of `LoadTransferUseCase`'s shape: mutate every aggregate in memory
    first, save all, commit once. The single-order "assign" entry point on
    `Order` (`application/order/use_cases.py::AssignOrderUseCase`) resolves
    a `route_id` (finding or planning one) and then delegates here — this
    class is also the direct handler for the Dispatch Board's own
    "assign this unassigned order onto that already-planned route" action.
    """

    def __init__(
        self,
        route_repository: RouteRepository,
        order_repository: OrderRepository,
        inventory_location_repository: InventoryLocationRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._route_repository = route_repository
        self._order_repository = order_repository
        self._inventory_repository = inventory_location_repository
        self._unit_of_work = unit_of_work
        self._get_or_create_location = GetOrCreateInventoryLocationUseCase(
            inventory_location_repository
        )

    async def execute(self, command: AssignOrderToRouteCommand) -> AssignOrderToRouteResult:
        route = await self._route_repository.get_by_id(command.route_id)
        if route is None:
            msg = f"No route visible with id {command.route_id}."
            raise NotFoundError(msg, route_id=str(command.route_id))
        order = await self._order_repository.get_by_id(command.order_id)
        if order is None:
            msg = f"No order visible with id {command.order_id}."
            raise NotFoundError(msg, order_id=str(command.order_id))

        active_routes = await self._route_repository.count_active_routes_for_order(order.id)
        if active_routes > 0:
            msg = f"Order {order.id} is already assigned to an active route."
            raise DuplicateRouteAssignmentError(msg, order_id=str(order.id))

        vehicle_location = await self._get_or_create_location.execute(
            tenant_id=order.tenant_id, location_type="vehicle", location_ref_id=route.vehicle_id
        )
        vehicle_balances = {
            line.cylinder_type_id: vehicle_location.balance_of(line.cylinder_type_id, "filled")
            for line in order.lines
        }
        lines_for_allocation = [
            (line.cylinder_type_id, line.quantity_ordered) for line in order.lines
        ]
        allocation = VehicleCapacityChecker.allocate(
            vehicle_balances=vehicle_balances, lines=lines_for_allocation
        )
        reservations = {ct: reserved for ct, (reserved, _pending) in allocation.items()}
        backorders = {ct: pending for ct, (_reserved, pending) in allocation.items()}

        # All mutation happens in memory before any save — if reserve()
        # raises partway through, nothing below has run and nothing is
        # saved (same reasoning `AssignOrderUseCase`'s own docstring gives).
        for cylinder_type_id, (reserved, _pending) in allocation.items():
            if reserved > 0:
                vehicle_location.reserve(
                    cylinder_type_id,
                    reserved,
                    performed_by=command.changed_by,
                    reference_order_id=order.id,
                )

        route.assign_order(order.id)
        new_stop = next(s for s in route.stops if s.order_id == order.id)
        order.assign(
            route_stop_id=new_stop.id,
            reservations=reservations,
            backorders=backorders,
            changed_by=command.changed_by,
        )

        await self._route_repository.save(route)
        await self._order_repository.save(order)
        await self._inventory_repository.save(vehicle_location)
        await self._unit_of_work.commit()
        return AssignOrderToRouteResult(route=route, order=order)


class LoadVehicleForRouteUseCase:
    """`planned -> loaded` (BR-12): moves stock warehouse -> vehicle and
    marks the route loaded, atomically. Reuses `InventoryLocation.unload()`/
    `.load()` (the same domain methods `LoadTransferUseCase` calls) rather
    than duplicating BR-12's transfer logic — doesn't call
    `LoadTransferUseCase.execute()` itself since that use case owns its own
    commit, which would break this operation's atomicity with the route's
    own status change.
    """

    def __init__(
        self,
        route_repository: RouteRepository,
        inventory_location_repository: InventoryLocationRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._route_repository = route_repository
        self._inventory_repository = inventory_location_repository
        self._unit_of_work = unit_of_work
        self._get_or_create_location = GetOrCreateInventoryLocationUseCase(
            inventory_location_repository
        )

    async def execute(self, command: LoadVehicleForRouteCommand) -> Route:
        route = await self._route_repository.get_by_id(command.route_id)
        if route is None:
            msg = f"No route visible with id {command.route_id}."
            raise NotFoundError(msg, route_id=str(command.route_id))

        warehouse_location = await self._get_or_create_location.execute(
            tenant_id=route.tenant_id,
            location_type="warehouse",
            location_ref_id=command.warehouse_id,
        )
        vehicle_location = await self._get_or_create_location.execute(
            tenant_id=route.tenant_id, location_type="vehicle", location_ref_id=route.vehicle_id
        )

        for line in command.lines:
            warehouse_location.unload(
                line.cylinder_type_id, "filled", line.quantity, performed_by=command.performed_by
            )
            vehicle_location.load(
                line.cylinder_type_id, "filled", line.quantity, performed_by=command.performed_by
            )

        route.change_status("loaded")

        await self._inventory_repository.save(warehouse_location)
        await self._inventory_repository.save(vehicle_location)
        await self._route_repository.save(route)
        await self._unit_of_work.commit()
        return route


class CompleteRouteReconciliationUseCase:
    """`completed -> reconciled` (BR-14): only once the vehicle's
    `InventoryLocation` has an *approved* `ReconciliationRecord` — Route
    references Inventory's own reconciliation outcome rather than
    reimplementing D-16/D-31's approval-restricted reconciliation flow.
    """

    def __init__(
        self,
        route_repository: RouteRepository,
        inventory_location_repository: InventoryLocationRepository,
        reconciliation_repository: ReconciliationRecordRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._route_repository = route_repository
        self._inventory_repository = inventory_location_repository
        self._reconciliation_repository = reconciliation_repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: CompleteRouteReconciliationCommand) -> Route:
        route = await self._route_repository.get_by_id(command.route_id)
        if route is None:
            msg = f"No route visible with id {command.route_id}."
            raise NotFoundError(msg, route_id=str(command.route_id))

        vehicle_location = await self._inventory_repository.get_by_location_ref(
            "vehicle", route.vehicle_id
        )
        record = (
            await self._reconciliation_repository.get_latest_for_location(vehicle_location.id)
            if vehicle_location is not None
            else None
        )
        if record is None or record.approved_by is None:
            msg = f"Route {route.id}'s vehicle has no approved reconciliation yet."
            raise RouteReconciliationPendingError(msg, route_id=str(route.id))

        route.change_status("reconciled")
        await self._route_repository.save(route)
        await self._unit_of_work.commit()
        return route


class UpdateRouteStatusUseCase:
    """Transitions a route to a new status. Only `in_progress`/`cancelled`
    are reachable via this use case — the API schema's `new_status` field
    is typed `Literal["in_progress", "cancelled"]` precisely so `loaded`/
    `reconciled` (which need cross-aggregate coordination the domain method
    alone can't perform) can never reach here; only
    `LoadVehicleForRouteUseCase`/`CompleteRouteReconciliationUseCase` set
    those, after doing that coordination themselves.
    """

    def __init__(self, repository: RouteRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: UpdateRouteStatusCommand) -> Route:
        route = await self._repository.get_by_id(command.route_id)
        if route is None:
            msg = f"No route visible with id {command.route_id}."
            raise NotFoundError(msg, route_id=str(command.route_id))

        route.change_status(command.new_status)
        await self._repository.save(route)
        await self._unit_of_work.commit()
        return route


class ListRoutesUseCase:
    """Lists routes matching optional filters."""

    def __init__(self, repository: RouteRepository) -> None:
        self._repository = repository

    async def execute(self, query: ListRoutesQuery) -> tuple[list[Route], int]:
        total = await self._repository.count_routes(
            status=query.status,
            branch_id=query.branch_id,
            date_from=query.date_from,
            date_to=query.date_to,
        )
        if total == 0:
            return [], 0

        items = await self._repository.list_routes(
            skip=query.skip,
            limit=query.limit,
            status=query.status,
            branch_id=query.branch_id,
            date_from=query.date_from,
            date_to=query.date_to,
        )
        return items, total


class GetRouteUseCase:
    """Retrieves a single route by ID."""

    def __init__(self, repository: RouteRepository) -> None:
        self._repository = repository

    async def execute(self, query: GetRouteQuery) -> Route:
        route = await self._repository.get_by_id(query.route_id)
        if route is None:
            msg = f"No route visible with id {query.route_id}."
            raise NotFoundError(msg, route_id=str(query.route_id))
        return route


class GetActiveRouteForDriverUseCase:
    """Retrieves the active route for a driver, if any."""

    def __init__(self, repository: RouteRepository) -> None:
        self._repository = repository

    async def execute(self, query: GetActiveRouteForDriverQuery) -> Route:
        route = await self._repository.get_active_route_for_driver(query.driver_id)
        if route is None:
            msg = f"No active route for driver {query.driver_id}."
            raise NotFoundError(msg, driver_id=str(query.driver_id))
        return route
