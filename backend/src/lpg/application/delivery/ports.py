"""Repository ports for the delivery bounded context.

Defines the abstract interface (Protocol) that the infrastructure layer must
implement.  The application layer depends only on these protocols — never on
SQLAlchemy or any other concrete technology.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import datetime
    import uuid

    from lpg.domain.delivery.driver import Driver
    from lpg.domain.delivery.route import Route
    from lpg.domain.delivery.vehicle import Vehicle


@dataclass(frozen=True, slots=True)
class RouteStopOwner:
    """Narrow projection of a `RouteStop`'s parent `Route` — driver-ownership
    checks (`_require_own_driver_order`) and vehicle-inventory lookups
    (`DeliverOrderUseCase`/`CancelOrderUseCase`/`ApproveOrderCancellationUseCase`)
    need only these three ids, not the whole aggregate. Matches the
    "narrow aggregation methods" pattern already used elsewhere in this
    codebase rather than loading a full `Route` for a single-field read.
    """

    route_id: uuid.UUID
    driver_id: uuid.UUID
    vehicle_id: uuid.UUID


class DriverRepository(Protocol):
    def next_id(self) -> uuid.UUID: ...

    async def save(self, driver: Driver) -> None: ...

    async def get_by_id(self, driver_id: uuid.UUID) -> Driver | None: ...

    async def get_by_employee_code(self, employee_code: str) -> Driver | None: ...

    async def get_by_identity_user_id(self, identity_user_id: uuid.UUID) -> Driver | None: ...

    async def list_drivers(
        self,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        status: str | None = None,
        branch_id: uuid.UUID | None = None,
    ) -> list[Driver]: ...

    async def count_drivers(
        self,
        search: str | None = None,
        status: str | None = None,
        branch_id: uuid.UUID | None = None,
    ) -> int: ...


class VehicleRepository(Protocol):
    def next_id(self) -> uuid.UUID: ...

    async def save(self, vehicle: Vehicle) -> None: ...

    async def get_by_id(self, vehicle_id: uuid.UUID) -> Vehicle | None: ...

    async def get_by_registration_number(self, registration_number: str) -> Vehicle | None: ...

    async def list_vehicles(
        self,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        status: str | None = None,
        branch_id: uuid.UUID | None = None,
    ) -> list[Vehicle]: ...

    async def count_vehicles(
        self,
        search: str | None = None,
        status: str | None = None,
        branch_id: uuid.UUID | None = None,
    ) -> int: ...

    async def count_by_status(self) -> dict[str, int]:
        """Vehicle counts grouped by status, for dashboard summaries."""
        ...


class RouteRepository(Protocol):
    def next_id(self) -> uuid.UUID: ...

    async def save(self, route: Route) -> None: ...

    async def get_by_id(self, route_id: uuid.UUID) -> Route | None: ...

    async def get_active_route_for_driver(self, driver_id: uuid.UUID) -> Route | None: ...

    async def get_route_with_open_stop_for(
        self, driver_id: uuid.UUID, vehicle_id: uuid.UUID, route_date: datetime.date
    ) -> Route | None:
        """The single-order "quick assign" path's find-or-create lookup:
        an existing `planned`/`loaded` route for this exact driver+vehicle+
        date, if one already exists, so a second order assigned to the same
        driver/vehicle/day joins the same route rather than spawning a new
        one-stop route per order.
        """
        ...

    async def count_active_routes_for_order(self, order_id: uuid.UUID) -> int:
        """Guards against the same order being assigned to two different
        routes — `Route.assign_order()` only rejects a *duplicate* stop on
        the *same* route, this catches the cross-route case.
        """
        ...

    async def get_stop_owner(self, route_stop_id: uuid.UUID) -> RouteStopOwner | None: ...

    async def list_routes(
        self,
        skip: int = 0,
        limit: int = 100,
        status: str | None = None,
        branch_id: uuid.UUID | None = None,
        date_from: datetime.date | None = None,
        date_to: datetime.date | None = None,
    ) -> list[Route]: ...

    async def count_routes(
        self,
        status: str | None = None,
        branch_id: uuid.UUID | None = None,
        date_from: datetime.date | None = None,
        date_to: datetime.date | None = None,
    ) -> int: ...
