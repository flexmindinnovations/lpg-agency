"""Unit tests for the Route aggregate root (and its owned `RouteStop` entity).

Validates every `_ROUTE_TRANSITIONS`/`_STOP_TRANSITIONS` edge, the
empty-route and not-all-stops-terminal guards on `change_status("completed")`,
`cancel_stop()` (including the "a cancelled stop no longer blocks
'completed'" case — a real bug fixed this phase), `record_planned()` only
firing when explicitly called rather than on every reconstruction (also a
real bug fixed this phase), and `record_proof_of_delivery()`/
`record_failed_delivery()` requiring `in_progress` — all without touching
the database.
"""

from __future__ import annotations

import uuid

import pytest

from lpg.domain.common.base import InvariantViolation
from lpg.domain.delivery.route import (
    OrderAssignedToRoute,
    OrderDelivered,
    OrderDeliveryFailed,
    ProofOfDelivery,
    Route,
    RoutePlanned,
    RouteStatusChanged,
    RouteStop,
    VehicleLoaded,
)


def _make_route(**kwargs: object) -> Route:
    defaults: dict[str, object] = {
        "route_id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "branch_id": uuid.uuid4(),
        "driver_id": uuid.uuid4(),
        "vehicle_id": uuid.uuid4(),
    }
    defaults.update(kwargs)
    return Route(**defaults)  # type: ignore[arg-type]


def _route_with_stop(status: str = "planned") -> tuple[Route, uuid.UUID]:
    """A route with one assigned order/stop — the minimum fixture needed to
    exercise `change_status("completed")`'s all-stops-terminal guard and the
    POD/failed-delivery methods.
    """
    route = _make_route(status=status)
    order_id = uuid.uuid4()
    # `assign_order()` only allows "planned"/"loaded" — force through those
    # first if the caller wants a stop on a route already further along.
    if status in ("planned", "loaded"):
        route.assign_order(order_id)
    else:
        temp = _make_route(status="planned")
        temp.assign_order(order_id)
        stop = temp.stops[0]
        route = _make_route(status=status, stops=[stop])
    stop_id = route.stops[0].id
    return route, stop_id


class TestRouteConstruction:
    def test_creates_in_planned_status_with_no_stops(self) -> None:
        route = _make_route()
        assert route.status == "planned"
        assert route.stops == ()

    def test_construction_does_not_auto_record_planned_event(self) -> None:
        """Regression test: an earlier version of this class fired
        `RoutePlanned` from `__init__`, which also runs every time the
        repository reconstructs an *existing* route from a database row —
        indistinguishable from "genuinely just created." `record_planned()`
        must be called explicitly instead.
        """
        route = _make_route()
        assert route.events == ()


class TestRecordPlanned:
    def test_emits_route_planned_event_with_correct_payload(self) -> None:
        route = _make_route()
        route.record_planned()

        events = [e for e in route.events if isinstance(e, RoutePlanned)]
        assert len(events) == 1
        assert events[0].route_id == route.id
        assert events[0].tenant_id == route.tenant_id
        assert events[0].branch_id == route.branch_id
        assert events[0].driver_id == route.driver_id
        assert events[0].vehicle_id == route.vehicle_id

    def test_reconstructing_an_existing_route_does_not_auto_fire_it(self) -> None:
        """Repository reconstruction of a persisted route (status not
        "just planned," may already have stops) must never emit
        `RoutePlanned` on its own — only an explicit `record_planned()`
        call does. Constructing with a non-default status/stops simulates
        that reconstruction path.
        """
        stop_source = _make_route(status="planned")
        stop_source.assign_order(uuid.uuid4())
        reconstructed = _make_route(status="loaded", stops=list(stop_source.stops))
        assert reconstructed.events == ()


