"""FastAPI router for the order bounded context.

Exposes the full 10-state order lifecycle under `/orders`, gated by the
permissions seeded in `fa52b77ec442`/`7c3f1a9e2b4d`:

  orders:create    orders:read      orders:confirm    orders:assign
  orders:dispatch  orders:deliver   orders:cancel      orders:cancel_approve
  orders:close

`orders:cancel_approve` is live-checked (D-19, `docs/data/17-api-security.md`
§7). `orders:dispatch` deliberately covers dispatch/depart/reschedule — one
permission for the "move along the pipeline" family, matching this
codebase's existing economy-of-permissions judgment.

Domain and application errors are never caught here — they propagate to the
global handlers registered in `lpg.api.middleware.problem_details`, which
already map them to the correct status code, `error_code` and RFC 7807
body. Catching and re-wrapping them into a generic `HTTPException` here
would only lose that mapping.

**Role-scoped `orders:read`/`orders:create`** — applied here, before the
repository is ever queried (never a post-filter, OWASP API1): `customer`
role forces `customer_id` from `CustomerRepository.get_by_identity_user_id`;
`driver` role forces `driver_id` from `DriverRepository.
get_by_identity_user_id`; `dispatcher`/`manager` force `branch_id =
principal.branch_id`; every other role that holds the permission
(`agency_admin`, `super_admin`, `accountant`, `warehouse_staff`) is
tenant-wide. A `customer`/`driver` principal with no linked record sees an
empty list / 404 on GET, never another tenant's or another customer's data.

**Idempotency-Key** — required on `POST /orders` and `POST /orders/{id}/
deliver` (offline-sync retries). A repeat request with the same key+body
replays the original response rather than re-running the use case.

**`/deliver`'s response omits `invoice_id`/`ledger_transaction_id`** —
Accounting/Cylinder Ledger don't exist yet (Phase 12/13); the fields are
absent, not null-faked.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Annotated, Any, cast

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    Response,
    UploadFile,
)

from lpg.api.v1.dependencies.admin import (
    get_employee_repository,
    get_price_list_repository,
    get_tenant_configuration_repository,
)
from lpg.api.v1.dependencies.customer import get_customer_repository
from lpg.api.v1.dependencies.delivery import (
    get_driver_repository,
    get_route_repository,
    get_vehicle_repository,
)
from lpg.api.v1.dependencies.identity import (
    get_current_principal,
    get_otp_delivery,
    get_otp_store,
    require_live_permission,
    require_permission,
)
from lpg.api.v1.dependencies.inventory import get_inventory_location_repository
from lpg.api.v1.dependencies.order import (
    get_cancel_order_use_case_factory,
    get_cancellation_record_repository,
    get_credit_limit_evaluator,
    get_cylinder_cap_policy,
    get_file_storage,
    get_idempotency_service,
    get_job_queue,
    get_order_number_sequence,
    get_order_repository,
    get_proof_of_delivery_repository,
)
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.api.v1.schemas.order import (
    AssignOrderRequest,
    BookingSource,
    BulkCancelOrderResultItem,
    BulkCancelOrdersRequest,
    BulkCancelOrdersResponse,
    CancelOrderRequest,
    CancelOrderResponse,
    CreateOrderRequest,
    DeliverOrderRequest,
    DeliverOrderResponse,
    DeliveryAddressPayload,
    DriverLocationSnapshot,
    OrderLineResponse,
    OrderPageResponse,
    OrderResponse,
    OrderStatus,
    OrderStatusHistoryEntryResponse,
    OrderTrackingResponse,
    PaymentMethod,
    PodAttachmentResponse,
    ProofOfDeliveryResponse,
    RecordFailedDeliveryRequest,
    TrackingDriverInfo,
)
from lpg.application.common.errors import NotFoundError
from lpg.application.common.ports import FileStorage, JobQueuePort, UnitOfWork
from lpg.application.customer.ports import CustomerRepository
from lpg.application.delivery.ports import (
    DriverRepository,
    RouteRepository,
    VehicleRepository,
)
from lpg.application.identity.ports import (
    AuthenticatedPrincipal,
    OtpDeliveryPort,
    OtpStore,
)
from lpg.application.inventory.ports import InventoryLocationRepository
from lpg.application.order.ports import (
    CancellationRecordRepository,
    CreditLimitEvaluator,
    CylinderCapPolicy,
    OrderNumberSequence,
    OrderRepository,
    ProofOfDeliveryEntry,
    ProofOfDeliveryRepository,
)
from lpg.application.order.use_cases import (
    ApproveOrderCancellationCommand,
    ApproveOrderCancellationUseCase,
    AssignOrderCommand,
    AssignOrderUseCase,
    BulkCancelOrdersCommand,
    BulkCancelOrdersUseCase,
    CancelOrderCommand,
    CancelOrderUseCase,
    CloseOrderCommand,
    CloseOrderUseCase,
    ConfirmOrderCommand,
    ConfirmOrderUseCase,
    CreateOrderCommand,
    CreateOrderLine,
    CreateOrderUseCase,
    DeliverOrderCommand,
    DeliverOrderUseCase,
    DepartOrderCommand,
    DepartOrderUseCase,
    DispatchOrderCommand,
    DispatchOrderUseCase,
    GetOrderQuery,
    GetOrderUseCase,
    ListOrdersQuery,
    ListOrderStatusHistoryQuery,
    ListOrderStatusHistoryUseCase,
    ListOrdersUseCase,
    RecordFailedDeliveryCommand,
    RecordFailedDeliveryUseCase,
    RescheduleOrderCommand,
    RescheduleOrderUseCase,
)
from lpg.application.tenant.ports import (
    PriceListRepository,
    TenantConfigurationRepository,
)
from lpg.application.tenant_admin.ports import EmployeeRepository
from lpg.domain.order.order import DeliveredLine, DeliveryAddress, Order
from lpg.infrastructure.idempotency.service import IdempotencyService, fingerprint

router = APIRouter(tags=["Orders"])


def _require_actor(principal: AuthenticatedPrincipal) -> uuid.UUID:
    if principal.user_id is None:
        raise HTTPException(status_code=401, detail="User ID is required.")
    return principal.user_id


def _order_to_response(order: Order) -> OrderResponse:
    address = order.delivery_address
    return OrderResponse(
        id=order.id,
        order_number=order.order_number,
        tenant_id=order.tenant_id,
        branch_id=order.branch_id,
        customer_id=order.customer_id,
        address_id=order.address_id,
        delivery_address=DeliveryAddressPayload(
            address_line=address.address_line,
            latitude=address.latitude,
            longitude=address.longitude,
        ),
        status=cast("OrderStatus", order.status),
        booking_source=cast("BookingSource", order.booking_source),
        payment_method_preference=cast("PaymentMethod | None", order.payment_method_preference),
        requested_date=order.requested_date,
        metadata=order.metadata,
        route_stop_id=order.route_stop_id,
        total_amount=order.total_amount,
        lines=[
            OrderLineResponse(
                id=line.id,
                cylinder_type_id=line.cylinder_type_id,
                quantity_ordered=line.quantity_ordered,
                quantity_delivered=line.quantity_delivered,
                quantity_pending=line.quantity_pending,
                quantity_collected_empty=line.quantity_collected_empty,
                is_backordered=line.is_backordered,
                unit_price=line.unit_price,
            )
            for line in order.lines
        ],
    )


def _pod_to_response(entry: ProofOfDeliveryEntry) -> ProofOfDeliveryResponse:
    return ProofOfDeliveryResponse(
        id=entry.id,
        tenant_id=entry.tenant_id,
        order_id=entry.order_id,
        otp_verified_at=entry.otp_verified_at,
        signature_blob_ref=entry.signature_blob_ref,
        photo_blob_ref=entry.photo_blob_ref,
        gps_lat=entry.gps_lat,
        gps_lng=entry.gps_lng,
        payment_method=cast("PaymentMethod", entry.payment_method),
        amount_collected=entry.amount_collected,
        recorded_by=entry.recorded_by,
        recorded_at=entry.recorded_at,
    )


class _OrderScope:
    """Row-scoping filters resolved from the principal's role, applied
    *before* any repository query (OWASP API1) — see module docstring.
    """

    __slots__ = ("blocked", "branch_id", "customer_id", "driver_id", "route_stop_ids")

    def __init__(
        self,
        *,
        customer_id: uuid.UUID | None = None,
        driver_id: uuid.UUID | None = None,
        branch_id: uuid.UUID | None = None,
        route_stop_ids: frozenset[uuid.UUID] | None = None,
        blocked: bool = False,
    ) -> None:
        self.customer_id = customer_id
        self.driver_id = driver_id
        self.branch_id = branch_id
        self.route_stop_ids = route_stop_ids
        self.blocked = blocked


async def _resolve_scope(
    principal: AuthenticatedPrincipal,
    customer_repository: CustomerRepository,
    driver_repository: DriverRepository,
    route_repository: RouteRepository,
) -> _OrderScope:
    if principal.role == "customer":
        actor_id = _require_actor(principal)
        customer = await customer_repository.get_by_identity_user_id(actor_id)
        if customer is None:
            return _OrderScope(blocked=True)
        return _OrderScope(customer_id=customer.id)
    if principal.role == "driver":
        actor_id = _require_actor(principal)
        driver = await driver_repository.get_by_identity_user_id(actor_id)
        if driver is None:
            return _OrderScope(blocked=True)
        # `Order` no longer stores a driver id directly (Phase 12) — a
        # driver's own orders are the stops on *their* active route.
        active_route = await route_repository.get_active_route_for_driver(driver.id)
        route_stop_ids = (
            frozenset(s.id for s in active_route.stops) if active_route else frozenset()
        )
        return _OrderScope(driver_id=driver.id, route_stop_ids=route_stop_ids)
    if principal.role in ("dispatcher", "manager"):
        return _OrderScope(branch_id=principal.branch_id)
    return _OrderScope()


# ==========================================================================
# Create / Confirm
# ==========================================================================


@router.post(
    "/orders",
    response_model=OrderResponse,
    status_code=201,
    dependencies=[Depends(require_permission("orders:create"))],
)
async def create_order(
    request: Request,
    body: CreateOrderRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    order_repository: Annotated[OrderRepository, Depends(get_order_repository)],
    customer_repository: Annotated[
        CustomerRepository, Depends(get_customer_repository)
    ],
    driver_repository: Annotated[DriverRepository, Depends(get_driver_repository)],
    route_repository: Annotated[RouteRepository, Depends(get_route_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    idempotency_service: Annotated[
        IdempotencyService, Depends(get_idempotency_service)
    ],
    order_number_sequence: Annotated[OrderNumberSequence, Depends(get_order_number_sequence)],
) -> OrderResponse:
    """Create a booking (`draft -> booked`). Idempotency-Key required."""
    idempotency_key = request.headers.get("Idempotency-Key")
    if idempotency_key is None:
        raise HTTPException(
            status_code=400, detail="Idempotency-Key header is required."
        )

    actor_id = _require_actor(principal)
    scope = await _resolve_scope(
        principal, customer_repository, driver_repository, route_repository
    )
    customer_id = body.customer_id
    if principal.role == "customer":
        scoped_id = scope.customer_id
        if scope.blocked or scoped_id is None:
            raise HTTPException(
                status_code=403, detail="No customer profile linked to this account."
            )
        customer_id = scoped_id

    use_case = CreateOrderUseCase(order_repository, unit_of_work, order_number_sequence)

    async def _operation() -> dict[str, Any]:
        order = await use_case.execute(
            CreateOrderCommand(
                tenant_id=principal.tenant_id,
                branch_id=body.branch_id,
                customer_id=customer_id,
                address_id=body.address_id,
                delivery_address=DeliveryAddress(
                    address_line=body.delivery_address.address_line,
                    latitude=body.delivery_address.latitude,
                    longitude=body.delivery_address.longitude,
                ),
                booking_source=body.booking_source,
                requested_date=body.requested_date,
                lines=[
                    CreateOrderLine(
                        cylinder_type_id=line.cylinder_type_id, quantity=line.quantity
                    )
                    for line in body.lines
                ],
                created_by=actor_id,
                payment_method_preference=body.payment_method_preference,
            )
        )
        return _order_to_response(order).model_dump(mode="json")

    result = await idempotency_service.execute(
        tenant_id=principal.tenant_id,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint(body.model_dump(mode="json")),
        operation=_operation,
    )
    return OrderResponse.model_validate(result)


@router.get(
    "/orders",
    response_model=OrderPageResponse,
    dependencies=[Depends(require_permission("orders:read"))],
)
async def list_orders(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    order_repository: Annotated[OrderRepository, Depends(get_order_repository)],
    customer_repository: Annotated[
        CustomerRepository, Depends(get_customer_repository)
    ],
    driver_repository: Annotated[DriverRepository, Depends(get_driver_repository)],
    route_repository: Annotated[RouteRepository, Depends(get_route_repository)],
    skip: int = 0,
    limit: int = 50,
    status: str | None = None,
) -> OrderPageResponse:
    """Order Queue — the dominant query pattern, status/branch/date filterable."""
    scope = await _resolve_scope(
        principal, customer_repository, driver_repository, route_repository
    )
    if scope.blocked:
        return OrderPageResponse(items=[], total=0)

    use_case = ListOrdersUseCase(order_repository)
    page = await use_case.execute(
        ListOrdersQuery(
            skip=skip,
            limit=limit,
            status=status,
            branch_id=scope.branch_id,
            customer_id=scope.customer_id,
            driver_id=scope.driver_id,
        )
    )
    return OrderPageResponse(
        items=[_order_to_response(order) for order in page.items], total=page.total
    )


@router.get(
    "/orders/{order_id}",
    response_model=OrderResponse,
    dependencies=[Depends(require_permission("orders:read"))],
)
async def get_order(
    order_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    order_repository: Annotated[OrderRepository, Depends(get_order_repository)],
    customer_repository: Annotated[
        CustomerRepository, Depends(get_customer_repository)
    ],
    driver_repository: Annotated[DriverRepository, Depends(get_driver_repository)],
    route_repository: Annotated[RouteRepository, Depends(get_route_repository)],
) -> OrderResponse:
    scope = await _resolve_scope(
        principal, customer_repository, driver_repository, route_repository
    )
    if scope.blocked:
        msg = f"No order visible with id {order_id}."
        raise NotFoundError(msg, order_id=str(order_id))

    use_case = GetOrderUseCase(order_repository)
    order = await use_case.execute(
        GetOrderQuery(
            order_id=order_id,
            scoped_customer_id=scope.customer_id,
            scoped_route_stop_ids=scope.route_stop_ids,
            scoped_branch_id=scope.branch_id,
        )
    )
    return _order_to_response(order)


@router.get(
    "/orders/{order_id}/tracking",
    response_model=OrderTrackingResponse,
    dependencies=[Depends(require_permission("orders:read"))],
)
async def get_order_tracking(
    order_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    order_repository: Annotated[OrderRepository, Depends(get_order_repository)],
    customer_repository: Annotated[
        CustomerRepository, Depends(get_customer_repository)
    ],
    driver_repository: Annotated[DriverRepository, Depends(get_driver_repository)],
    route_repository: Annotated[RouteRepository, Depends(get_route_repository)],
    vehicle_repository: Annotated[VehicleRepository, Depends(get_vehicle_repository)],
    employee_repository: Annotated[
        EmployeeRepository, Depends(get_employee_repository)
    ],
) -> OrderTrackingResponse:
    """The order-tracking map's data: the delivery destination, the route's
    status, the driver's last-known position (from the short-TTL cache the
    Driver App's location pings write), and the assigned driver + vehicle.
    Same row-scoping as `GET /orders/{order_id}` — a customer only sees their
    own order.
    """
    scope = await _resolve_scope(
        principal, customer_repository, driver_repository, route_repository
    )
    if scope.blocked:
        msg = f"No order visible with id {order_id}."
        raise NotFoundError(msg, order_id=str(order_id))

    order = await GetOrderUseCase(order_repository).execute(
        GetOrderQuery(
            order_id=order_id,
            scoped_customer_id=scope.customer_id,
            scoped_route_stop_ids=scope.route_stop_ids,
            scoped_branch_id=scope.branch_id,
        )
    )

    route_status: str | None = None
    driver_location: DriverLocationSnapshot | None = None
    driver_info: TrackingDriverInfo | None = None
    if order.route_stop_id is not None:
        owner = await route_repository.get_stop_owner(order.route_stop_id)
        if owner is not None:
            route = await route_repository.get_by_id(owner.route_id)
            route_status = route.status if route is not None else None

            driver = await driver_repository.get_by_id(owner.driver_id)
            employee = (
                await employee_repository.get_by_id(driver.employee_id)
                if driver is not None
                else None
            )
            vehicle = await vehicle_repository.get_by_id(owner.vehicle_id)
            if employee is not None:
                vehicle_model = (
                    f"{vehicle.make} {vehicle.model}".strip()
                    if vehicle is not None
                    else None
                )
                driver_info = TrackingDriverInfo(
                    name=f"{employee.first_name} {employee.last_name}".strip(),
                    phone_number=employee.phone_number,
                    vehicle_number=(
                        vehicle.registration_number if vehicle is not None else None
                    ),
                    vehicle_model=vehicle_model or None,
                )

            from lpg.api.app import get_app_state
            from lpg.infrastructure.realtime.driver_location import (
                RedisDriverLocationStore,
            )

            state = get_app_state()
            if state.redis is not None:
                raw = await RedisDriverLocationStore(state.redis).read(
                    order.tenant_id, owner.route_id
                )
                if raw is not None:
                    driver_location = DriverLocationSnapshot.model_validate(raw)

    address = order.delivery_address
    return OrderTrackingResponse(
        order_id=order.id,
        status=cast("OrderStatus", order.status),
        destination_latitude=address.latitude,
        destination_longitude=address.longitude,
        destination_label=address.address_line,
        route_status=route_status,
        driver_location=driver_location,
        driver=driver_info,
    )


@router.get(
    "/orders/{order_id}/history",
    response_model=list[OrderStatusHistoryEntryResponse],
    dependencies=[Depends(require_permission("orders:read"))],
)
async def list_order_status_history(
    order_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    order_repository: Annotated[OrderRepository, Depends(get_order_repository)],
    customer_repository: Annotated[
        CustomerRepository, Depends(get_customer_repository)
    ],
    driver_repository: Annotated[DriverRepository, Depends(get_driver_repository)],
    route_repository: Annotated[RouteRepository, Depends(get_route_repository)],
) -> list[OrderStatusHistoryEntryResponse]:
    """The order detail view's timeline — same row-scoping as `GET /orders/{order_id}`."""
    scope = await _resolve_scope(
        principal, customer_repository, driver_repository, route_repository
    )
    if scope.blocked:
        msg = f"No order visible with id {order_id}."
        raise NotFoundError(msg, order_id=str(order_id))

    use_case = ListOrderStatusHistoryUseCase(order_repository)
    entries = await use_case.execute(
        ListOrderStatusHistoryQuery(
            order_id=order_id,
            scoped_customer_id=scope.customer_id,
            scoped_route_stop_ids=scope.route_stop_ids,
            scoped_branch_id=scope.branch_id,
        )
    )
    return [
        OrderStatusHistoryEntryResponse(
            id=entry.id,
            order_id=entry.order_id,
            from_status=cast("OrderStatus | None", entry.from_status),
            to_status=cast("OrderStatus", entry.to_status),
            changed_by=entry.changed_by,
            changed_at=entry.changed_at,
            reason=entry.reason,
        )
        for entry in entries
    ]


