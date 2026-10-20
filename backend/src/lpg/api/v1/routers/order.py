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
from collections.abc import Callable, Sequence
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal, cast

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
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
    require_rate_limit,
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
    get_order_customer_directory,
    get_order_number_sequence,
    get_order_repository,
    get_orderable_cylinder_types,
    get_proof_of_delivery_repository,
)
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.api.v1.schemas.order import (
    AmendOrderRequest,
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
    OrderableCylinderTypeResponse,
    OrderCustomerResponse,
    OrderLineResponse,
    OrderPageResponse,
    OrderResponse,
    OrderStatus,
    OrderStatusHistoryEntryResponse,
    OrderTrackingResponse,
    PaymentMethod,
    PendingCancellationResponse,
    PodAttachmentResponse,
    ProofOfDeliveryResponse,
    RecordFailedDeliveryRequest,
    RejectCancellationRequest,
    RescheduleOrderRequest,
    TrackingDriverInfo,
)
from lpg.application.common.errors import NotFoundError, ValidationError
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
from lpg.application.order.booking_source import resolve_booking_source
from lpg.application.order.orderable import OrderableCylinderTypes
from lpg.application.order.ports import (
    CancellationRecordEntry,
    CancellationRecordRepository,
    CreditLimitEvaluator,
    CylinderCapPolicy,
    OrderCustomerDirectory,
    OrderCustomerSummary,
    OrderNumberSequence,
    OrderRepository,
    ProofOfDeliveryEntry,
    ProofOfDeliveryRepository,
)
from lpg.application.order.use_cases import (
    AmendOrderCommand,
    AmendOrderUseCase,
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
    GetCancellationRequestUseCase,
    GetOrderQuery,
    GetOrderUseCase,
    ListOrdersQuery,
    ListOrderStatusHistoryQuery,
    ListOrderStatusHistoryUseCase,
    ListOrdersUseCase,
    RecordFailedDeliveryCommand,
    RecordFailedDeliveryUseCase,
    RejectOrderCancellationCommand,
    RejectOrderCancellationUseCase,
    RescheduleOrderCommand,
    RescheduleOrderUseCase,
    ResendDeliveryOtpCommand,
    ResendDeliveryOtpUseCase,
)
from lpg.application.tenant.ports import (
    PriceListRepository,
    TenantConfigurationRepository,
)
from lpg.application.tenant_admin.ports import EmployeeRepository
from lpg.config.settings import Settings, get_settings
from lpg.domain.order.order import DeliveredLine, Order
from lpg.infrastructure.idempotency.service import (
    IdempotencyService,
    fingerprint,
    run_idempotent,
)

router = APIRouter(tags=["Orders"])


def _require_actor(principal: AuthenticatedPrincipal) -> uuid.UUID:
    if principal.user_id is None:
        raise HTTPException(status_code=401, detail="User ID is required.")
    return principal.user_id


def _order_to_response(
    order: Order,
    *,
    customer: OrderCustomerSummary | None = None,
    cancellation_pending: bool = False,
) -> OrderResponse:
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
        customer=(
            OrderCustomerResponse(
                id=customer.customer_id,
                full_name=customer.full_name,
                phone_number=customer.phone_number,
                consumer_number=customer.consumer_number,
                customer_type=customer.customer_type,
            )
            if customer is not None
            else None
        ),
        cancellation_pending=cancellation_pending,
    )