class TestRouteStatusTransitions:
    @pytest.mark.parametrize(
        ("from_status", "to_status"),
        [
            ("planned", "loaded"),
            ("planned", "cancelled"),
            ("loaded", "in_progress"),
            ("loaded", "cancelled"),
        ],
    )
    def test_valid_transition_without_stops(self, from_status: str, to_status: str) -> None:
        route = _make_route(status=from_status)
        route.change_status(to_status)
        assert route.status == to_status

    def test_records_route_status_changed_event(self) -> None:
        route = _make_route(status="planned")
        route.change_status("loaded")
        events = [e for e in route.events if isinstance(e, RouteStatusChanged)]
        assert len(events) == 1
        assert events[0].old_status == "planned"
        assert events[0].new_status == "loaded"

    def test_loaded_also_records_vehicle_loaded_event(self) -> None:
        route = _make_route(status="planned")
        route.change_status("loaded")
        events = [e for e in route.events if isinstance(e, VehicleLoaded)]
        assert len(events) == 1
        assert events[0].vehicle_id == route.vehicle_id

    def test_non_loaded_transition_does_not_record_vehicle_loaded(self) -> None:
        route = _make_route(status="loaded")
        route.change_status("in_progress")
        events = [e for e in route.events if isinstance(e, VehicleLoaded)]
        assert events == []

    def test_rejects_unknown_status(self) -> None:
        route = _make_route(status="planned")
        with pytest.raises(InvariantViolation, match="Unknown route status"):
            route.change_status("teleported")

    @pytest.mark.parametrize(
        ("from_status", "to_status"),
        [
            ("planned", "in_progress"),
            ("planned", "completed"),
            ("planned", "reconciled"),
            ("loaded", "completed"),
            ("in_progress", "loaded"),
            ("in_progress", "cancelled"),
            ("completed", "in_progress"),
            ("completed", "cancelled"),
            ("reconciled", "completed"),
            ("cancelled", "planned"),
        ],
    )
    def test_illegal_transition_is_rejected(self, from_status: str, to_status: str) -> None:
        route = _make_route(status=from_status)
        with pytest.raises(InvariantViolation, match="not permitted"):
            route.change_status(to_status)

    def test_reconciled_and_cancelled_are_terminal(self) -> None:
        reconciled = _make_route(status="reconciled")
        with pytest.raises(InvariantViolation):
            reconciled.change_status("planned")
        cancelled = _make_route(status="cancelled")
        with pytest.raises(InvariantViolation):
            cancelled.change_status("planned")


class TestCompleteRequiresNonEmptyTerminalStops:
    """Direct `change_status("completed")` calls — the guard these exercise
    also backs `_auto_complete_if_all_stops_terminal()` (see
    `TestAutoCompleteOnLastStopResolved` below), which is how a route
    actually reaches `completed` in practice; nothing calls this directly.
    """

    def test_empty_route_cannot_complete(self) -> None:
        route = _make_route(status="in_progress")
        with pytest.raises(InvariantViolation, match="no stops"):
            route.change_status("completed")

    def test_non_terminal_stop_blocks_completion(self) -> None:
        route, _stop_id = _route_with_stop(status="in_progress")
        with pytest.raises(InvariantViolation, match="not all stops are in a terminal state"):
            route.change_status("completed")

    def test_manual_completion_succeeds_when_reconstructed_with_terminal_stops(self) -> None:
        """A route reconstructed from the database (e.g. by the repository)
        with stops that are already terminal — as opposed to one that just
        transitioned a stop in memory, which auto-completes instead (see
        below) — can still be completed directly.
        """
        stop = RouteStop(
            stop_id=uuid.uuid4(),
            route_id=uuid.uuid4(),
            order_id=uuid.uuid4(),
            sequence_number=1,
            status="delivered",
        )
        route = _make_route(status="in_progress", stops=[stop])
        route.change_status("completed")
        assert route.status == "completed"


