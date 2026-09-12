"""Auto-route stop resequencing — AI Operational Intelligence, Horizon 1
Stage 5.

Pure-Python nearest-neighbour + 2-opt over haversine distance between
consecutive stops' delivery coordinates — no OR-Tools, no new dependency,
adequate for the realistic 5-25 stops/route this codebase's own Dispatch
Board shows. A full multi-vehicle CVRP solver and a real road-time matrix
(as opposed to straight-line distance) are the documented Horizon-2
upgrade, not built here.

Stops whose order has no delivery coordinates (an older order booked
before LocationIQ geocoding, or a manual address entry) keep their current
relative position, appended after the optimised block — guessing a
position for an unlocated stop would be worse than leaving it alone.

Applies the resequence immediately via `Route.resequence_stops()` — fully
reversible, since only sequence numbers move, and records the proposal to
`ai.prediction` (`prediction_type="route_sequence"`) first, the same
traceability contract every Horizon 1 heuristic follows.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lpg.application.ai.prediction import RecordPredictionCommand, RecordPredictionUseCase
from lpg.application.common.config import is_truthy_config_value
from lpg.application.common.cqrs import Command
from lpg.application.common.errors import NotFoundError, RouteOptimizationDisabledError
from lpg.application.tenant.tenant_configuration import (
    GetEffectiveTenantConfigurationQuery,
    GetEffectiveTenantConfigurationUseCase,
)

if TYPE_CHECKING:
    import uuid

    from lpg.application.ai.prediction import PredictionRepository
    from lpg.application.common.ports import UnitOfWork
    from lpg.application.delivery.ports import RouteRepository
    from lpg.application.order.ports import OrderRepository
    from lpg.application.tenant.ports import TenantConfigurationRepository
    from lpg.domain.delivery.route import Route

#: `ai.prediction.model_version` every route-sequence proposal is stamped
#: with — a deterministic solver, not a trained model, honestly labelled.
MODEL_VERSION = "route_nn_2opt_v1"
PREDICTION_TYPE = "route_sequence"

_EARTH_RADIUS_KM = 6371.0

Coordinate = tuple[float, float]


def _haversine_km(a: Coordinate, b: Coordinate) -> float:
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def _tour_length(order: list[int], coords: list[Coordinate]) -> float:
    return sum(
        _haversine_km(coords[order[i]], coords[order[i + 1]]) for i in range(len(order) - 1)
    )


def nearest_neighbour(coords: list[Coordinate]) -> list[int]:
    """Greedy construction: starting from the first coordinate (the
    route's own current first located stop), repeatedly visits whichever
    unvisited point is nearest. Returns an ordering of `coords`' indices.
    """
    n = len(coords)
    if n <= 1:
        return list(range(n))
    visited = [False] * n
    tour = [0]
    visited[0] = True
    for _ in range(n - 1):
        last = tour[-1]
        nearest = min(
            (i for i in range(n) if not visited[i]),
            key=lambda i: _haversine_km(coords[last], coords[i]),
        )
        tour.append(nearest)
        visited[nearest] = True
    return tour


def two_opt(order: list[int], coords: list[Coordinate]) -> list[int]:
    """Standard 2-opt local search on top of a starting tour: repeatedly
    reverses whichever segment shortens the total distance, until no
    single reversal helps. O(n^2) per pass — fine for the stop counts a
    real route here ever has (a full CVRP solver is Horizon 2's job, not
    this one's)."""
    best = order
    improved = True
    while improved:
        improved = False
        for i in range(1, len(best) - 1):
            for j in range(i + 1, len(best)):
                candidate = best[:i] + best[i : j + 1][::-1] + best[j + 1 :]
                if _tour_length(candidate, coords) < _tour_length(best, coords):
                    best = candidate
                    improved = True
    return best


@dataclass(frozen=True, slots=True)
class OptimizedRouteSequence:
    route: Route
    ordered_stop_ids: list[uuid.UUID]
    km_before: float
    km_after: float

    @property
    def km_saved(self) -> float:
        return max(0.0, self.km_before - self.km_after)


@dataclass(frozen=True, slots=True)
class OptimizeRouteSequenceCommand(Command):
    tenant_id: uuid.UUID
    route_id: uuid.UUID


class OptimizeRouteSequenceUseCase:
    def __init__(
        self,
        route_repository: RouteRepository,
        order_repository: OrderRepository,
        prediction_repository: PredictionRepository,
        tenant_config_repository: TenantConfigurationRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._route_repository = route_repository
        self._order_repository = order_repository
        self._prediction_repository = prediction_repository
        self._tenant_config_repository = tenant_config_repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: OptimizeRouteSequenceCommand) -> OptimizedRouteSequence:
        config = await GetEffectiveTenantConfigurationUseCase(
            self._tenant_config_repository
        ).execute(
            GetEffectiveTenantConfigurationQuery(
                tenant_id=command.tenant_id, config_key="route_optimization_enabled"
            )
        )
        if config is None or not is_truthy_config_value(config.config_value):
            msg = "Route optimization is not enabled for this tenant."
            raise RouteOptimizationDisabledError(msg, tenant_id=str(command.tenant_id))

        route = await self._route_repository.get_by_id(command.route_id)
        if route is None:
            msg = f"No route visible with id {command.route_id}."
            raise NotFoundError(msg, route_id=str(command.route_id))

        pending_stops = sorted(
            (s for s in route.stops if s.status == "pending"), key=lambda s: s.sequence_number
        )

        located: list[tuple[uuid.UUID, Coordinate]] = []
        unlocated_ids: list[uuid.UUID] = []
        for stop in pending_stops:
            order = await self._order_repository.get_by_id(stop.order_id)
            address = order.delivery_address if order is not None else None
            if (
                order is not None
                and address is not None
                and address.latitude is not None
                and address.longitude is not None
            ):
                located.append((stop.id, (address.latitude, address.longitude)))
            else:
                unlocated_ids.append(stop.id)

        if len(located) < 2:
            # Nothing meaningful to reorder -- keep the current order.
            ordered_ids = [stop.id for stop in pending_stops]
            km_before = km_after = 0.0
        else:
            coords = [coordinate for _, coordinate in located]
            km_before = _tour_length(list(range(len(coords))), coords)
            optimized_indices = two_opt(nearest_neighbour(coords), coords)
            km_after = _tour_length(optimized_indices, coords)
            ordered_ids = [located[i][0] for i in optimized_indices] + unlocated_ids

        route.resequence_stops(ordered_ids)
        await self._route_repository.save(route)

        await RecordPredictionUseCase(self._prediction_repository).execute(
            RecordPredictionCommand(
                tenant_id=command.tenant_id,
                prediction_type=PREDICTION_TYPE,
                subject_type="route",
                subject_id=command.route_id,
                model_version=MODEL_VERSION,
                value={
                    "ordered_stop_ids": [str(stop_id) for stop_id in ordered_ids],
                    "km_before": km_before,
                    "km_after": km_after,
                    "km_saved": max(0.0, km_before - km_after),
                },
            )
        )
        await self._unit_of_work.commit()

        return OptimizedRouteSequence(
            route=route,
            ordered_stop_ids=ordered_ids,
            km_before=km_before,
            km_after=km_after,
        )