async def _orders_with_customers(
    orders: Sequence[Order],
    directory: OrderCustomerDirectory,
    cancellations: CancellationRecordRepository,
) -> list[OrderResponse]:
    """Order responses with who each order is for and whether a
    cancellation request is waiting — two queries for the whole page."""
    customers = await directory.summaries([order.customer_id for order in orders])
    pending = await cancellations.pending_order_ids([order.id for order in orders])
    return [
        _order_to_response(
            order,
            customer=customers.get(order.customer_id),
            cancellation_pending=order.id in pending,
        )
        for order in orders
    ]


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
        dac_code=entry.dac_code,
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
    customer_repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
    driver_repository: Annotated[DriverRepository, Depends(get_driver_repository)],
    route_repository: Annotated[RouteRepository, Depends(get_route_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
    order_number_sequence: Annotated[OrderNumberSequence, Depends(get_order_number_sequence)],
    orderable_cylinder_types: Annotated[
        OrderableCylinderTypes, Depends(get_orderable_cylinder_types)
    ],
    cylinder_cap_policy: Annotated[CylinderCapPolicy, Depends(get_cylinder_cap_policy)],
) -> OrderResponse:
    """Create a booking (`draft -> booked`). Idempotency-Key required.

    The delivery address is always the customer's saved address
    `address_id`; `delivery_address` in the body is ignored.

    - 404 when the customer is not visible.
    - 409 `CUSTOMER_NOT_ELIGIBLE` when the connection is not active or KYC
      is rejected/expired; `ADDRESS_NOT_FOUND` when `address_id` is not one
      of the customer's addresses.
    - 409 `CYLINDER_NOT_ORDERABLE` when a line's cylinder type is inactive,
      has no price for the customer, or is out of stock at the branch.
    - 409 `CYLINDER_CAP_EXCEEDED` when the booking takes the customer over
      the tenant's cylinder holding cap for their connection type.
    """
    idempotency_key = request.headers.get("Idempotency-Key")
    if idempotency_key is None:
        raise HTTPException(status_code=400, detail="Idempotency-Key header is required.")

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

    booking_source = resolve_booking_source(principal.role, body.booking_source)
    use_case = CreateOrderUseCase(
        order_repository,
        unit_of_work,
        order_number_sequence,
        customer_repository,
        orderable_cylinder_types,
        cylinder_cap_policy,
    )

    async def _operation() -> dict[str, Any]:
        order = await use_case.execute(
            CreateOrderCommand(
                tenant_id=principal.tenant_id,
                branch_id=body.branch_id,
                customer_id=customer_id,
                address_id=body.address_id,
                booking_source=booking_source,
                requested_date=body.requested_date,
                lines=[
                    CreateOrderLine(cylinder_type_id=line.cylinder_type_id, quantity=line.quantity)
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
    "/orders/orderable-cylinder-types",
    response_model=list[OrderableCylinderTypeResponse],
    dependencies=[Depends(require_permission("orders:create"))],
    summary="List the cylinder types a customer can book",
)
async def list_orderable_cylinder_types(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    customer_repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
    orderable_cylinder_types: Annotated[
        OrderableCylinderTypes, Depends(get_orderable_cylinder_types)
    ],
    customer_id: uuid.UUID | None = None,
    branch_id: uuid.UUID | None = None,
) -> list[OrderableCylinderTypeResponse]:
    """Only the types a booking would accept: active, priced for the
    customer's type at the branch, and with filled stock left after open
    orders. A customer login always gets its own list at its own branch;
    staff pass `customer_id`, and `branch_id` defaults to the customer's.
    """
    if principal.role == "customer":
        customer = await customer_repository.get_by_identity_user_id(_require_actor(principal))
        if customer is None:
            raise HTTPException(
                status_code=403, detail="No customer profile linked to this account."
            )
        branch_id = customer.branch_id
    else:
        if customer_id is None:
            raise HTTPException(status_code=422, detail="customer_id is required.")
        found = await customer_repository.get_by_id(customer_id)
        if found is None:
            msg = f"No customer visible with id {customer_id}."
            raise NotFoundError(msg, customer_id=str(customer_id))
        customer = found
        branch_id = branch_id or customer.branch_id

    options = await orderable_cylinder_types.list(
        tenant_id=principal.tenant_id,
        branch_id=branch_id,
        customer_type=customer.customer_type,
    )
    return [
        OrderableCylinderTypeResponse(
            cylinder_type_id=option.cylinder_type_id,
            name=option.name,
            weight_kg=option.weight_kg,
            unit_price=option.unit_price,
            available_quantity=option.available_quantity,
        )
        for option in options
    ]


@router.get(
    "/orders",
    response_model=OrderPageResponse,
    dependencies=[Depends(require_permission("orders:read"))],
)
async def list_orders(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    order_repository: Annotated[OrderRepository, Depends(get_order_repository)],
    customer_repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
    driver_repository: Annotated[DriverRepository, Depends(get_driver_repository)],
    route_repository: Annotated[RouteRepository, Depends(get_route_repository)],
    customer_directory: Annotated[OrderCustomerDirectory, Depends(get_order_customer_directory)],
    cancellation_repository: Annotated[
        CancellationRecordRepository, Depends(get_cancellation_record_repository)
    ],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    status: OrderStatus | None = None,
    search: Annotated[
        str | None,
        Query(
            max_length=100,
            description="Order number, or the customer's name, phone or consumer number.",
        ),
    ] = None,
    from_date: Annotated[
        datetime | None, Query(description="Delivery date on or after (inclusive).")
    ] = None,
    to_date: Annotated[
        datetime | None, Query(description="Delivery date on or before (inclusive).")
    ] = None,
    customer_id: Annotated[
        uuid.UUID | None, Query(description="One customer's orders (staff only).")
    ] = None,
) -> OrderPageResponse:
    """Order Queue — newest first; filter by status, delivery date range,
    customer, or a free-text search (DO-12). Each order carries its
    customer's name, phone and consumer number."""
    scope = await _resolve_scope(
        principal, customer_repository, driver_repository, route_repository
    )
    if scope.blocked:
        return OrderPageResponse(items=[], total=0)
    if from_date is not None and to_date is not None and from_date > to_date:
        msg = "The 'from' date must be on or before the 'to' date."
        raise ValidationError(msg, field="from_date")

    use_case = ListOrdersUseCase(order_repository)
    page = await use_case.execute(
        ListOrdersQuery(
            skip=skip,
            limit=limit,
            status=status,
            branch_id=scope.branch_id,
            # A customer login is always limited to their own orders.
            customer_id=scope.customer_id if scope.customer_id is not None else customer_id,
            driver_id=scope.driver_id,
            from_date=from_date,
            to_date=to_date,
            search=search,
        )
    )
    items = await _orders_with_customers(page.items, customer_directory, cancellation_repository)
    return OrderPageResponse(items=items, total=page.total)


@router.get(
    "/orders/{order_id}",
    response_model=OrderResponse,
    dependencies=[Depends(require_permission("orders:read"))],
)
async def get_order(
    order_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    order_repository: Annotated[OrderRepository, Depends(get_order_repository)],
    customer_repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
    driver_repository: Annotated[DriverRepository, Depends(get_driver_repository)],
    route_repository: Annotated[RouteRepository, Depends(get_route_repository)],
    customer_directory: Annotated[OrderCustomerDirectory, Depends(get_order_customer_directory)],
    cancellation_repository: Annotated[
        CancellationRecordRepository, Depends(get_cancellation_record_repository)
    ],
) -> OrderResponse:
    scope = await _resolve_scope(
        principal, customer_repository, driver_repository, route_repository
    )
    if scope.blocked:
        msg = "Order not found."
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
    [response] = await _orders_with_customers([order], customer_directory, cancellation_repository)
    return response


@router.get(
    "/orders/{order_id}/tracking",
    response_model=OrderTrackingResponse,
    dependencies=[Depends(require_permission("orders:read"))],
)
async def get_order_tracking(
    order_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    order_repository: Annotated[OrderRepository, Depends(get_order_repository)],
    customer_repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
    driver_repository: Annotated[DriverRepository, Depends(get_driver_repository)],
    route_repository: Annotated[RouteRepository, Depends(get_route_repository)],
    vehicle_repository: Annotated[VehicleRepository, Depends(get_vehicle_repository)],
    employee_repository: Annotated[EmployeeRepository, Depends(get_employee_repository)],
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
        msg = "Order not found."
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
                    f"{vehicle.make} {vehicle.model}".strip() if vehicle is not None else None
                )
                driver_info = TrackingDriverInfo(
                    name=f"{employee.first_name} {employee.last_name}".strip(),
                    phone_number=employee.phone_number,
                    vehicle_number=(vehicle.registration_number if vehicle is not None else None),
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
    customer_repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
    driver_repository: Annotated[DriverRepository, Depends(get_driver_repository)],
    route_repository: Annotated[RouteRepository, Depends(get_route_repository)],
) -> list[OrderStatusHistoryEntryResponse]:
    """The order detail view's timeline — same row-scoping as `GET /orders/{order_id}`."""
    scope = await _resolve_scope(
        principal, customer_repository, driver_repository, route_repository
    )
    if scope.blocked:
        msg = "Order not found."
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
    customer_repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
    price_list_repository: Annotated[PriceListRepository, Depends(get_price_list_repository)],
    cylinder_cap_policy: Annotated[CylinderCapPolicy, Depends(get_cylinder_cap_policy)],
    credit_limit_evaluator: Annotated[CreditLimitEvaluator, Depends(get_credit_limit_evaluator)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    orderable_cylinder_types: Annotated[
        OrderableCylinderTypes, Depends(get_orderable_cylinder_types)
    ],
) -> OrderResponse:
    """`booked -> confirmed`. Resolves and snapshots unit prices.

    409 `CYLINDER_CAP_EXCEEDED` (BR-04) or `CREDIT_LIMIT_EXCEEDED` (BR-19)
    when the tenant's configured `cylinder_holding_cap` /
    `credit_limit_default` for the customer's type would be exceeded.
    """
    actor_id = _require_actor(principal)
    use_case = ConfirmOrderUseCase(
        order_repository,
        customer_repository,
        price_list_repository,
        cylinder_cap_policy,
        credit_limit_evaluator,
        unit_of_work,
        orderable_cylinder_types,
    )
    order = await use_case.execute(ConfirmOrderCommand(order_id=order_id, changed_by=actor_id))
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
    order = await use_case.execute(DispatchOrderCommand(order_id=order_id, changed_by=actor_id))
    return _order_to_response(order)


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
        msg = "Order not found."
        raise NotFoundError(msg, order_id=str(order_id))


async def _require_own_driver_order_when_driver(
    order_id: uuid.UUID,
    principal: AuthenticatedPrincipal,
    order_repository: OrderRepository,
    driver_repository: DriverRepository,
    route_repository: RouteRepository,
) -> None:
    """`orders:dispatch` folds dispatch/depart/reschedule and is granted to
    both dispatch staff and the `driver` role (`7c3f1a9e2b4d`). For a driver
    principal, additionally confirm the order is *this* driver's own
    assignment — the same 404-not-403 ownership rule the `orders:deliver`
    endpoints apply. Staff principals are scoped by tenant/RLS alone.
    """
    if principal.role != "driver":
        return
    await _require_own_driver_order(
        order_id, principal, order_repository, driver_repository, route_repository
    )


@router.post(
    "/orders/{order_id}/depart",
    response_model=OrderResponse,
    dependencies=[Depends(require_permission("orders:dispatch"))],
)
async def depart_order(
    request: Request,
    order_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    order_repository: Annotated[OrderRepository, Depends(get_order_repository)],
    driver_repository: Annotated[DriverRepository, Depends(get_driver_repository)],
    route_repository: Annotated[RouteRepository, Depends(get_route_repository)],
    customer_repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
    otp_store: Annotated[OtpStore, Depends(get_otp_store)],
    otp_delivery: Annotated[OtpDeliveryPort, Depends(get_otp_delivery)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> OrderResponse:
    """`ready_for_dispatch -> out_for_delivery` ("driver departs"). Issues
    the delivery OTP to the customer's phone post-commit.

    `Idempotency-Key` is optional (the offline Driver App sends one so a
    queued retry replays rather than re-issuing the OTP; online callers need
    not) — see `run_idempotent`.
    """
    await _require_own_driver_order_when_driver(
        order_id, principal, order_repository, driver_repository, route_repository
    )
    actor_id = _require_actor(principal)
    use_case = DepartOrderUseCase(
        order_repository,
        route_repository,
        customer_repository,
        otp_store,
        otp_delivery,
        unit_of_work,
        delivery_otp_ttl_seconds=settings.delivery_otp_ttl_seconds,
    )

    async def _operation() -> dict[str, Any]:
        order = await use_case.execute(DepartOrderCommand(order_id=order_id, changed_by=actor_id))
        return _order_to_response(order).model_dump(mode="json")

    result = await run_idempotent(
        idempotency_service,
        tenant_id=principal.tenant_id,
        idempotency_key=request.headers.get("Idempotency-Key"),
        fingerprint_payload={"order_id": str(order_id)},
        operation=_operation,
    )
    return OrderResponse.model_validate(result)


@router.post(
    "/orders/{order_id}/delivery-otp",
    status_code=204,
    dependencies=[Depends(require_permission("orders:deliver"))],
)
async def resend_delivery_otp(
    order_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    order_repository: Annotated[OrderRepository, Depends(get_order_repository)],
    driver_repository: Annotated[DriverRepository, Depends(get_driver_repository)],
    route_repository: Annotated[RouteRepository, Depends(get_route_repository)],
    customer_repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
    otp_store: Annotated[OtpStore, Depends(get_otp_store)],
    otp_delivery: Annotated[OtpDeliveryPort, Depends(get_otp_delivery)],
    settings: Annotated[Settings, Depends(get_settings)],
    _rate_limit: Annotated[
        None,
        Depends(
            require_rate_limit(
                key_prefix="orders:delivery_otp_resend", limit=10, window_seconds=600
            )
        ),
    ],
) -> Response:
    """Send the customer a fresh delivery OTP for an `out_for_delivery` order,
    replacing the earlier one (lost, never arrived, or expired). `409` when the
    order is not out for delivery; `503` when the SMS could not be sent.
    """
    await _require_own_driver_order(
        order_id, principal, order_repository, driver_repository, route_repository
    )
    use_case = ResendDeliveryOtpUseCase(
        order_repository,
        customer_repository,
        otp_store,
        otp_delivery,
        delivery_otp_ttl_seconds=settings.delivery_otp_ttl_seconds,
    )
    await use_case.execute(ResendDeliveryOtpCommand(order_id=order_id))
    return Response(status_code=204)


@router.patch(
    "/orders/{order_id}",
    response_model=OrderResponse,
    dependencies=[Depends(require_permission("orders:confirm"))],
)
async def amend_order(
    order_id: uuid.UUID,
    body: AmendOrderRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    order_repository: Annotated[OrderRepository, Depends(get_order_repository)],
    customer_repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
    price_list_repository: Annotated[PriceListRepository, Depends(get_price_list_repository)],
    orderable_cylinder_types: Annotated[
        OrderableCylinderTypes, Depends(get_orderable_cylinder_types)
    ],
    cylinder_cap_policy: Annotated[CylinderCapPolicy, Depends(get_cylinder_cap_policy)],
    credit_limit_evaluator: Annotated[CreditLimitEvaluator, Depends(get_credit_limit_evaluator)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> OrderResponse:
    """Edit a booked or confirmed order before it is put on a trip (DO-13):
    quantities, cylinder types, delivery address (one of the customer's
    saved addresses) or delivery date. A confirmed order is re-priced at
    today's prices. Needs `orders:confirm` — the staff who accept bookings
    are the ones who change them.

    409 when the order is already on a trip (`CONFLICT`), the date is in the
    past, the address is not the customer's (`ADDRESS_NOT_FOUND`), or a
    booking rule fails (`CYLINDER_NOT_ORDERABLE`, `CYLINDER_CAP_EXCEEDED`,
    `CREDIT_LIMIT_EXCEEDED`).
    """
    actor_id = _require_actor(principal)
    order = await AmendOrderUseCase(
        order_repository,
        customer_repository,
        price_list_repository,
        orderable_cylinder_types,
        cylinder_cap_policy,
        credit_limit_evaluator,
        unit_of_work,
    ).execute(
        AmendOrderCommand(
            order_id=order_id,
            changed_by=actor_id,
            lines=(
                [
                    CreateOrderLine(cylinder_type_id=line.cylinder_type_id, quantity=line.quantity)
                    for line in body.lines
                ]
                if body.lines is not None
                else None
            ),
            requested_date=body.requested_date,
            address_id=body.address_id,
            payment_method_preference=body.payment_method_preference,
        )
    )
    return _order_to_response(order)


@router.post(
    "/orders/{order_id}/reschedule",
    response_model=OrderResponse,
    dependencies=[Depends(require_permission("orders:dispatch"))],
)
async def reschedule_order(
    request: Request,
    order_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    order_repository: Annotated[OrderRepository, Depends(get_order_repository)],
    driver_repository: Annotated[DriverRepository, Depends(get_driver_repository)],
    route_repository: Annotated[RouteRepository, Depends(get_route_repository)],
    inventory_location_repository: Annotated[
        InventoryLocationRepository, Depends(get_inventory_location_repository)
    ],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
    body: RescheduleOrderRequest | None = None,
) -> OrderResponse:
    """Without a body: `failed_delivery -> ready_for_dispatch`, retrying on
    the same trip (the paired `RouteStop` goes back to `pending`).

    With `requested_date` (DO-13): `failed_delivery -> confirmed` — the order
    leaves its trip (the stop stays failed, the van's reservation is
    released) and waits to be planned onto a trip on that date. A date in
    the past is a 409.

    `Idempotency-Key` is optional — see `run_idempotent`.
    """
    await _require_own_driver_order_when_driver(
        order_id, principal, order_repository, driver_repository, route_repository
    )
    actor_id = _require_actor(principal)
    requested_date = body.requested_date if body is not None else None
    use_case = RescheduleOrderUseCase(
        order_repository, route_repository, unit_of_work, inventory_location_repository
    )

    async def _operation() -> dict[str, Any]:
        order = await use_case.execute(
            RescheduleOrderCommand(
                order_id=order_id, changed_by=actor_id, requested_date=requested_date
            )
        )
        return _order_to_response(order).model_dump(mode="json")

    result = await run_idempotent(
        idempotency_service,
        tenant_id=principal.tenant_id,
        idempotency_key=request.headers.get("Idempotency-Key"),
        fingerprint_payload={
            "order_id": str(order_id),
            "requested_date": requested_date.isoformat() if requested_date else None,
        },
        operation=_operation,
    )
    return OrderResponse.model_validate(result)


# ==========================================================================
# Proof of Delivery attachments / Deliver / Failed delivery
# ==========================================================================


@router.get(
    "/orders/{order_id}/proof-of-delivery",
    response_model=ProofOfDeliveryResponse | None,
    dependencies=[Depends(require_permission("orders:read"))],
)
async def get_proof_of_delivery(
    order_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    order_repository: Annotated[OrderRepository, Depends(get_order_repository)],
    customer_repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
    driver_repository: Annotated[DriverRepository, Depends(get_driver_repository)],
    route_repository: Annotated[RouteRepository, Depends(get_route_repository)],
    pod_repository: Annotated[ProofOfDeliveryRepository, Depends(get_proof_of_delivery_repository)],
    file_storage: Annotated[FileStorage, Depends(get_file_storage)],
) -> ProofOfDeliveryResponse | None:
    """The delivery record of a delivered order (DO-26): when the OTP was
    verified, where, how much was collected and how, with short-lived links
    to the signature and photo when the driver captured them. `null` until
    the order is delivered. Same row-scoping as `GET /orders/{order_id}`.
    """
    scope = await _resolve_scope(
        principal, customer_repository, driver_repository, route_repository
    )
    if scope.blocked:
        raise NotFoundError("Order not found.", order_id=str(order_id))
    order = await GetOrderUseCase(order_repository).execute(
        GetOrderQuery(
            order_id=order_id,
            scoped_customer_id=scope.customer_id,
            scoped_route_stop_ids=scope.route_stop_ids,
            scoped_branch_id=scope.branch_id,
        )
    )
    entry = await pod_repository.get_by_order_id(order.id)
    if entry is None:
        return None
    response = _pod_to_response(entry)
    if entry.signature_blob_ref:
        response.signature_url = await file_storage.url(
            entry.signature_blob_ref, expires_seconds=600
        )
    if entry.photo_blob_ref:
        response.photo_url = await file_storage.url(entry.photo_blob_ref, expires_seconds=600)
    return response


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
    pod_repository: Annotated[ProofOfDeliveryRepository, Depends(get_proof_of_delivery_repository)],
    otp_store: Annotated[OtpStore, Depends(get_otp_store)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
) -> DeliverOrderResponse:
    """`out_for_delivery -> delivered`. Idempotency-Key required (offline-
    sync retries). Missing POD fields are a 422 (see `ProofOfDeliverySubmission`);
    present-but-invalid ones (blank ref, out-of-range GPS) are a 400
    `IncompletePodError`; wrong/expired OTP is a 409.
    """
    idempotency_key = request.headers.get("Idempotency-Key")
    if idempotency_key is None:
        raise HTTPException(status_code=400, detail="Idempotency-Key header is required.")

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
                dac_code=body.proof_of_delivery.dac_code,
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
    request: Request,
    order_id: uuid.UUID,
    body: RecordFailedDeliveryRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    order_repository: Annotated[OrderRepository, Depends(get_order_repository)],
    driver_repository: Annotated[DriverRepository, Depends(get_driver_repository)],
    route_repository: Annotated[RouteRepository, Depends(get_route_repository)],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)],
) -> OrderResponse:
    """`out_for_delivery -> failed_delivery` (D-12).

    `Idempotency-Key` is optional — see `run_idempotent`. Reusing a key with
    a different reason/resolution body is a 409 `IDEMPOTENCY_KEY_CONFLICT`.
    """
    await _require_own_driver_order(
        order_id, principal, order_repository, driver_repository, route_repository
    )
    actor_id = _require_actor(principal)
    use_case = RecordFailedDeliveryUseCase(order_repository, route_repository, unit_of_work)

    async def _operation() -> dict[str, Any]:
        order = await use_case.execute(
            RecordFailedDeliveryCommand(
                order_id=order_id,
                reason_code=body.reason_code,
                resolution_action=body.resolution_action,
                recorded_by=actor_id,
            )
        )
        return _order_to_response(order).model_dump(mode="json")

    result = await run_idempotent(
        idempotency_service,
        tenant_id=principal.tenant_id,
        idempotency_key=request.headers.get("Idempotency-Key"),
        fingerprint_payload={"order_id": str(order_id), **body.model_dump(mode="json")},
        operation=_operation,
    )
    return OrderResponse.model_validate(result)


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


@router.get(
    "/orders/{order_id}/cancellation-request",
    response_model=PendingCancellationResponse | None,
    dependencies=[Depends(require_permission("orders:read"))],
)
async def get_pending_cancellation(
    order_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    order_repository: Annotated[OrderRepository, Depends(get_order_repository)],
    customer_repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
    driver_repository: Annotated[DriverRepository, Depends(get_driver_repository)],
    route_repository: Annotated[RouteRepository, Depends(get_route_repository)],
    cancellation_repository: Annotated[
        CancellationRecordRepository, Depends(get_cancellation_record_repository)
    ],
    tenant_configuration_repository: Annotated[
        TenantConfigurationRepository, Depends(get_tenant_configuration_repository)
    ],
    include_decided: Annotated[
        bool,
        Query(description="Return the latest request even once approved or rejected."),
    ] = False,
) -> PendingCancellationResponse | None:
    """The cancellation request waiting for Manager approval on this order,
    with the charge approving it would record, or `null` when there is none
    (D-19). With `include_decided=true`, the latest request whatever its
    outcome, so the apps can show that it was rejected and why (CA-07).
    """
    scope = await _resolve_scope(
        principal, customer_repository, driver_repository, route_repository
    )
    if scope.blocked:
        raise NotFoundError("Order not found.", order_id=str(order_id))
    view = await GetCancellationRequestUseCase(
        order_repository, cancellation_repository, tenant_configuration_repository
    ).execute(
        GetOrderQuery(
            order_id=order_id,
            scoped_customer_id=scope.customer_id,
            scoped_route_stop_ids=scope.route_stop_ids,
            scoped_branch_id=scope.branch_id,
        ),
        include_decided=include_decided,
    )
    if view is None:
        return None
    return _cancellation_request_to_response(view.record, view.estimated_charge)


def _cancellation_request_to_response(
    entry: CancellationRecordEntry, estimated_charge: Decimal | None = None
) -> PendingCancellationResponse:
    return PendingCancellationResponse(
        id=entry.id,
        order_id=entry.order_id,
        reason=entry.reason,
        requested_by=entry.cancelled_by,
        requested_at=entry.requested_at,
        status=cast("Literal['pending', 'approved', 'rejected']", entry.status),
        estimated_charge=estimated_charge,
        cancellation_charge=entry.cancellation_charge,
        decided_at=entry.approved_at or entry.rejected_at,
        rejection_reason=entry.rejection_reason,
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
    "/orders/{order_id}/cancel/reject",
    response_model=PendingCancellationResponse,
    dependencies=[Depends(require_live_permission("orders:cancel_approve"))],
)
async def reject_order_cancellation(
    order_id: uuid.UUID,
    body: RejectCancellationRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    order_repository: Annotated[OrderRepository, Depends(get_order_repository)],
    cancellation_repository: Annotated[
        CancellationRecordRepository, Depends(get_cancellation_record_repository)
    ],
    unit_of_work: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> PendingCancellationResponse:
    """Reject a pending post-dispatch cancellation request with a reason
    (DO-14). The order keeps its status and delivery goes ahead; the
    customer may ask again. Live-checked, like approval (D-19).

    404 when the order has no request waiting; 422 without a reason.
    """
    actor_id = _require_actor(principal)
    record = await RejectOrderCancellationUseCase(
        order_repository, cancellation_repository, unit_of_work
    ).execute(
        RejectOrderCancellationCommand(order_id=order_id, rejected_by=actor_id, reason=body.reason)
    )
    return _cancellation_request_to_response(record)


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
    order = await use_case.execute(CloseOrderCommand(order_id=order_id, closed_by=actor_id))
    return _order_to_response(order)