class TestAutoCompleteOnLastStopResolved:
    """`in_progress -> completed` fires automatically once every stop has
    resolved (`docs/data/08-state-machines.md` §3) — there is no separate
    "complete this route" endpoint or use case; `record_proof_of_delivery()`/
    `record_failed_delivery()`/`cancel_stop()` are the only three ways a
    stop becomes terminal, and each triggers this check itself. Regression
    coverage: before this fix, nothing ever transitioned a route out of
    `in_progress`, making `POST /routes/{id}/reconcile` (which requires
    `completed`) permanently unreachable.
    """

    def test_delivering_the_only_stop_auto_completes(self) -> None:
        route, stop_id = _route_with_stop(status="in_progress")
        route.record_proof_of_delivery(stop_id, ProofOfDelivery(otp_verified=True))
        assert route.status == "completed"

    def test_failing_the_only_stop_auto_completes(self) -> None:
        route, stop_id = _route_with_stop(status="in_progress")
        route.record_failed_delivery(stop_id, "customer_unavailable")
        assert route.status == "completed"

    def test_cancelling_the_only_stop_auto_completes(self) -> None:
        """Regression test: `cancel_stop()` used to leave a cancelled stop
        indistinguishable from a still-pending one for the completion
        check, which permanently blocked the whole route from ever
        completing once one order on it was cancelled. `cancelled` must
        count as terminal, and resolving the last stop this way must
        auto-complete just like the other two paths.
        """
        route, stop_id = _route_with_stop(status="in_progress")
        route.cancel_stop(stop_id)
        assert route.status == "completed"

    def test_records_route_status_changed_event_on_auto_complete(self) -> None:
        route, stop_id = _route_with_stop(status="in_progress")
        route.record_proof_of_delivery(stop_id, ProofOfDelivery(otp_verified=True))
        events = [e for e in route.events if isinstance(e, RouteStatusChanged)]
        assert events[-1].old_status == "in_progress"
        assert events[-1].new_status == "completed"

    def test_does_not_complete_while_any_stop_remains_non_terminal(self) -> None:
        route = _make_route(status="planned")
        stop_a, stop_b = uuid.uuid4(), uuid.uuid4()
        route.assign_order(stop_a)
        route.assign_order(stop_b)
        first_stop_id = route.stops[0].id
        route.change_status("loaded")
        route.change_status("in_progress")

        route.record_proof_of_delivery(first_stop_id, ProofOfDelivery(otp_verified=True))

        assert route.status == "in_progress"

    def test_mix_of_terminal_states_auto_completes_on_the_last_one(self) -> None:
        route = _make_route(status="planned")
        order_a, order_b, order_c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        route.assign_order(order_a)
        route.assign_order(order_b)
        route.assign_order(order_c)
        stop_a, stop_b, stop_c = (s.id for s in route.stops)
        route.change_status("loaded")
        route.change_status("in_progress")

        route.record_proof_of_delivery(stop_a, ProofOfDelivery(otp_verified=True))
        assert route.status == "in_progress"
        route.record_failed_delivery(stop_b, "wrong_address")
        assert route.status == "in_progress"
        route.cancel_stop(stop_c)

        assert route.status == "completed"

    def test_cancel_stop_outside_in_progress_does_not_auto_complete(self) -> None:
        """`cancel_stop()` works in any route status (D-19 free cancellation
        happens before dispatch); the auto-complete check must stay a no-op
        outside `in_progress` rather than trying to jump straight there.
        """
        route = _make_route(status="planned")
        route.assign_order(uuid.uuid4())
        stop_id = route.stops[0].id

        route.cancel_stop(stop_id)

        assert route.status == "planned"


class TestAssignOrder:
    def test_assigns_first_stop_with_sequence_one(self) -> None:
        route = _make_route(status="planned")
        order_id = uuid.uuid4()
        route.assign_order(order_id)

        assert len(route.stops) == 1
        stop = route.stops[0]
        assert stop.order_id == order_id
        assert stop.sequence_number == 1
        assert stop.status == "pending"

    def test_second_order_gets_sequence_two(self) -> None:
        route = _make_route(status="planned")
        route.assign_order(uuid.uuid4())
        route.assign_order(uuid.uuid4())
        assert [s.sequence_number for s in route.stops] == [1, 2]

    def test_records_order_assigned_to_route_event(self) -> None:
        route = _make_route(status="planned")
        order_id = uuid.uuid4()
        route.assign_order(order_id)

        events = [e for e in route.events if isinstance(e, OrderAssignedToRoute)]
        assert len(events) == 1
        assert events[0].order_id == order_id
        assert events[0].route_id == route.id

    def test_rejects_duplicate_order_on_same_route(self) -> None:
        route = _make_route(status="planned")
        order_id = uuid.uuid4()
        route.assign_order(order_id)
        with pytest.raises(InvariantViolation, match="already assigned"):
            route.assign_order(order_id)

    @pytest.mark.parametrize("status", ["in_progress", "completed", "reconciled", "cancelled"])
    def test_rejects_assignment_outside_planned_or_loaded(self, status: str) -> None:
        route = _make_route(status=status)
        with pytest.raises(InvariantViolation, match="Cannot assign order"):
            route.assign_order(uuid.uuid4())

    def test_allows_assignment_while_loaded(self) -> None:
        route = _make_route(status="loaded")
        route.assign_order(uuid.uuid4())
        assert len(route.stops) == 1


