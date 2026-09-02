"""Route aggregate root.

Lifecycle:  planned → loaded → in_progress → completed → reconciled

A Route represents a shift/trip for a Driver and Vehicle to deliver a set of
Orders (represented as RouteStops).

docs/data/01-domain-model.md §4.4
docs/data/08-state-machines.md §3, §4
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from lpg.domain.common.base import AggregateRoot, DomainEvent, InvariantViolation

if TYPE_CHECKING:
    from collections.abc import Sequence

# ---------------------------------------------------------------------------
# Domain Events
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RoutePlanned(DomainEvent):
    route_id: uuid.UUID
    tenant_id: uuid.UUID
    branch_id: uuid.UUID
    driver_id: uuid.UUID
    vehicle_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class OrderAssignedToRoute(DomainEvent):
    route_id: uuid.UUID
    stop_id: uuid.UUID
    order_id: uuid.UUID
    tenant_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class RouteStatusChanged(DomainEvent):
    route_id: uuid.UUID
    old_status: str
    new_status: str
    # Carried so thin notification/realtime handlers can resolve the driver
    # without a DB lookup (e.g. the `route_ready` push on `-> loaded`).
    tenant_id: uuid.UUID
    driver_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class OrderDelivered(DomainEvent):
    route_id: uuid.UUID
    stop_id: uuid.UUID
    order_id: uuid.UUID
    tenant_id: uuid.UUID
    delivered_at: datetime


@dataclass(frozen=True, slots=True)
class OrderDeliveryFailed(DomainEvent):
    route_id: uuid.UUID
    stop_id: uuid.UUID
    order_id: uuid.UUID
    tenant_id: uuid.UUID
    reason_code: str
    failed_at: datetime


@dataclass(frozen=True, slots=True)
class VehicleLoaded(DomainEvent):
    route_id: uuid.UUID
    vehicle_id: uuid.UUID
    tenant_id: uuid.UUID
    branch_id: uuid.UUID


# ---------------------------------------------------------------------------
# Value Objects and Constants
# ---------------------------------------------------------------------------

_ROUTE_TRANSITIONS: dict[str, set[str]] = {
    "planned": {"loaded", "cancelled"},
    "loaded": {"in_progress", "cancelled"},
    "in_progress": {"completed"},
    "completed": {"reconciled"},
    "reconciled": set(),
    "cancelled": set(),
}

ROUTE_STATUSES: frozenset[str] = frozenset(_ROUTE_TRANSITIONS)

_STOP_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"en_route", "delivered", "failed", "cancelled"},
    "en_route": {"delivered", "failed", "cancelled"},
    "delivered": set(),
    # "failed" is otherwise terminal, but D-12's reschedule flow
    # (`Order.reschedule()`, `failed_delivery -> ready_for_dispatch`)
    # legitimately re-attempts the same stop — `Route.reschedule_stop()`
    # is the only caller of this one edge.
    "failed": {"pending"},
    "cancelled": set(),
}

STOP_STATUSES: frozenset[str] = frozenset(_STOP_TRANSITIONS)


@dataclass(frozen=True, slots=True)
class ProofOfDelivery:
    otp_verified: bool
    signature_url: str | None = None
    photo_url: str | None = None
    gps_lat: float | None = None
    gps_lon: float | None = None


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------


class RouteStop:
    """A stop on a route to deliver an order."""

    __slots__ = (
        "failure_reason",
        "id",
        "order_id",
        "proof_of_delivery",
        "route_id",
        "sequence_number",
        "status",
    )

    def __init__(
        self,
        *,
        stop_id: uuid.UUID,
        route_id: uuid.UUID,
        order_id: uuid.UUID,
        sequence_number: int,
        status: str = "pending",
        proof_of_delivery: ProofOfDelivery | None = None,
        failure_reason: str | None = None,
    ) -> None:
        self.id = stop_id
        self.route_id = route_id
        self.order_id = order_id
        self.sequence_number = sequence_number
        self.status = status
        self.proof_of_delivery = proof_of_delivery
        self.failure_reason = failure_reason

    def change_status(self, new_status: str) -> str:
        """Change status, returns the old status."""
        if new_status not in STOP_STATUSES:
            msg = f"Unknown stop status: '{new_status}'."
            raise InvariantViolation(msg)
        allowed = _STOP_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            msg = f"Stop status transition from '{self.status}' to '{new_status}' is not permitted."
            raise InvariantViolation(msg)
        old_status = self.status
        self.status = new_status
        return old_status


# ---------------------------------------------------------------------------
# Aggregate root
# ---------------------------------------------------------------------------


class Route(AggregateRoot):
    """Route aggregate root."""

    __slots__ = (
        "_branch_id",
        "_date",
        "_driver_id",
        "_status",
        "_stops",
        "_tenant_id",
        "_vehicle_id",
    )

    def __init__(
        self,
        *,
        route_id: uuid.UUID,
        tenant_id: uuid.UUID,
        branch_id: uuid.UUID,
        driver_id: uuid.UUID,
        vehicle_id: uuid.UUID,
        route_date: datetime | None = None,
        status: str = "planned",
        stops: list[RouteStop] | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(route_id, version=version)
        self._tenant_id = tenant_id
        self._branch_id = branch_id
        self._driver_id = driver_id
        self._vehicle_id = vehicle_id
        self._date = route_date or datetime.now(UTC)
        self._status = status
        self._stops: list[RouteStop] = stops or []

    def record_planned(self) -> None:
        """Emits `RoutePlanned` — called explicitly by whichever use case
        just constructed a genuinely new `Route` (`PlanRouteUseCase`, and
        `AssignOrderUseCase`'s find-or-create path). Deliberately **not**
        auto-fired from `__init__` (unlike an earlier version of this
        class): `__init__` also runs every time the repository reconstructs
        an *existing* route from a database row, and a status/stops-based
        heuristic there can't tell "just created" apart from "loaded, still
        happens to be planned and empty" — the same trap `Order`'s own
        constructor deliberately avoids by never recording events itself,
        leaving that to explicit methods like `submit()`.
        """
        self.record_event(
            RoutePlanned(
                route_id=self.id,
                tenant_id=self.tenant_id,
                branch_id=self.branch_id,
                driver_id=self.driver_id,
                vehicle_id=self.vehicle_id,
            )
        )

    @property
    def tenant_id(self) -> uuid.UUID:
        return self._tenant_id

    @property
    def branch_id(self) -> uuid.UUID:
        return self._branch_id

    @property
    def driver_id(self) -> uuid.UUID:
        return self._driver_id

    @property
    def vehicle_id(self) -> uuid.UUID:
        return self._vehicle_id

    @property
    def status(self) -> str:
        return self._status

    @property
    def date(self) -> datetime:
        return self._date

    @property
    def stops(self) -> Sequence[RouteStop]:
        return tuple(self._stops)

    def change_status(self, new_status: str) -> None:
        """Transition the route to a new status."""
        if new_status not in ROUTE_STATUSES:
            msg = f"Unknown route status: '{new_status}'."
            raise InvariantViolation(msg)
        allowed = _ROUTE_TRANSITIONS.get(self._status, set())
        if new_status not in allowed:
            msg = (
                f"Route status transition from '{self._status}' to '{new_status}' is not permitted."
            )
            raise InvariantViolation(msg)

        if new_status == "completed":
            if not self._stops:
                msg = "Cannot complete route: it has no stops."
                raise InvariantViolation(msg)
            # Can only complete if all stops are in a terminal state
            terminal_states = {"delivered", "failed", "cancelled"}
            if any(stop.status not in terminal_states for stop in self._stops):
                msg = "Cannot complete route: not all stops are in a terminal state."
                raise InvariantViolation(msg)

        old_status = self._status
        self._status = new_status
        self.record_event(
            RouteStatusChanged(
                route_id=self.id,
                old_status=old_status,
                new_status=new_status,
                tenant_id=self._tenant_id,
                driver_id=self._driver_id,
            )
        )

        if new_status == "loaded":
            self.record_event(
                VehicleLoaded(
                    route_id=self.id,
                    vehicle_id=self.vehicle_id,
                    tenant_id=self.tenant_id,
                    branch_id=self.branch_id,
                )
            )

    def assign_order(self, order_id: uuid.UUID) -> None:
        """Assign an order to this route."""
        if self._status not in ("planned", "loaded"):
            msg = f"Cannot assign order to route in status '{self._status}'."
            raise InvariantViolation(msg)

        if any(stop.order_id == order_id for stop in self._stops):
            msg = f"Order {order_id} is already assigned to this route."
            raise InvariantViolation(msg)

        stop_id = uuid.uuid4()
        sequence_number = len(self._stops) + 1
        stop = RouteStop(
            stop_id=stop_id,
            route_id=self.id,
            order_id=order_id,
            sequence_number=sequence_number,
        )
        self._stops.append(stop)

        self.record_event(
            OrderAssignedToRoute(
                route_id=self.id,
                stop_id=stop_id,
                order_id=order_id,
                tenant_id=self.tenant_id,
            )
        )

    def cancel_stop(self, stop_id: uuid.UUID) -> None:
        """Marks one stop cancelled — called when the underlying `Order` is
        cancelled (any order status, so unlike `record_proof_of_delivery`/
        `record_failed_delivery` this does **not** require the route itself
        to be `in_progress`). Without this, a cancelled order's stop would
        stay non-terminal forever, and `change_status("completed")`'s
        all-stops-terminal check would permanently block the whole route.
        """
        stop = next((s for s in self._stops if s.id == stop_id), None)
        if not stop:
            msg = f"Stop {stop_id} not found on route {self.id}."
            raise InvariantViolation(msg)
        stop.change_status("cancelled")
        self._auto_complete_if_all_stops_terminal()

    def reschedule_stop(self, stop_id: uuid.UUID) -> None:
        """Resets a previously-`failed` stop back to `pending` so it can be
        reattempted — called by `RescheduleOrderUseCase` in lockstep with
        `Order.reschedule()` (`failed_delivery -> ready_for_dispatch`, D-12).
        Only legal from `failed` (see `_STOP_TRANSITIONS`); a stop that
        never failed has nothing to reschedule, and `Order.reschedule()`
        itself only fires from `failed_delivery` so this is never called
        otherwise.

        If this stop's earlier failure was the one that auto-completed the
        route (`_auto_complete_if_all_stops_terminal()` — every other stop
        was already terminal), the route is reopened to `in_progress`:
        otherwise `record_proof_of_delivery()`'s own "must be in_progress"
        guard would permanently block the retry this method exists to
        enable. Reopens directly rather than through `change_status()`'s
        validated `_ROUTE_TRANSITIONS` (which deliberately has no general
        `completed -> in_progress` edge — see its own docstring), but still
        records the same `RouteStatusChanged` event `change_status()` would,
        so consumers see a consistent history.
        """
        stop = next((s for s in self._stops if s.id == stop_id), None)
        if not stop:
            msg = f"Stop {stop_id} not found on route {self.id}."
            raise InvariantViolation(msg)
        stop.change_status("pending")
        if self._status == "completed":
            old_status = self._status
            self._status = "in_progress"
            self.record_event(
                RouteStatusChanged(
                    route_id=self.id,
                    old_status=old_status,
                    new_status="in_progress",
                    tenant_id=self._tenant_id,
                    driver_id=self._driver_id,
                )
            )

    def record_proof_of_delivery(self, stop_id: uuid.UUID, pod: ProofOfDelivery) -> None:
        """Record proof of delivery for a specific stop."""
        if self._status != "in_progress":
            msg = f"Cannot record POD: route is in status '{self._status}'."
            raise InvariantViolation(msg)

        stop = next((s for s in self._stops if s.id == stop_id), None)
        if not stop:
            msg = f"Stop {stop_id} not found on route {self.id}."
            raise InvariantViolation(msg)

        stop.change_status("delivered")
        stop.proof_of_delivery = pod

        self.record_event(
            OrderDelivered(
                route_id=self.id,
                stop_id=stop_id,
                order_id=stop.order_id,
                tenant_id=self.tenant_id,
                delivered_at=datetime.now(UTC),
            )
        )
        self._auto_complete_if_all_stops_terminal()

    def record_failed_delivery(self, stop_id: uuid.UUID, reason_code: str) -> None:
        """Record a failed delivery for a specific stop."""
        if self._status != "in_progress":
            msg = f"Cannot fail delivery: route is in status '{self._status}'."
            raise InvariantViolation(msg)

        stop = next((s for s in self._stops if s.id == stop_id), None)
        if not stop:
            msg = f"Stop {stop_id} not found on route {self.id}."
            raise InvariantViolation(msg)

        stop.change_status("failed")
        stop.failure_reason = reason_code

        self.record_event(
            OrderDeliveryFailed(
                route_id=self.id,
                stop_id=stop_id,
                order_id=stop.order_id,
                tenant_id=self.tenant_id,
                reason_code=reason_code,
                failed_at=datetime.now(UTC),
            )
        )
        self._auto_complete_if_all_stops_terminal()

    def _auto_complete_if_all_stops_terminal(self) -> None:
        """`in_progress -> completed` fires automatically once every stop
        has resolved (`docs/data/08-state-machines.md` §3: "all stops
        resolved") — there is no separate "complete this route" endpoint;
        `record_proof_of_delivery()`/`record_failed_delivery()`/
        `cancel_stop()` are the only three ways a stop becomes terminal, so
        each calls this after doing so. Reuses `change_status()` itself
        (rather than duplicating its empty-route/all-terminal guard and
        event recording) — safe to call speculatively since `change_status()`
        is a no-op-safe check here: this method only calls it once its own
        stricter condition (all stops terminal) already holds, matching
        `change_status()`'s own guard exactly.
        """
        if self._status != "in_progress":
            return
        terminal_states = {"delivered", "failed", "cancelled"}
        if self._stops and all(stop.status in terminal_states for stop in self._stops):
            self.change_status("completed")
