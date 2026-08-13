"""Application use cases for the order bounded context.

One class per endpoint (`api/v1/routers/order.py`), following the
established pattern: delegate all business invariant checks to the
aggregate, persist via the repository, commit via the Unit of Work, which
dispatches domain events after commit.

**The atomic multi-aggregate pattern** (`AssignOrderUseCase`,
`DeliverOrderUseCase`, `ApproveOrderCancellationUseCase`, the free-cancel
path of `CancelOrderUseCase`) is an exact copy of
`application/inventory/use_cases.py::LoadTransferUseCase`'s proven shape:
load every aggregate involved into memory first, mutate every aggregate in
memory, and only once every mutation has succeeded call `.save()` on each
touched repository, then `unit_of_work.commit()` exactly once. If any
mutation raises partway through, nothing has been saved yet and nothing
needs to be undone.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from lpg.application.common.cqrs import Command, Query
from lpg.application.common.errors import NotFoundError, OtpMismatchError
from lpg.application.delivery.use_cases import AssignOrderToRouteCommand, AssignOrderToRouteUseCase
from lpg.application.inventory.use_cases import GetOrCreateInventoryLocationUseCase
from lpg.domain.delivery.route import ProofOfDelivery as RouteProofOfDelivery
from lpg.domain.delivery.route import Route
from lpg.domain.order.cancellation_fee import CancellationFeeCalculator
from lpg.domain.order.order import DeliveredLine, DeliveryAddress, Order, OrderLine
from lpg.domain.tenant.price_list import EffectivePriceResolver
from lpg.domain.tenant.tenant_configuration import TenantConfigurationResolver

if TYPE_CHECKING:
    import uuid
    from collections.abc import Callable, Sequence
    from contextlib import AbstractAsyncContextManager

    from lpg.application.common.ports import JobQueuePort, UnitOfWork
    from lpg.application.customer.ports import CustomerRepository
    from lpg.application.delivery.ports import RouteRepository
    from lpg.application.identity.ports import OtpDeliveryPort, OtpStore
    from lpg.application.inventory.ports import InventoryLocationRepository
    from lpg.application.order.ports import (
        CancellationRecordRepository,
        CreditLimitEvaluator,
        CylinderCapPolicy,
        OrderRepository,
        OrderStatusHistoryEntry,
        ProofOfDeliveryEntry,
        ProofOfDeliveryRepository,
    )
    from lpg.application.tenant.ports import PriceListRepository, TenantConfigurationRepository


_CANCELLATION_FEE_CONFIG_KEY = "cancellation_fee_amount"


def order_delivery_otp_key(tenant_id: uuid.UUID, order_id: uuid.UUID) -> str:
    """Distinct from the login-OTP key (`otp_request.py::otp_store_key`,
    keyed by phone number) — a customer can have a delivery OTP pending for
    one order and a login OTP pending at the same time without either
    invalidating the other.
    """
    return f"tenant:{tenant_id}:order-delivery-otp:{order_id}"


# ==========================================================================
# Create / Confirm
# ==========================================================================


@dataclass(frozen=True, slots=True)
class CreateOrderLine:
    cylinder_type_id: uuid.UUID
    quantity: int


@dataclass(frozen=True, slots=True)
class CreateOrderCommand(Command):
    tenant_id: uuid.UUID
    branch_id: uuid.UUID
    customer_id: uuid.UUID
    address_id: uuid.UUID
    delivery_address: DeliveryAddress
    booking_source: str
    requested_date: datetime
    lines: Sequence[CreateOrderLine]
    created_by: uuid.UUID
    payment_method_preference: str | None = None


class CreateOrderUseCase:
    def __init__(self, repository: OrderRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: CreateOrderCommand) -> Order:
        order = Order(
            order_id=self._repository.next_id(),
            tenant_id=command.tenant_id,
            branch_id=command.branch_id,
            customer_id=command.customer_id,
            address_id=command.address_id,
            delivery_address=command.delivery_address,
            booking_source=command.booking_source,
            requested_date=command.requested_date,
            payment_method_preference=command.payment_method_preference,
            lines=[
                OrderLine(
                    line_id=self._repository.next_id(),
                    cylinder_type_id=line.cylinder_type_id,
                    quantity_ordered=line.quantity,
                )
                for line in command.lines
            ],
        )
        order.submit(changed_by=command.created_by)
        await self._repository.save(order)
        await self._unit_of_work.commit()
        return order


@dataclass(frozen=True, slots=True)
class ConfirmOrderCommand(Command):
    order_id: uuid.UUID
    changed_by: uuid.UUID


class ConfirmOrderUseCase:
    def __init__(
        self,
        order_repository: OrderRepository,
        customer_repository: CustomerRepository,
        price_list_repository: PriceListRepository,
        cylinder_cap_policy: CylinderCapPolicy,
        credit_limit_evaluator: CreditLimitEvaluator,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._order_repository = order_repository
        self._customer_repository = customer_repository
        self._price_list_repository = price_list_repository
        self._cylinder_cap_policy = cylinder_cap_policy
        self._credit_limit_evaluator = credit_limit_evaluator
        self._unit_of_work = unit_of_work

    async def execute(self, command: ConfirmOrderCommand) -> Order:
        order = await self._order_repository.get_by_id(command.order_id)
        if order is None:
            msg = f"No order visible with id {command.order_id}."
            raise NotFoundError(msg, order_id=str(command.order_id))
        customer = await self._customer_repository.get_by_id(order.customer_id)
        if customer is None:
            msg = f"No customer visible with id {order.customer_id}."
            raise NotFoundError(msg, customer_id=str(order.customer_id))

        requested_lines = [(line.cylinder_type_id, line.quantity_ordered) for line in order.lines]
        await self._cylinder_cap_policy.evaluate(
            tenant_id=order.tenant_id,
            customer_id=order.customer_id,
            customer_type=customer.customer_type,
            requested_lines=requested_lines,
        )

        now = datetime.now(UTC)
        unit_prices: dict[uuid.UUID, Decimal] = {}
        for line in order.lines:
            entries = await self._price_list_repository.list_for_tenant_and_cylinder_type(
                order.tenant_id, line.cylinder_type_id, customer.customer_type
            )
            resolved = EffectivePriceResolver.resolve(
                entries,
                cylinder_type_id=line.cylinder_type_id,
                customer_type=customer.customer_type,
                branch_id=order.branch_id,
                at=now,
            )
            if resolved is None:
                msg = f"No price configured for cylinder type {line.cylinder_type_id}."
                raise NotFoundError(msg, cylinder_type_id=str(line.cylinder_type_id))
            unit_prices[line.cylinder_type_id] = resolved.price

        order_total_preview = sum(
            (unit_prices[line.cylinder_type_id] * line.quantity_ordered for line in order.lines),
            start=Decimal("0"),
        )
        await self._credit_limit_evaluator.evaluate(
            tenant_id=order.tenant_id,
            customer_id=order.customer_id,
            order_total=order_total_preview,
        )

        order.confirm(unit_prices=unit_prices, changed_by=command.changed_by)
        await self._order_repository.save(order)
        await self._unit_of_work.commit()
        return order


# ==========================================================================
# Assign (atomic: Order + Route/RouteStop + vehicle InventoryLocation)
# ==========================================================================


@dataclass(frozen=True, slots=True)
class AssignOrderCommand(Command):
    order_id: uuid.UUID
    driver_id: uuid.UUID
    vehicle_id: uuid.UUID
    changed_by: uuid.UUID


class AssignOrderUseCase:
    """`confirmed -> assigned` — the single-order "quick assign" entry
    point (`POST /orders/{id}/assign`, driven from the Order Queue/Detail
    UI). Finds an already-open route for this exact driver+vehicle+day
    (`RouteRepository.get_route_with_open_stop_for`) or plans a new
    single-stop one, then delegates the actual atomic Order+Route+
    `InventoryLocation` mutation to `AssignOrderToRouteUseCase` — the same
    use case the Dispatch Board calls directly when a dispatcher assigns an
    unassigned order onto an already-planned route. Both paths converge on
    one place that does the reservation math and state transitions, so
    there is exactly one "assign an order" behavior, not two.
    """

    def __init__(
        self,
        order_repository: OrderRepository,
        route_repository: RouteRepository,
        inventory_location_repository: InventoryLocationRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._order_repository = order_repository
        self._route_repository = route_repository
        self._assign_to_route = AssignOrderToRouteUseCase(
            route_repository, order_repository, inventory_location_repository, unit_of_work
        )

    async def execute(self, command: AssignOrderCommand) -> Order:
        order = await self._order_repository.get_by_id(command.order_id)
        if order is None:
            msg = f"No order visible with id {command.order_id}."
            raise NotFoundError(msg, order_id=str(command.order_id))

        route_date = order.requested_date.date()
        route = await self._route_repository.get_route_with_open_stop_for(
            command.driver_id, command.vehicle_id, route_date
        )
        if route is None:
            route = Route(
                route_id=self._route_repository.next_id(),
                tenant_id=order.tenant_id,
                branch_id=order.branch_id,
                driver_id=command.driver_id,
                vehicle_id=command.vehicle_id,
                route_date=order.requested_date,
                status="planned",
                stops=[],
            )
            route.record_planned()
            await self._route_repository.save(route)

        result = await self._assign_to_route.execute(
            AssignOrderToRouteCommand(
                route_id=route.id, order_id=order.id, changed_by=command.changed_by
            )
        )
        return result.order


# ==========================================================================
# Dispatch / depart / reschedule (single-aggregate)
# ==========================================================================


@dataclass(frozen=True, slots=True)
class DispatchOrderCommand(Command):
    order_id: uuid.UUID
    changed_by: uuid.UUID


class DispatchOrderUseCase:
    def __init__(self, repository: OrderRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: DispatchOrderCommand) -> Order:
        order = await self._repository.get_by_id(command.order_id)
        if order is None:
            msg = f"No order visible with id {command.order_id}."
            raise NotFoundError(msg, order_id=str(command.order_id))
        order.dispatch(changed_by=command.changed_by)
        await self._repository.save(order)
        await self._unit_of_work.commit()
        return order


@dataclass(frozen=True, slots=True)
class DepartOrderCommand(Command):
    order_id: uuid.UUID
    changed_by: uuid.UUID


class DepartOrderUseCase:
    """`ready_for_dispatch -> out_for_delivery`. Also advances the paired
    `delivery.route` to `in_progress` if this is the first order on that
    route to depart — `Route.record_proof_of_delivery()`/`.record_failed_
    delivery()` (called later, from `DeliverOrderUseCase`/`RecordFailedDelivery
    UseCase`) both require the route to already be `in_progress`, and
    nothing else in the system triggers that transition. Idempotent: a
    second order on the same multi-stop route departing finds the route
    already `in_progress` and skips the transition.
    """

    def __init__(
        self,
        order_repository: OrderRepository,
        route_repository: RouteRepository,
        customer_repository: CustomerRepository,
        otp_store: OtpStore,
        otp_delivery: OtpDeliveryPort,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._order_repository = order_repository
        self._route_repository = route_repository
        self._customer_repository = customer_repository
        self._otp_store = otp_store
        self._otp_delivery = otp_delivery
        self._unit_of_work = unit_of_work

    async def execute(self, command: DepartOrderCommand) -> Order:
        order = await self._order_repository.get_by_id(command.order_id)
        if order is None:
            msg = f"No order visible with id {command.order_id}."
            raise NotFoundError(msg, order_id=str(command.order_id))

        # Read the customer *before* committing, not after: `Database.
        # _apply_tenant_context()` sets `app.current_tenant_id` via
        # `set_config(..., is_local => true)`, which is transaction-scoped —
        # `unit_of_work.commit()` ends that transaction, so a query issued
        # afterward on this same session runs with no tenant context set,
        # and RLS's null-safe predicate then silently matches zero rows.
        # This is a genuine bug class, not just this call site — any
        # post-commit read on a `UnitOfWork`'s own session hits it.
        customer = await self._customer_repository.get_by_id(order.customer_id)

        route = None
        if order.route_stop_id is not None:
            owner = await self._route_repository.get_stop_owner(order.route_stop_id)
            if owner is not None:
                route = await self._route_repository.get_by_id(owner.route_id)

        order.depart(changed_by=command.changed_by)
        if route is not None and route.status == "loaded":
            route.change_status("in_progress")

        await self._order_repository.save(order)
        if route is not None:
            await self._route_repository.save(route)
        await self._unit_of_work.commit()

        # Best-effort, post-commit: a real status change already landed —
        # a delivery-OTP delivery hiccup shouldn't roll it back. Only the
        # external I/O (Redis OTP store, delivery send) happens here now.
        if customer is not None:
            key = order_delivery_otp_key(order.tenant_id, order.id)
            code = await self._otp_store.issue(key)
            await self._otp_delivery.send(customer.phone_number, code)
        return order


@dataclass(frozen=True, slots=True)
class RescheduleOrderCommand(Command):
    order_id: uuid.UUID
    changed_by: uuid.UUID


class RescheduleOrderUseCase:
    """`failed_delivery -> ready_for_dispatch` (D-12). Also resets the paired
    `RouteStop` from `failed` back to `pending` (`Route.reschedule_stop()`)
    — without this, the stop stays terminal and the retry's later `POST
    .../deliver` would fail `Route.record_proof_of_delivery()`'s own
    transition guard even though the Order itself is legitimately back in
    the dispatch pipeline.
    """

    def __init__(
        self,
        repository: OrderRepository,
        route_repository: RouteRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._repository = repository
        self._route_repository = route_repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: RescheduleOrderCommand) -> Order:
        order = await self._repository.get_by_id(command.order_id)
        if order is None:
            msg = f"No order visible with id {command.order_id}."
            raise NotFoundError(msg, order_id=str(command.order_id))

        route = None
        if order.route_stop_id is not None:
            owner = await self._route_repository.get_stop_owner(order.route_stop_id)
            if owner is not None:
                route = await self._route_repository.get_by_id(owner.route_id)

        order.reschedule(changed_by=command.changed_by)
        if route is not None and order.route_stop_id is not None:
            route.reschedule_stop(order.route_stop_id)

        await self._repository.save(order)
        if route is not None:
            await self._route_repository.save(route)
        await self._unit_of_work.commit()
        return order


# ==========================================================================
# Deliver (atomic: Order + vehicle InventoryLocation + ProofOfDelivery)
# ==========================================================================


@dataclass(frozen=True, slots=True)
class DeliverOrderCommand(Command):
    order_id: uuid.UUID
    lines: Sequence[DeliveredLine]
    otp_code: str
    signature_blob_ref: str
    photo_blob_ref: str
    gps_lat: Decimal
    gps_lng: Decimal
    payment_method: str
    amount_collected: Decimal
    changed_by: uuid.UUID


@dataclass(frozen=True, slots=True)
class DeliverOrderResult:
    order: Order
    proof_of_delivery: ProofOfDeliveryEntry


class DeliverOrderUseCase:
    """`out_for_delivery -> delivered`. Also the single point where a
    `delivery.route_stop`'s own status/proof-of-delivery gets set (Phase
    12) — the driver-facing capture happens here, once; the Dispatch
    Board's route-stop view only ever *reads* what this method wrote.
    """

    def __init__(
        self,
        order_repository: OrderRepository,
        route_repository: RouteRepository,
        inventory_location_repository: InventoryLocationRepository,
        pod_repository: ProofOfDeliveryRepository,
        otp_store: OtpStore,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._order_repository = order_repository
        self._route_repository = route_repository
        self._inventory_repository = inventory_location_repository
        self._pod_repository = pod_repository
        self._otp_store = otp_store
        self._unit_of_work = unit_of_work

    async def execute(self, command: DeliverOrderCommand) -> DeliverOrderResult:
        order = await self._order_repository.get_by_id(command.order_id)
        if order is None:
            msg = f"No order visible with id {command.order_id}."
            raise NotFoundError(msg, order_id=str(command.order_id))

        key = order_delivery_otp_key(order.tenant_id, order.id)
        otp_ok = await self._otp_store.verify(key, command.otp_code)
        if not otp_ok:
            msg = "Incorrect delivery OTP."
            raise OtpMismatchError(msg, order_id=str(order.id))

        self._validate_pod_fields(command)

        vehicle_location = None
        route = None
        if order.route_stop_id is not None:
            owner = await self._route_repository.get_stop_owner(order.route_stop_id)
            if owner is not None:
                vehicle_location = await self._inventory_repository.get_by_location_ref(
                    "vehicle", owner.vehicle_id
                )
                route = await self._route_repository.get_by_id(owner.route_id)

        # All mutation happens in memory before any save.
        if vehicle_location is not None:
            for delivered in command.lines:
                line = order.line_for(delivered.cylinder_type_id)
                reserved = line.quantity_ordered - line.quantity_pending
                shortfall = reserved - delivered.quantity_delivered
                if shortfall > 0:
                    vehicle_location.release_reservation(
                        delivered.cylinder_type_id,
                        shortfall,
                        performed_by=command.changed_by,
                        reference_order_id=order.id,
                    )
                if delivered.quantity_collected_empty > 0:
                    vehicle_location.record_collection(
                        delivered.cylinder_type_id,
                        delivered.quantity_collected_empty,
                        performed_by=command.changed_by,
                    )

        order.deliver(lines=command.lines, changed_by=command.changed_by)
        if route is not None and order.route_stop_id is not None:
            route.record_proof_of_delivery(
                order.route_stop_id,
                RouteProofOfDelivery(
                    otp_verified=True,
                    signature_url=command.signature_blob_ref,
                    photo_url=command.photo_blob_ref,
                    gps_lat=float(command.gps_lat),
                    gps_lon=float(command.gps_lng),
                ),
            )

        await self._order_repository.save(order)
        if vehicle_location is not None:
            await self._inventory_repository.save(vehicle_location)
        if route is not None:
            await self._route_repository.save(route)
        pod = await self._pod_repository.create(
            pod_id=self._pod_repository.next_id(),
            tenant_id=order.tenant_id,
            order_id=order.id,
            otp_verified_at=datetime.now(UTC),
            signature_blob_ref=command.signature_blob_ref,
            photo_blob_ref=command.photo_blob_ref,
            gps_lat=command.gps_lat,
            gps_lng=command.gps_lng,
            payment_method=command.payment_method,
            amount_collected=command.amount_collected,
            recorded_by=command.changed_by,
        )
        await self._unit_of_work.commit()
        return DeliverOrderResult(order=order, proof_of_delivery=pod)

    @staticmethod
    def _validate_pod_fields(command: DeliverOrderCommand) -> None:
        from lpg.application.common.errors import IncompletePodError

        if not command.signature_blob_ref.strip() or not command.photo_blob_ref.strip():
            msg = "Signature/photo reference cannot be blank."
            raise IncompletePodError(msg, order_id=str(command.order_id))
        if not (Decimal("-90") <= command.gps_lat <= Decimal("90")):
            msg = f"GPS latitude out of range: {command.gps_lat}."
            raise IncompletePodError(msg, order_id=str(command.order_id))
        if not (Decimal("-180") <= command.gps_lng <= Decimal("180")):
            msg = f"GPS longitude out of range: {command.gps_lng}."
            raise IncompletePodError(msg, order_id=str(command.order_id))


# ==========================================================================
# Failed delivery
# ==========================================================================


@dataclass(frozen=True, slots=True)
class RecordFailedDeliveryCommand(Command):
    order_id: uuid.UUID
    reason_code: str
    resolution_action: str | None
    recorded_by: uuid.UUID


class RecordFailedDeliveryUseCase:
    """`out_for_delivery -> failed_delivery` (D-12). Keeps the paired
    `RouteStop` in sync the same way `DeliverOrderUseCase` does for a
    successful delivery.
    """

    def __init__(
        self,
        repository: OrderRepository,
        route_repository: RouteRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._repository = repository
        self._route_repository = route_repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: RecordFailedDeliveryCommand) -> Order:
        order = await self._repository.get_by_id(command.order_id)
        if order is None:
            msg = f"No order visible with id {command.order_id}."
            raise NotFoundError(msg, order_id=str(command.order_id))

        route = None
        if order.route_stop_id is not None:
            owner = await self._route_repository.get_stop_owner(order.route_stop_id)
            if owner is not None:
                route = await self._route_repository.get_by_id(owner.route_id)

        order.fail_delivery(
            reason_code=command.reason_code,
            resolution_action=command.resolution_action,
            recorded_by=command.recorded_by,
        )
        if route is not None and order.route_stop_id is not None:
            route.record_failed_delivery(order.route_stop_id, command.reason_code)

        await self._repository.save(order)
        if route is not None:
            await self._route_repository.save(route)
        await self._unit_of_work.commit()
        return order


# ==========================================================================
# Cancellation (free path atomic when a vehicle is assigned; approval path
# is two requests — request now, approve later)
# ==========================================================================


@dataclass(frozen=True, slots=True)
class CancelOrderCommand(Command):
    order_id: uuid.UUID
    reason: str
    cancelled_by: uuid.UUID


@dataclass(frozen=True, slots=True)
class CancelOrderResult:
    order: Order
    pending_approval: bool


class CancelOrderUseCase:
    def __init__(
        self,
        order_repository: OrderRepository,
        route_repository: RouteRepository,
        inventory_location_repository: InventoryLocationRepository,
        cancellation_repository: CancellationRecordRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._order_repository = order_repository
        self._route_repository = route_repository
        self._inventory_repository = inventory_location_repository
        self._cancellation_repository = cancellation_repository
        self._unit_of_work = unit_of_work
        self._get_or_create_location = GetOrCreateInventoryLocationUseCase(
            inventory_location_repository
        )

    async def execute(self, command: CancelOrderCommand) -> CancelOrderResult:
        order = await self._order_repository.get_by_id(command.order_id)
        if order is None:
            msg = f"No order visible with id {command.order_id}."
            raise NotFoundError(msg, order_id=str(command.order_id))

        if order.requires_cancellation_approval:
            order.request_cancellation_approval(reason=command.reason)
            await self._cancellation_repository.create(
                record_id=self._cancellation_repository.next_id(),
                tenant_id=order.tenant_id,
                order_id=order.id,
                cancelled_by=command.cancelled_by,
                reason=command.reason,
            )
            await self._unit_of_work.commit()
            return CancelOrderResult(order=order, pending_approval=True)

        vehicle_location = None
        route = None
        if order.route_stop_id is not None:
            # A confirmed order's `route_stop_id` is only ever set by
            # `assign()`, which always creates/reserves against the
            # vehicle's `InventoryLocation` in the same transaction — so
            # this location is guaranteed to already exist. Resolved the
            # same lazy-create-on-first-use way regardless, matching every
            # other inventory call site instead of assuming a raw lookup
            # can't be `None`.
            owner = await self._route_repository.get_stop_owner(order.route_stop_id)
            if owner is not None:
                vehicle_location = await self._get_or_create_location.execute(
                    tenant_id=order.tenant_id,
                    location_type="vehicle",
                    location_ref_id=owner.vehicle_id,
                )
                route = await self._route_repository.get_by_id(owner.route_id)
                for line in order.lines:
                    reserved = line.quantity_ordered - line.quantity_pending
                    if reserved > 0:
                        vehicle_location.release_reservation(
                            line.cylinder_type_id,
                            reserved,
                            performed_by=command.cancelled_by,
                            reference_order_id=order.id,
                        )

        # cancel_free() itself raises INVALID_STATE_TRANSITION for any
        # status neither free-cancellable nor approval-required (draft,
        # cancelled, closed) — no separate guard needed here.
        order.cancel_free(cancelled_by=command.cancelled_by, reason=command.reason)
        if route is not None and order.route_stop_id is not None:
            route.cancel_stop(order.route_stop_id)

        await self._order_repository.save(order)
        if vehicle_location is not None:
            await self._inventory_repository.save(vehicle_location)
        if route is not None:
            await self._route_repository.save(route)
        await self._unit_of_work.commit()
        return CancelOrderResult(order=order, pending_approval=False)


@dataclass(frozen=True, slots=True)
class ApproveOrderCancellationCommand(Command):
    order_id: uuid.UUID
    approved_by: uuid.UUID


class ApproveOrderCancellationUseCase:
    def __init__(
        self,
        order_repository: OrderRepository,
        route_repository: RouteRepository,
        inventory_location_repository: InventoryLocationRepository,
        cancellation_repository: CancellationRecordRepository,
        tenant_configuration_repository: TenantConfigurationRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._order_repository = order_repository
        self._route_repository = route_repository
        self._inventory_repository = inventory_location_repository
        self._cancellation_repository = cancellation_repository
        self._tenant_configuration_repository = tenant_configuration_repository
        self._unit_of_work = unit_of_work
        self._get_or_create_location = GetOrCreateInventoryLocationUseCase(
            inventory_location_repository
        )

    async def execute(self, command: ApproveOrderCancellationCommand) -> Order:
        order = await self._order_repository.get_by_id(command.order_id)
        if order is None:
            msg = f"No order visible with id {command.order_id}."
            raise NotFoundError(msg, order_id=str(command.order_id))
        pending = await self._cancellation_repository.get_pending_by_order_id(order.id)
        if pending is None:
            msg = f"No pending cancellation approval for order {command.order_id}."
            raise NotFoundError(msg, order_id=str(command.order_id))

        entries = await self._tenant_configuration_repository.list_for_tenant_and_key(
            order.tenant_id, _CANCELLATION_FEE_CONFIG_KEY
        )
        resolved_config = TenantConfigurationResolver.resolve(
            entries, _CANCELLATION_FEE_CONFIG_KEY, datetime.now(UTC)
        )
        config_value = resolved_config.config_value if resolved_config is not None else None
        fee = CancellationFeeCalculator.calculate(
            config_value=config_value, order_total=order.total_amount or Decimal("0")
        )

        vehicle_location = None
        route = None
        if order.route_stop_id is not None:
            owner = await self._route_repository.get_stop_owner(order.route_stop_id)
            if owner is not None:
                vehicle_location = await self._get_or_create_location.execute(
                    tenant_id=order.tenant_id,
                    location_type="vehicle",
                    location_ref_id=owner.vehicle_id,
                )
                route = await self._route_repository.get_by_id(owner.route_id)
                for line in order.lines:
                    reserved = line.quantity_ordered - line.quantity_pending
                    if reserved > 0:
                        vehicle_location.release_reservation(
                            line.cylinder_type_id,
                            reserved,
                            performed_by=command.approved_by,
                            reference_order_id=order.id,
                        )

        order.approve_cancellation(
            approved_by=command.approved_by, cancellation_charge=fee, reason=pending.reason
        )
        if route is not None and order.route_stop_id is not None:
            route.cancel_stop(order.route_stop_id)

        await self._order_repository.save(order)
        if vehicle_location is not None:
            await self._inventory_repository.save(vehicle_location)
        if route is not None:
            await self._route_repository.save(route)
        await self._cancellation_repository.approve(
            pending.id, approved_by=command.approved_by, cancellation_charge=fee
        )
        await self._unit_of_work.commit()
        return order


# ==========================================================================
# Bulk cancel
# ==========================================================================

#: Above this many order ids, `CancelOrdersUseCase` enqueues a background
#: job instead of cancelling synchronously in the request (10-api-design-
#: guidelines.md §8).
BULK_CANCEL_SYNC_THRESHOLD = 50


@dataclass(frozen=True, slots=True)
class BulkCancelOrdersCommand(Command):
    tenant_id: uuid.UUID
    order_ids: Sequence[uuid.UUID]
    reason: str
    cancelled_by: uuid.UUID


@dataclass(frozen=True, slots=True)
class BulkCancelOrderResult:
    order_id: uuid.UUID
    succeeded: bool
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class BulkCancelOrdersResult:
    job_id: str | None
    results: Sequence[BulkCancelOrderResult] | None


class BulkCancelOrdersUseCase:
    """`cancel_use_case_factory` must mint a **fresh** `CancelOrderUseCase`
    (bound to its own, fresh `UnitOfWork`/session) on every call — never a
    single shared instance. `CancelOrderUseCase.execute()` calls `unit_of_
    work.commit()` internally, and a `UnitOfWork` is a one-transaction,
    one-commit object (see `dependencies/unit_of_work.py::get_unit_of_work_
    factory`'s docstring for the two independent ways reusing one across
    this loop breaks silently). This mirrors `infrastructure/jobs/worker.
    py::bulk_cancel_orders`'s async-job sibling, which already opens a new
    session per order for the identical reason.
    """

    def __init__(
        self,
        cancel_use_case_factory: Callable[[], AbstractAsyncContextManager[CancelOrderUseCase]],
        job_queue: JobQueuePort,
    ) -> None:
        self._cancel_use_case_factory = cancel_use_case_factory
        self._job_queue = job_queue

    async def execute(self, command: BulkCancelOrdersCommand) -> BulkCancelOrdersResult:
        if len(command.order_ids) > BULK_CANCEL_SYNC_THRESHOLD:
            job_id = await self._job_queue.enqueue(
                "bulk_cancel_orders",
                tenant_id=str(command.tenant_id),
                order_ids=[str(oid) for oid in command.order_ids],
                reason=command.reason,
                cancelled_by=str(command.cancelled_by),
            )
            return BulkCancelOrdersResult(job_id=job_id, results=None)

        results: list[BulkCancelOrderResult] = []
        for order_id in command.order_ids:
            try:
                async with self._cancel_use_case_factory() as cancel_use_case:
                    await cancel_use_case.execute(
                        CancelOrderCommand(
                            order_id=order_id,
                            reason=command.reason,
                            cancelled_by=command.cancelled_by,
                        )
                    )
            except NotFoundError:
                results.append(
                    BulkCancelOrderResult(
                        order_id, succeeded=False, error_code="RESOURCE_NOT_FOUND"
                    )
                )
            except Exception as exc:  # noqa: BLE001 - one order's failure must not abort the batch
                error_code = getattr(exc, "error_code", "UNKNOWN_ERROR")
                results.append(
                    BulkCancelOrderResult(order_id, succeeded=False, error_code=error_code)
                )
            else:
                results.append(BulkCancelOrderResult(order_id, succeeded=True))
        return BulkCancelOrdersResult(job_id=None, results=results)


# ==========================================================================
# Close
# ==========================================================================


@dataclass(frozen=True, slots=True)
class CloseOrderCommand(Command):
    order_id: uuid.UUID
    closed_by: uuid.UUID


class CloseOrderUseCase:
    def __init__(self, repository: OrderRepository, unit_of_work: UnitOfWork) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def execute(self, command: CloseOrderCommand) -> Order:
        order = await self._repository.get_by_id(command.order_id)
        if order is None:
            msg = f"No order visible with id {command.order_id}."
            raise NotFoundError(msg, order_id=str(command.order_id))
        order.close(closed_by=command.closed_by)
        await self._repository.save(order)
        await self._unit_of_work.commit()
        return order


# ==========================================================================
# Reads
# ==========================================================================


@dataclass(frozen=True, slots=True)
class GetOrderQuery(Query):
    order_id: uuid.UUID
    #: Non-None means the caller is scoped — the fetched order must match,
    #: or a 404 is raised (never 403, so scoped callers can't distinguish
    #: "doesn't exist" from "not yours" — OWASP API1).
    scoped_customer_id: uuid.UUID | None = None
    #: A driver's own `Order.route_stop_id` must be one of the stops on
    #: *their* active route — the router resolves this set once via
    #: `RouteRepository.get_active_route_for_driver()` before building the
    #: query (Order itself no longer stores a driver id to compare against
    #: directly, Phase 12).
    scoped_route_stop_ids: frozenset[uuid.UUID] | None = None
    scoped_branch_id: uuid.UUID | None = None


def _order_in_scope(
    order: Order,
    *,
    scoped_customer_id: uuid.UUID | None,
    scoped_route_stop_ids: frozenset[uuid.UUID] | None,
    scoped_branch_id: uuid.UUID | None,
) -> bool:
    """Shared by `GetOrderUseCase` and `ListOrderStatusHistoryUseCase` — both
    apply the identical OWASP-API1 scoping rule (404, never 403) before
    returning anything about an order a caller doesn't own/isn't assigned/
    isn't in the branch of.
    """
    if scoped_customer_id is not None and order.customer_id != scoped_customer_id:
        return False
    if scoped_route_stop_ids is not None and order.route_stop_id not in scoped_route_stop_ids:
        return False
    return not (scoped_branch_id is not None and order.branch_id != scoped_branch_id)


class GetOrderUseCase:
    def __init__(self, repository: OrderRepository) -> None:
        self._repository = repository

    async def execute(self, query: GetOrderQuery) -> Order:
        order = await self._repository.get_by_id(query.order_id)
        in_scope = order is not None and _order_in_scope(
            order,
            scoped_customer_id=query.scoped_customer_id,
            scoped_route_stop_ids=query.scoped_route_stop_ids,
            scoped_branch_id=query.scoped_branch_id,
        )
        if not in_scope:
            msg = f"No order visible with id {query.order_id}."
            raise NotFoundError(msg, order_id=str(query.order_id))
        return order  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class ListOrdersQuery(Query):
    skip: int = 0
    limit: int = 50
    status: str | None = None
    branch_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    driver_id: uuid.UUID | None = None
    from_date: datetime | None = None
    to_date: datetime | None = None


@dataclass(frozen=True, slots=True)
class OrderPage:
    items: Sequence[Order]
    total: int


class ListOrdersUseCase:
    def __init__(self, repository: OrderRepository) -> None:
        self._repository = repository

    async def execute(self, query: ListOrdersQuery) -> OrderPage:
        items = await self._repository.list_orders(
            skip=query.skip,
            limit=query.limit,
            status=query.status,
            branch_id=query.branch_id,
            customer_id=query.customer_id,
            driver_id=query.driver_id,
            from_date=query.from_date,
            to_date=query.to_date,
        )
        total = await self._repository.count_orders(
            status=query.status,
            branch_id=query.branch_id,
            customer_id=query.customer_id,
            driver_id=query.driver_id,
            from_date=query.from_date,
            to_date=query.to_date,
        )
        return OrderPage(items=items, total=total)


@dataclass(frozen=True, slots=True)
class ListOrderStatusHistoryQuery(Query):
    order_id: uuid.UUID
    #: Same OWASP-API1 reasoning as `GetOrderQuery` — a scoped caller who
    #: can't see the order gets a 404, never a 403.
    scoped_customer_id: uuid.UUID | None = None
    scoped_route_stop_ids: frozenset[uuid.UUID] | None = None
    scoped_branch_id: uuid.UUID | None = None


class ListOrderStatusHistoryUseCase:
    def __init__(self, repository: OrderRepository) -> None:
        self._repository = repository

    async def execute(
        self, query: ListOrderStatusHistoryQuery
    ) -> Sequence[OrderStatusHistoryEntry]:
        order = await self._repository.get_by_id(query.order_id)
        in_scope = order is not None and _order_in_scope(
            order,
            scoped_customer_id=query.scoped_customer_id,
            scoped_route_stop_ids=query.scoped_route_stop_ids,
            scoped_branch_id=query.scoped_branch_id,
        )
        if not in_scope:
            msg = f"No order visible with id {query.order_id}."
            raise NotFoundError(msg, order_id=str(query.order_id))
        return await self._repository.list_status_history(query.order_id)