class TestCancelStop:
    def test_cancels_a_pending_stop(self) -> None:
        route = _make_route(status="planned")
        route.assign_order(uuid.uuid4())
        stop_id = route.stops[0].id

        route.cancel_stop(stop_id)

        assert route.stops[0].status == "cancelled"

    def test_works_regardless_of_route_status(self) -> None:
        """Unlike `record_proof_of_delivery`/`record_failed_delivery`, a
        stop can be cancelled with the route in *any* status — an order can
        be cancelled before the driver ever departs.
        """
        route = _make_route(status="planned")
        route.assign_order(uuid.uuid4())
        stop_id = route.stops[0].id
        route.cancel_stop(stop_id)
        assert route.stops[0].status == "cancelled"

    def test_raises_for_unknown_stop(self) -> None:
        route = _make_route(status="planned")
        with pytest.raises(InvariantViolation, match="not found"):
            route.cancel_stop(uuid.uuid4())

    def test_cannot_cancel_an_already_delivered_stop(self) -> None:
        route, stop_id = _route_with_stop(status="in_progress")
        route.record_proof_of_delivery(stop_id, ProofOfDelivery(otp_verified=True))
        with pytest.raises(InvariantViolation, match="not permitted"):
            route.cancel_stop(stop_id)


class TestRescheduleStop:
    """Regression coverage for the D-12 retry gap: `failed` used to be
    fully terminal, so a rescheduled order's stop could never reach
    `delivered` again on the next attempt — `POST /orders/{id}/deliver`
    would 409 out of `Route.record_proof_of_delivery()`'s own transition
    guard even though the Order itself had legitimately gone back through
    `failed_delivery -> ready_for_dispatch -> out_for_delivery`.
    """

    def test_resets_a_failed_stop_back_to_pending(self) -> None:
        route, stop_id = _route_with_stop(status="in_progress")
        route.record_failed_delivery(stop_id, "customer_unavailable")

        route.reschedule_stop(stop_id)

        assert route.stops[0].status == "pending"

    def test_reopens_a_route_that_auto_completed_on_this_stops_failure(self) -> None:
        """This stop was the last one unresolved, so `record_failed_delivery()`
        auto-completed the route (`TestAutoCompleteOnLastStopResolved`).
        Rescheduling it must reopen the route — otherwise the retry's later
        `record_proof_of_delivery()` call would 409 out of "must be
        in_progress" even though the Order itself is legitimately back in
        the dispatch pipeline.
        """
        route, stop_id = _route_with_stop(status="in_progress")
        route.record_failed_delivery(stop_id, "customer_unavailable")
        assert route.status == "completed"

        route.reschedule_stop(stop_id)

        assert route.status == "in_progress"

    def test_does_not_reopen_a_route_still_in_progress(self) -> None:
        """A multi-stop route where another stop is still unresolved never
        auto-completed in the first place — rescheduling this one must
        leave its status untouched, not force it anywhere.
        """
        route = _make_route(status="planned")
        route.assign_order(uuid.uuid4())
        route.assign_order(uuid.uuid4())
        stop_a, stop_b = (s.id for s in route.stops)
        route.change_status("loaded")
        route.change_status("in_progress")
        route.record_failed_delivery(stop_a, "customer_unavailable")
        assert route.status == "in_progress"

        route.reschedule_stop(stop_a)

        assert route.status == "in_progress"
        assert route.stops[1].id == stop_b  # untouched

    def test_rescheduled_stop_can_reach_delivered_on_retry(self) -> None:
        route, stop_id = _route_with_stop(status="in_progress")
        route.record_failed_delivery(stop_id, "customer_unavailable")
        route.reschedule_stop(stop_id)

        route.record_proof_of_delivery(stop_id, ProofOfDelivery(otp_verified=True))

        assert route.stops[0].status == "delivered"
        assert route.status == "completed"

    def test_rejects_rescheduling_a_stop_that_never_failed(self) -> None:
        route = _make_route(status="planned")
        route.assign_order(uuid.uuid4())
        stop_id = route.stops[0].id
        with pytest.raises(InvariantViolation, match="not permitted"):
            route.reschedule_stop(stop_id)

    def test_raises_for_unknown_stop(self) -> None:
        route = _make_route(status="in_progress")
        with pytest.raises(InvariantViolation, match="not found"):
            route.reschedule_stop(uuid.uuid4())


