"""Deterministic driver/vehicle suggestion for zero-click auto-assignment.

Plain filtering + sorting — no model, no prompt, no hallucination surface.
Matches this codebase's own stated AI-guardrail philosophy (`docs/
architecture/15-architecture-decision-records.md` ADR-045, `planning/
features/23-ai-assistive-interfaces/PLAN.md`'s "the model never decides
anything that carries money, entitlement, or compliance weight"): picking
the least-loaded idle driver in the right branch is a data query, not a
judgment call an LLM should make.

This use case only *suggests* — `SuggestDriverAndVehicleForOrderUseCase.
execute()` never mutates anything and never raises for "no eligible
candidate" (returns `None`); the caller (`infrastructure/jobs/
auto_assignment_jobs.py`) decides what to do with that, including the
no-driver fallback. The actual assignment still goes through the exact
same `AssignOrderUseCase`/`AssignOrderToRouteUseCase` a human's click
would use — this file never touches an `Order`/`Route`/`InventoryLocation`
aggregate directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Query

if TYPE_CHECKING:
    import uuid

    from lpg.application.delivery.ports import DriverRepository, RouteRepository, VehicleRepository
    from lpg.application.order.ports import OrderRepository

#: Route/stop statuses that still occupy a driver or vehicle's day —
#: mirrors `RouteRepository.get_active_route_for_driver`'s own
#: `["planned", "loaded", "in_progress"]` filter for routes, and excludes
#: only the terminal stop statuses when counting today's load.
_TERMINAL_STOP_STATUSES = frozenset({"delivered", "failed", "cancelled"})


@dataclass(frozen=True, slots=True)
class SuggestDriverAndVehicleForOrderQuery(Query):
    order_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class DriverVehicleSuggestion:
    """A ranked, explainable suggestion — `reasons` are plain fixed strings
    (not LLM-generated free text) suitable for a future audit/explainability
    surface without any risk of a hallucinated justification."""

    driver_id: uuid.UUID
    vehicle_id: uuid.UUID
    reasons: tuple[str, ...]


class SuggestDriverAndVehicleForOrderUseCase:
    """Filters to active, same-branch, currently-idle drivers/vehicles and
    ranks by today's existing load — never raises; `None` means "nothing
    eligible," which the caller must treat as a normal, expected outcome
    (an empty branch, or everyone already on a route), not an error.
    """

    def __init__(
        self,
        order_repository: OrderRepository,
        driver_repository: DriverRepository,
        vehicle_repository: VehicleRepository,
        route_repository: RouteRepository,
    ) -> None:
        self._order_repository = order_repository
        self._driver_repository = driver_repository
        self._vehicle_repository = vehicle_repository
        self._route_repository = route_repository

    async def execute(
        self, query: SuggestDriverAndVehicleForOrderQuery
    ) -> DriverVehicleSuggestion | None:
        order = await self._order_repository.get_by_id(query.order_id)
        if order is None:
            return None

        driver = await self._pick_driver(order.branch_id)
        if driver is None:
            return None

        vehicle_id = await self._pick_vehicle(order.branch_id)
        if vehicle_id is None:
            return None

        return DriverVehicleSuggestion(
            driver_id=driver,
            vehicle_id=vehicle_id,
            reasons=(
                "same branch as the order",
                "no active route (currently idle)",
                "fewest active stops scheduled today",
            ),
        )

    async def _pick_driver(self, branch_id: uuid.UUID) -> uuid.UUID | None:
        candidates = await self._driver_repository.list_drivers(
            status="active", branch_id=branch_id, limit=200
        )
        if not candidates:
            return None

        idle_ids: list[uuid.UUID] = []
        for driver in candidates:
            active_route = await self._route_repository.get_active_route_for_driver(driver.id)
            if active_route is None:
                idle_ids.append(driver.id)
        if not idle_ids:
            return None
        if len(idle_ids) == 1:
            return idle_ids[0]

        load_by_driver = await self._today_stop_counts(branch_id)
        idle_ids.sort(key=lambda driver_id: load_by_driver.get(driver_id, 0))
        return idle_ids[0]

    async def _pick_vehicle(self, branch_id: uuid.UUID) -> uuid.UUID | None:
        candidates = await self._vehicle_repository.list_vehicles(
            status="active", branch_id=branch_id, limit=200
        )
        if not candidates:
            return None

        idle: list[tuple[uuid.UUID, int]] = []
        for vehicle in candidates:
            active_route = await self._route_repository.get_active_route_for_vehicle(vehicle.id)
            if active_route is None:
                idle.append((vehicle.id, vehicle.capacity_units))
        if not idle:
            return None

        # Real capacity checking happens for real inside
        # `AssignOrderToRouteUseCase.execute()` -> `VehicleCapacityChecker.
        # allocate()`, exactly as it does for a manual assignment; this is
        # only a cheap heuristic (largest capacity first) to minimize the
        # odds of a backorder, not a hard gate.
        idle.sort(key=lambda pair: pair[1], reverse=True)
        return idle[0][0]

    async def _today_stop_counts(self, branch_id: uuid.UUID) -> dict[uuid.UUID, int]:
        """One query, not one per candidate driver — avoids real N+1 for
        the load-balancing tiebreak (accepted-cost precedent:
        `GetTodayDeliveryStatusUseCase` already runs a comparable handful
        of queries per call, `application/order/use_cases.py`)."""
        today = datetime.now(UTC).date()
        routes = await self._route_repository.list_routes(
            branch_id=branch_id, date_from=today, date_to=today, limit=500
        )
        counts: dict[uuid.UUID, int] = {}
        for route in routes:
            active_stops = sum(
                1 for stop in route.stops if stop.status not in _TERMINAL_STOP_STATUSES
            )
            counts[route.driver_id] = counts.get(route.driver_id, 0) + active_stops
        return counts