@router.post(
    "/orders/{order_id}/confirm",
    response_model=OrderResponse,
    dependencies=[Depends(require_permission("orders:confirm"))],
)
async def confirm_order(
    order_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    order_repository: Annotated[OrderRepository, Depends(get_order_repository)],
    customer_repository: Annotated[
        CustomerRepository, Depends(get_customer_repository)
    ],
    price_list_repository: Annotated[
        PriceListRepository, Depends(get_price_list_repository)
    ],
    cylinder_cap_policy: Annotated[CylinderCapPolicy, Depends(get_cylinder_cap_policy)],
    credit_limit_evaluator: Annotated[
        CreditLimitEvaluator, Depends(get_credit_limit_evaluator)
    ],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> OrderResponse:
    """`booked -> confirmed`. Resolves and snapshots unit prices; runs the
    BR-04/BR-19 stub policy checks (see `infrastructure/order/policies.py`).
    """
    actor_id = _require_actor(principal)
    use_case = ConfirmOrderUseCase(
        order_repository,
        customer_repository,
        price_list_repository,
        cylinder_cap_policy,
        credit_limit_evaluator,
        unit_of_work,
    )
    order = await use_case.execute(
        ConfirmOrderCommand(order_id=order_id, changed_by=actor_id)
    )
    return _order_to_response(order)


# ==========================================================================
# Assign / Dispatch / Depart / Reschedule
# ==========================================================================


@router.post(
    "/orders/{order_id}/assign",
    response_model=OrderResponse,
    dependencies=[Depends(require_permission("orders:assign"))],
)
async def assign_order(
    order_id: uuid.UUID,
    body: AssignOrderRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    order_repository: Annotated[OrderRepository, Depends(get_order_repository)],
    route_repository: Annotated[RouteRepository, Depends(get_route_repository)],
    inventory_location_repository: Annotated[
        InventoryLocationRepository, Depends(get_inventory_location_repository)
    ],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> OrderResponse:
    """`confirmed -> assigned`. Reserves stock on the vehicle atomically with
    the Order's own transition (BR-09/D-08 backorder split) and attaches a
    `delivery.route_stop` (Phase 12) — see `AssignOrderUseCase`'s docstring
    for how the underlying `Route` is found or planned.
    """
    actor_id = _require_actor(principal)
    use_case = AssignOrderUseCase(
        order_repository, route_repository, inventory_location_repository, unit_of_work
    )
    order = await use_case.execute(
        AssignOrderCommand(
            order_id=order_id,
            driver_id=body.driver_id,
            vehicle_id=body.vehicle_id,
            changed_by=actor_id,
        )
    )
    return _order_to_response(order)


@router.post(
    "/orders/{order_id}/dispatch",
    response_model=OrderResponse,
    dependencies=[Depends(require_permission("orders:dispatch"))],
)
async def dispatch_order(
    order_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    order_repository: Annotated[OrderRepository, Depends(get_order_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> OrderResponse:
    """`assigned -> ready_for_dispatch` ("vehicle loaded")."""
    actor_id = _require_actor(principal)
    use_case = DispatchOrderUseCase(order_repository, unit_of_work)
    order = await use_case.execute(
        DispatchOrderCommand(order_id=order_id, changed_by=actor_id)
    )
    return _order_to_response(order)


@router.post(
    "/orders/{order_id}/depart",
    response_model=OrderResponse,
    dependencies=[Depends(require_permission("orders:dispatch"))],
)
async def depart_order(
    order_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    order_repository: Annotated[OrderRepository, Depends(get_order_repository)],
    route_repository: Annotated[RouteRepository, Depends(get_route_repository)],
    customer_repository: Annotated[
        CustomerRepository, Depends(get_customer_repository)
    ],
    otp_store: Annotated[OtpStore, Depends(get_otp_store)],
    otp_delivery: Annotated[OtpDeliveryPort, Depends(get_otp_delivery)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> OrderResponse:
    """`ready_for_dispatch -> out_for_delivery` ("driver departs"). Issues
    the delivery OTP to the customer's phone post-commit.
    """
    actor_id = _require_actor(principal)
    use_case = DepartOrderUseCase(
        order_repository,
        route_repository,
        customer_repository,
        otp_store,
        otp_delivery,
        unit_of_work,
    )
    order = await use_case.execute(
        DepartOrderCommand(order_id=order_id, changed_by=actor_id)
    )
    return _order_to_response(order)


@router.post(
    "/orders/{order_id}/reschedule",
    response_model=OrderResponse,
    dependencies=[Depends(require_permission("orders:dispatch"))],
)
async def reschedule_order(
    order_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    order_repository: Annotated[OrderRepository, Depends(get_order_repository)],
    route_repository: Annotated[RouteRepository, Depends(get_route_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> OrderResponse:
    """`failed_delivery -> ready_for_dispatch`. Also resets the paired
    `RouteStop` back to `pending` so the retry can reach `delivered` (see
    `RescheduleOrderUseCase`'s docstring).
    """
    actor_id = _require_actor(principal)
    use_case = RescheduleOrderUseCase(order_repository, route_repository, unit_of_work)
    order = await use_case.execute(
        RescheduleOrderCommand(order_id=order_id, changed_by=actor_id)
    )
    return _order_to_response(order)


# ==========================================================================
# Proof of Delivery attachments / Deliver / Failed delivery
# ==========================================================================


async def _require_own_driver_order(
    order_id: uuid.UUID,
    principal: AuthenticatedPrincipal,
    order_repository: OrderRepository,
    driver_repository: DriverRepository,
    route_repository: RouteRepository,
) -> None:
    """`orders:deliver` is only ever granted to the `driver` role
    (`fa52b77ec442`) — this additionally confirms the order is *this*
    driver's own assignment, 404 (never 403) if not, so a driver can't
    distinguish "not yours" from "doesn't exist" (OWASP API1). Ownership is
    resolved via the order's `route_stop_id` -> its `Route`'s `driver_id`
    (Phase 12 — `Order` no longer stores a driver id directly).
    """
    actor_id = _require_actor(principal)
    driver = await driver_repository.get_by_identity_user_id(actor_id)
    order = await order_repository.get_by_id(order_id)
    owner = (
        await route_repository.get_stop_owner(order.route_stop_id)
        if order is not None and order.route_stop_id is not None
        else None
    )
    if driver is None or order is None or owner is None or owner.driver_id != driver.id:
        msg = f"No order visible with id {order_id}."
        raise NotFoundError(msg, order_id=str(order_id))


@router.post(
    "/orders/{order_id}/pod-attachments",
    response_model=PodAttachmentResponse,
    status_code=201,
    dependencies=[Depends(require_permission("orders:deliver"))],
)
async def upload_pod_attachment(
    order_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    order_repository: Annotated[OrderRepository, Depends(get_order_repository)],
    driver_repository: Annotated[DriverRepository, Depends(get_driver_repository)],
    route_repository: Annotated[RouteRepository, Depends(get_route_repository)],
    file_storage: Annotated[FileStorage, Depends(get_file_storage)],
    file: Annotated[UploadFile, File()],
) -> PodAttachmentResponse:
    """Pre-upload a delivery photo/signature blob before `POST .../deliver`."""
    await _require_own_driver_order(
        order_id, principal, order_repository, driver_repository, route_repository
    )
    key = f"tenant/{principal.tenant_id}/orders/{order_id}/pod/{uuid.uuid4()}_{file.filename}"
    data = await file.read()
    await file_storage.upload(key, data, content_type=file.content_type)
    return PodAttachmentResponse(blob_ref=key)


@router.post(
    "/orders/{order_id}/deliver",
    response_model=DeliverOrderResponse,
    dependencies=[Depends(require_permission("orders:deliver"))],
)
async def deliver_order(
    request: Request,
    order_id: uuid.UUID,
    body: DeliverOrderRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    order_repository: Annotated[OrderRepository, Depends(get_order_repository)],
    driver_repository: Annotated[DriverRepository, Depends(get_driver_repository)],
    route_repository: Annotated[RouteRepository, Depends(get_route_repository)],
    inventory_location_repository: Annotated[
        InventoryLocationRepository, Depends(get_inventory_location_repository)
    ],
    pod_repository: Annotated[
        ProofOfDeliveryRepository, Depends(get_proof_of_delivery_repository)
    ],
    otp_store: Annotated[OtpStore, Depends(get_otp_store)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    idempotency_service: Annotated[
        IdempotencyService, Depends(get_idempotency_service)
    ],
) -> DeliverOrderResponse:
    """`out_for_delivery -> delivered`. Idempotency-Key required (offline-
    sync retries). Missing POD fields are a 422 (see `ProofOfDeliverySubmission`);
    present-but-invalid ones (blank ref, out-of-range GPS) are a 400
    `IncompletePodError`; wrong/expired OTP is a 409.
    """
    idempotency_key = request.headers.get("Idempotency-Key")
    if idempotency_key is None:
        raise HTTPException(
            status_code=400, detail="Idempotency-Key header is required."
        )

    await _require_own_driver_order(
        order_id, principal, order_repository, driver_repository, route_repository
    )
    actor_id = _require_actor(principal)
    use_case = DeliverOrderUseCase(
        order_repository,
        route_repository,
        inventory_location_repository,
        pod_repository,
        otp_store,
        unit_of_work,
    )

    async def _operation() -> dict[str, Any]:
        result = await use_case.execute(
            DeliverOrderCommand(
                order_id=order_id,
                lines=[
                    DeliveredLine(
                        cylinder_type_id=line.cylinder_type_id,
                        quantity_delivered=line.quantity_delivered,
                        quantity_collected_empty=line.quantity_collected_empty,
                    )
                    for line in body.lines
                ],
                otp_code=body.otp_code,
                signature_blob_ref=body.proof_of_delivery.signature_blob_ref,
                photo_blob_ref=body.proof_of_delivery.photo_blob_ref,
                gps_lat=body.proof_of_delivery.gps_lat,
                gps_lng=body.proof_of_delivery.gps_lng,
                payment_method=body.proof_of_delivery.payment_method,
                amount_collected=body.proof_of_delivery.amount_collected,
                changed_by=actor_id,
            )
        )
        return DeliverOrderResponse(
            order=_order_to_response(result.order),
            proof_of_delivery=_pod_to_response(result.proof_of_delivery),
        ).model_dump(mode="json")

    result = await idempotency_service.execute(
        tenant_id=principal.tenant_id,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint(body.model_dump(mode="json")),
        operation=_operation,
    )
    return DeliverOrderResponse.model_validate(result)


@router.post(
    "/orders/{order_id}/failed-delivery",
    response_model=OrderResponse,
    dependencies=[Depends(require_permission("orders:deliver"))],
)
async def record_failed_delivery(
    order_id: uuid.UUID,
    body: RecordFailedDeliveryRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    order_repository: Annotated[OrderRepository, Depends(get_order_repository)],
    driver_repository: Annotated[DriverRepository, Depends(get_driver_repository)],
    route_repository: Annotated[RouteRepository, Depends(get_route_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> OrderResponse:
    """`out_for_delivery -> failed_delivery` (D-12)."""
    await _require_own_driver_order(
        order_id, principal, order_repository, driver_repository, route_repository
    )
    actor_id = _require_actor(principal)
    use_case = RecordFailedDeliveryUseCase(
        order_repository, route_repository, unit_of_work
    )
    order = await use_case.execute(
        RecordFailedDeliveryCommand(
            order_id=order_id,
            reason_code=body.reason_code,
            resolution_action=body.resolution_action,
            recorded_by=actor_id,
        )
    )
    return _order_to_response(order)


# ==========================================================================
# Cancellation
# ==========================================================================


@router.post(
    "/orders/{order_id}/cancel",
    response_model=CancelOrderResponse,
    dependencies=[Depends(require_permission("orders:cancel"))],
)
async def cancel_order(
    order_id: uuid.UUID,
    body: CancelOrderRequest,
    response: Response,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    order_repository: Annotated[OrderRepository, Depends(get_order_repository)],
    route_repository: Annotated[RouteRepository, Depends(get_route_repository)],
    inventory_location_repository: Annotated[
        InventoryLocationRepository, Depends(get_inventory_location_repository)
    ],
    cancellation_repository: Annotated[
        CancellationRecordRepository, Depends(get_cancellation_record_repository)
    ],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> CancelOrderResponse:
    """200 (pre-dispatch, immediately `cancelled`) or 202 (post-dispatch,
    status unchanged, pending Manager approval — D-19).
    """
    actor_id = _require_actor(principal)
    use_case = CancelOrderUseCase(
        order_repository,
        route_repository,
        inventory_location_repository,
        cancellation_repository,
        unit_of_work,
    )
    result = await use_case.execute(
        CancelOrderCommand(order_id=order_id, reason=body.reason, cancelled_by=actor_id)
    )
    if result.pending_approval:
        response.status_code = 202
    return CancelOrderResponse(
        order=_order_to_response(result.order), pending_approval=result.pending_approval
    )


@router.post(
    "/orders/{order_id}/cancel/approve",
    response_model=OrderResponse,
    dependencies=[Depends(require_live_permission("orders:cancel_approve"))],
)
async def approve_order_cancellation(
    order_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    order_repository: Annotated[OrderRepository, Depends(get_order_repository)],
    route_repository: Annotated[RouteRepository, Depends(get_route_repository)],
    inventory_location_repository: Annotated[
        InventoryLocationRepository, Depends(get_inventory_location_repository)
    ],
    cancellation_repository: Annotated[
        CancellationRecordRepository, Depends(get_cancellation_record_repository)
    ],
    tenant_configuration_repository: Annotated[
        TenantConfigurationRepository, Depends(get_tenant_configuration_repository)
    ],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> OrderResponse:
    """Approve a pending post-dispatch cancellation. Live-checked (D-19)."""
    actor_id = _require_actor(principal)
    use_case = ApproveOrderCancellationUseCase(
        order_repository,
        route_repository,
        inventory_location_repository,
        cancellation_repository,
        tenant_configuration_repository,
        unit_of_work,
    )
    order = await use_case.execute(
        ApproveOrderCancellationCommand(order_id=order_id, approved_by=actor_id)
    )
    return _order_to_response(order)


@router.post(
    "/orders/bulk-cancel",
    response_model=BulkCancelOrdersResponse,
    status_code=202,
    dependencies=[Depends(require_permission("orders:cancel"))],
)
async def bulk_cancel_orders(
    body: BulkCancelOrdersRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    cancel_use_case_factory: Annotated[
        Callable[[], AbstractAsyncContextManager[CancelOrderUseCase]],
        Depends(get_cancel_order_use_case_factory),
    ],
    job_queue: Annotated[JobQueuePort, Depends(get_job_queue)],
) -> BulkCancelOrdersResponse:
    """<=50 order ids cancel synchronously (each its own transaction — see
    `get_cancel_order_use_case_factory`'s docstring for why one shared
    transaction can't process more than the first order); more enqueues
    `bulk_cancel_orders`.
    """
    actor_id = _require_actor(principal)
    use_case = BulkCancelOrdersUseCase(cancel_use_case_factory, job_queue)
    result = await use_case.execute(
        BulkCancelOrdersCommand(
            tenant_id=principal.tenant_id,
            order_ids=body.order_ids,
            reason=body.reason,
            cancelled_by=actor_id,
        )
    )
    return BulkCancelOrdersResponse(
        job_id=result.job_id,
        results=(
            [
                BulkCancelOrderResultItem(
                    order_id=item.order_id,
                    succeeded=item.succeeded,
                    error_code=item.error_code,
                )
                for item in result.results
            ]
            if result.results is not None
            else None
        ),
    )


# ==========================================================================
# Close
# ==========================================================================


@router.post(
    "/orders/{order_id}/close",
    response_model=OrderResponse,
    dependencies=[Depends(require_permission("orders:close"))],
)
async def close_order(
    order_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    order_repository: Annotated[OrderRepository, Depends(get_order_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> OrderResponse:
    """`delivered -> closed` — manual interim action pending Phase 13's
    automatic invoice-settlement trigger.
    """
    actor_id = _require_actor(principal)
    use_case = CloseOrderUseCase(order_repository, unit_of_work)
    order = await use_case.execute(
        CloseOrderCommand(order_id=order_id, closed_by=actor_id)
    )
    return _order_to_response(order)