class TestRecordProofOfDelivery:
    def test_records_pod_and_marks_stop_delivered(self) -> None:
        route, stop_id = _route_with_stop(status="in_progress")
        pod = ProofOfDelivery(
            otp_verified=True,
            signature_url="sig.png",
            photo_url="photo.png",
            gps_lat=12.9,
            gps_lon=77.6,
        )

        route.record_proof_of_delivery(stop_id, pod)

        stop = route.stops[0]
        assert stop.status == "delivered"
        assert stop.proof_of_delivery == pod

    def test_records_order_delivered_event(self) -> None:
        route, stop_id = _route_with_stop(status="in_progress")
        order_id = route.stops[0].order_id

        route.record_proof_of_delivery(stop_id, ProofOfDelivery(otp_verified=True))

        events = [e for e in route.events if isinstance(e, OrderDelivered)]
        assert len(events) == 1
        assert events[0].stop_id == stop_id
        assert events[0].order_id == order_id

    @pytest.mark.parametrize(
        "status", ["planned", "loaded", "completed", "reconciled", "cancelled"]
    )
    def test_rejects_when_route_not_in_progress(self, status: str) -> None:
        route, stop_id = _route_with_stop(status=status)
        with pytest.raises(InvariantViolation, match="in status"):
            route.record_proof_of_delivery(stop_id, ProofOfDelivery(otp_verified=True))

    def test_raises_for_unknown_stop(self) -> None:
        route = _make_route(status="in_progress")
        with pytest.raises(InvariantViolation, match="not found"):
            route.record_proof_of_delivery(uuid.uuid4(), ProofOfDelivery(otp_verified=True))


class TestRecordFailedDelivery:
    def test_marks_stop_failed_with_reason(self) -> None:
        route, stop_id = _route_with_stop(status="in_progress")
        route.record_failed_delivery(stop_id, "customer_unavailable")

        stop = route.stops[0]
        assert stop.status == "failed"
        assert stop.failure_reason == "customer_unavailable"

    def test_records_order_delivery_failed_event(self) -> None:
        route, stop_id = _route_with_stop(status="in_progress")
        route.record_failed_delivery(stop_id, "wrong_address")

        events = [e for e in route.events if isinstance(e, OrderDeliveryFailed)]
        assert len(events) == 1
        assert events[0].stop_id == stop_id
        assert events[0].reason_code == "wrong_address"

    @pytest.mark.parametrize(
        "status", ["planned", "loaded", "completed", "reconciled", "cancelled"]
    )
    def test_rejects_when_route_not_in_progress(self, status: str) -> None:
        route, stop_id = _route_with_stop(status=status)
        with pytest.raises(InvariantViolation, match="in status"):
            route.record_failed_delivery(stop_id, "vehicle_issue")

    def test_raises_for_unknown_stop(self) -> None:
        route = _make_route(status="in_progress")
        with pytest.raises(InvariantViolation, match="not found"):
            route.record_failed_delivery(uuid.uuid4(), "vehicle_issue")


class TestRouteStopStatusTransitions:
    """`RouteStop.change_status()` — exercised indirectly above via
    `Route`'s own methods for the reachable edges; this covers the raw
    entity-level transition table directly, including the illegal ones.
    """

    @pytest.mark.parametrize(
        ("from_status", "to_status"),
        [
            ("pending", "en_route"),
            ("pending", "delivered"),
            ("pending", "failed"),
            ("pending", "cancelled"),
            ("en_route", "delivered"),
            ("en_route", "failed"),
            ("en_route", "cancelled"),
            ("failed", "pending"),
        ],
    )
    def test_valid_transition(self, from_status: str, to_status: str) -> None:
        stop = RouteStop(
            stop_id=uuid.uuid4(),
            route_id=uuid.uuid4(),
            order_id=uuid.uuid4(),
            sequence_number=1,
            status=from_status,
        )
        old = stop.change_status(to_status)
        assert old == from_status
        assert stop.status == to_status

    @pytest.mark.parametrize("terminal_status", ["delivered", "failed", "cancelled"])
    def test_terminal_statuses_reject_any_further_transition(self, terminal_status: str) -> None:
        stop = RouteStop(
            stop_id=uuid.uuid4(),
            route_id=uuid.uuid4(),
            order_id=uuid.uuid4(),
            sequence_number=1,
            status=terminal_status,
        )
        with pytest.raises(InvariantViolation, match="not permitted"):
            stop.change_status("en_route")

    def test_rejects_unknown_status(self) -> None:
        stop = RouteStop(
            stop_id=uuid.uuid4(), route_id=uuid.uuid4(), order_id=uuid.uuid4(), sequence_number=1
        )
        with pytest.raises(InvariantViolation, match="Unknown stop status"):
            stop.change_status("teleported")
