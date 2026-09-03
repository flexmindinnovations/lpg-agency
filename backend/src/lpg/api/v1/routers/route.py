"""API endpoints for delivery route management.

Gated by the permissions seeded in `fa52b77ec442`/`de56730bb88f`:
`routes:create`, `routes:read` (role-scoped), `routes:manage` (plan/assign/
load/status-transition — one code for the "move along the pipeline" family,
matching `orders:dispatch`'s own economy-of-permissions precedent),
`routes:deliver` (driver-only, mirrors `orders:deliver`).

`POST /orders/{id}/deliver`/`POST /orders/{id}/failed-delivery` remain the
only driver-facing "record what happened at this stop" endpoints — Proof-
of-Delivery capture is not duplicated here (see `DeliverOrderUseCase`'s
docstring). Reconciliation approval also lives in Inventory
(`POST /reconciliation/{id}/approve`); `POST /routes/{id}/reconcile` only
checks that an approval already happened.

Domain and application errors are never caught here — they propagate to the
global handlers in `lpg.api.middleware.problem_details`.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, status

from lpg.api.v1.dependencies.delivery import (
    get_assign_order_to_route_use_case,
    get_complete_route_reconciliation_use_case,
    get_confirm_route_load_use_case,
    get_driver_repository,
    get_load_vehicle_for_route_use_case,
    get_route_repository,
)
from lpg.api.v1.dependencies.identity import get_current_principal, require_permission
from lpg.api.v1.dependencies.order import get_idempotency_service
from lpg.api.v1.dependencies.unit_of_work import get_unit_of_work
from lpg.api.v1.schemas.route import (
    AssignOrderRequest,
    DriverLocationPingRequest,
    LoadVehicleRequest,
    PlanRouteRequest,
    RoutePageResponse,
    RouteResponse,
    UpdateRouteStatusRequest,
)
from lpg.application.common.errors import NotFoundError
from lpg.application.common.ports import UnitOfWork
from lpg.application.delivery.ports import DriverRepository, RouteRepository
from lpg.application.delivery.use_cases import (
    AssignOrderToRouteCommand,
    AssignOrderToRouteUseCase,
    CompleteRouteReconciliationCommand,
    CompleteRouteReconciliationUseCase,
    ConfirmRouteLoadCommand,
    ConfirmRouteLoadUseCase,
    GetActiveRouteForDriverQuery,
    GetActiveRouteForDriverUseCase,
    GetRouteQuery,
    GetRouteUseCase,
    ListRoutesQuery,
    ListRoutesUseCase,
    LoadVehicleForRouteCommand,
    LoadVehicleForRouteUseCase,
    LoadVehicleLine,
    PlanRouteCommand,
    PlanRouteUseCase,
    UpdateRouteStatusCommand,
    UpdateRouteStatusUseCase,
)
from lpg.application.identity.ports import AuthenticatedPrincipal
from lpg.domain.delivery.route import Route
from lpg.infrastructure.idempotency.service import IdempotencyService, run_idempotent

router = APIRouter(prefix="/routes", tags=["Routes"])


def _require_actor(principal: AuthenticatedPrincipal) -> uuid.UUID:
    from fastapi import HTTPException

    if principal.user_id is None:
        raise HTTPException(status_code=401, detail="User ID is required.")
    return principal.user_id


async def _resolve_read_scope(
    principal: AuthenticatedPrincipal,
    driver_repository: DriverRepository,
) -> tuple[uuid.UUID | None, uuid.UUID | None]:
    """Returns `(scoped_driver_id, scoped_branch_id)` — `driver` role is
    forced to their own id, `dispatcher`/`manager` to their branch, every
    other role holding `routes:read` (`agency_admin`, `super_admin`,
    `warehouse_staff`) is tenant-wide.
    """
    if principal.role == "driver":
        actor_id = _require_actor(principal)
        driver = await driver_repository.get_by_identity_user_id(actor_id)
        return (driver.id if driver is not None else uuid.uuid4()), None
    if principal.role in ("dispatcher", "manager"):
        return None, principal.branch_id
    return None, None


@router.post(
    "",
    response_model=RouteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Plan a new route",
    dependencies=[Depends(require_permission("routes:manage"))],
)
async def plan_route(
    request: PlanRouteRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[RouteRepository, Depends(get_route_repository)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> RouteResponse:
    command = PlanRouteCommand(
        tenant_id=principal.tenant_id,
        branch_id=request.branch_id,
        driver_id=request.driver_id,
        vehicle_id=request.vehicle_id,
        route_date=request.route_date,
    )
    use_case = PlanRouteUseCase(repository, uow)
    route = await use_case.execute(command)
    return RouteResponse.model_validate(route)


@router.get(
    "",
    response_model=RoutePageResponse,
    summary="List routes",
    dependencies=[Depends(require_permission("routes:read"))],
)
async def list_routes(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[RouteRepository, Depends(get_route_repository)],
    driver_repository: Annotated[DriverRepository, Depends(get_driver_repository)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    status: str | None = None,
    branch_id: uuid.UUID | None = None,
    date_from: datetime.date | None = None,
    date_to: datetime.date | None = None,
) -> RoutePageResponse:
    scoped_driver_id, scoped_branch_id = await _resolve_read_scope(principal, driver_repository)
    query = ListRoutesQuery(
        skip=(page - 1) * page_size,
        limit=page_size,
        status=status,
        branch_id=scoped_branch_id or branch_id,
        date_from=date_from,
        date_to=date_to,
    )
    use_case = ListRoutesUseCase(repository)
    items, total = await use_case.execute(query)
    if scoped_driver_id is not None:
        items = [r for r in items if r.driver_id == scoped_driver_id]
        total = len(items)

    return RoutePageResponse(
        items=[RouteResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/active",
    response_model=RouteResponse,
    summary="The calling driver's own active route",
    dependencies=[Depends(require_permission("routes:read"))],
)
async def get_my_active_route(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[RouteRepository, Depends(get_route_repository)],
    driver_repository: Annotated[DriverRepository, Depends(get_driver_repository)],
) -> RouteResponse:
    """The Driver App's entry point — resolves the driver from the token, so
    the app never needs to know its own `driver_id`. `404` if the caller
    isn't a driver or has no active route.
    """
    scoped_driver_id, _ = await _resolve_read_scope(principal, driver_repository)
    if scoped_driver_id is None:
        msg = "No active route for this account."
        raise NotFoundError(msg)
    query = GetActiveRouteForDriverQuery(driver_id=scoped_driver_id)
    use_case = GetActiveRouteForDriverUseCase(repository)
    route = await use_case.execute(query)
    return RouteResponse.model_validate(route)


@router.get(
    "/active-for-driver/{driver_id}",
    response_model=RouteResponse,
    summary="Get active route for driver",
    dependencies=[Depends(require_permission("routes:read"))],
)
async def get_active_route_for_driver(
    driver_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[RouteRepository, Depends(get_route_repository)],
    driver_repository: Annotated[DriverRepository, Depends(get_driver_repository)],
) -> RouteResponse:
    scoped_driver_id, _ = await _resolve_read_scope(principal, driver_repository)
    if scoped_driver_id is not None and scoped_driver_id != driver_id:
        msg = f"No active route visible for driver {driver_id}."
        raise NotFoundError(msg, driver_id=str(driver_id))
    query = GetActiveRouteForDriverQuery(driver_id=driver_id)
    use_case = GetActiveRouteForDriverUseCase(repository)
    route = await use_case.execute(query)
    return RouteResponse.model_validate(route)


@router.get(
    "/{route_id}",
    response_model=RouteResponse,
    summary="Get a specific route",
    dependencies=[Depends(require_permission("routes:read"))],
)
async def get_route(
    route_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[RouteRepository, Depends(get_route_repository)],
    driver_repository: Annotated[DriverRepository, Depends(get_driver_repository)],
) -> RouteResponse:
    scoped_driver_id, scoped_branch_id = await _resolve_read_scope(principal, driver_repository)
    query = GetRouteQuery(route_id=route_id)
    use_case = GetRouteUseCase(repository)
    route = await use_case.execute(query)
    if not _route_in_scope(route, scoped_driver_id, scoped_branch_id):
        msg = f"No route visible with id {route_id}."
        raise NotFoundError(msg, route_id=str(route_id))
    return RouteResponse.model_validate(route)


def _route_in_scope(
    route: Route, scoped_driver_id: uuid.UUID | None, scoped_branch_id: uuid.UUID | None
) -> bool:
    if scoped_driver_id is not None and route.driver_id != scoped_driver_id:
        return False
    return not (scoped_branch_id is not None and route.branch_id != scoped_branch_id)


@router.post(
    "/{route_id}/assign-order",
    response_model=RouteResponse,
    summary="Assign an unassigned order onto this route",
    dependencies=[Depends(require_permission("routes:manage"))],
)
async def assign_order(
    route_id: uuid.UUID,
    request: AssignOrderRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    use_case: Annotated[AssignOrderToRouteUseCase, Depends(get_assign_order_to_route_use_case)],
) -> RouteResponse:
    """The Dispatch Board's own multi-order grouping action — the Order
    Queue/Detail single-order "Assign" flow instead calls
    `POST /orders/{id}/assign`, which finds-or-creates a route and
    delegates to this same use case internally (see `AssignOrderUseCase`'s
    docstring in `application/order/use_cases.py`).
    """
    actor_id = _require_actor(principal)
    result = await use_case.execute(
        AssignOrderToRouteCommand(route_id=route_id, order_id=request.order_id, changed_by=actor_id)
    )
    return RouteResponse.model_validate(result.route)


@router.post(
    "/{route_id}/load",
    response_model=RouteResponse,
    summary="Load the vehicle and mark the route loaded",
    dependencies=[Depends(require_permission("routes:manage"))],
)
async def load_vehicle_for_route(
    route_id: uuid.UUID,
    request: LoadVehicleRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    use_case: Annotated[LoadVehicleForRouteUseCase, Depends(get_load_vehicle_for_route_use_case)],
) -> RouteResponse:
    """`planned -> loaded` (BR-12): atomic warehouse -> vehicle transfer."""
    actor_id = _require_actor(principal)
    route = await use_case.execute(
        LoadVehicleForRouteCommand(
            route_id=route_id,
            warehouse_id=request.warehouse_id,
            lines=[
                LoadVehicleLine(cylinder_type_id=line.cylinder_type_id, quantity=line.quantity)
                for line in request.lines
            ],
            performed_by=actor_id,
        )
    )
    return RouteResponse.model_validate(route)


@router.post(
    "/{route_id}/confirm-load",
    response_model=RouteResponse,
    summary="Driver confirms the van matches the load manifest",
    dependencies=[Depends(require_permission("routes:deliver"))],
)
async def confirm_route_load(
    http_request: Request,
    route_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    driver_repository: Annotated[DriverRepository, Depends(get_driver_repository)],
    use_case: Annotated[ConfirmRouteLoadUseCase, Depends(get_confirm_route_load_use_case)],
    idempotency_service: Annotated[
        IdempotencyService, Depends(get_idempotency_service)
    ],
) -> RouteResponse:
    """A **soft** acknowledgement that the driver has checked the van against
    the load manifest — it does *not* gate departing. Idempotent (a second
    confirm is a no-op `200`); `409 INVARIANT_VIOLATION` if the route isn't
    `loaded`. `Idempotency-Key` optional (the offline Driver App sends one).
    """
    actor_id = _require_actor(principal)
    scoped_driver_id, _ = await _resolve_read_scope(principal, driver_repository)

    async def _operation() -> dict[str, Any]:
        route = await use_case.execute(
            ConfirmRouteLoadCommand(
                route_id=route_id,
                confirmed_by=actor_id,
                expected_driver_id=scoped_driver_id,
            )
        )
        return RouteResponse.model_validate(route).model_dump(mode="json")

    result = await run_idempotent(
        idempotency_service,
        tenant_id=principal.tenant_id,
        idempotency_key=http_request.headers.get("Idempotency-Key"),
        fingerprint_payload={"route_id": str(route_id)},
        operation=_operation,
    )
    return RouteResponse.model_validate(result)


@router.post(
    "/{route_id}/reconcile",
    response_model=RouteResponse,
    summary="Close out a route once its vehicle has been reconciled",
    dependencies=[Depends(require_permission("routes:manage"))],
)
async def complete_route_reconciliation(
    route_id: uuid.UUID,
    use_case: Annotated[
        CompleteRouteReconciliationUseCase, Depends(get_complete_route_reconciliation_use_case)
    ],
) -> RouteResponse:
    """`completed -> reconciled` (BR-14) — `409 ROUTE_RECONCILIATION_PENDING`
    if the vehicle's `InventoryLocation` has no approved `ReconciliationRecord`
    yet (create/approve one via Inventory's own reconciliation endpoints
    first).
    """
    route = await use_case.execute(CompleteRouteReconciliationCommand(route_id=route_id))
    return RouteResponse.model_validate(route)


@router.post(
    "/{route_id}/location",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Report the driver's live location",
    dependencies=[Depends(require_permission("routes:deliver"))],
)
async def report_driver_location(
    route_id: uuid.UUID,
    ping: DriverLocationPingRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    repository: Annotated[RouteRepository, Depends(get_route_repository)],
    driver_repository: Annotated[DriverRepository, Depends(get_driver_repository)],
) -> None:
    """Transient telemetry, not a domain event: the ping is cached as the
    route's last-known position (short TTL) and published on each of the
    route's per-order real-time channels. `404` unless the caller is the
    route's own driver; `409` unless the route is `in_progress`.
    """
    from lpg.api.app import get_app_state
    from lpg.application.delivery.driver_location import (
        DriverLocationPing,
        publish_driver_location,
    )
    from lpg.infrastructure.realtime.driver_location import RedisDriverLocationStore

    scoped_driver_id, _ = await _resolve_read_scope(principal, driver_repository)
    route = await GetRouteUseCase(repository).execute(GetRouteQuery(route_id=route_id))

    state = get_app_state()
    if state.redis is None or state.realtime_publisher is None:
        from lpg.application.common.errors import ServiceUnavailableError

        msg = "Real-time infrastructure is not available."
        raise ServiceUnavailableError(msg)

    await publish_driver_location(
        route=route,
        acting_driver_id=scoped_driver_id,
        ping=DriverLocationPing(
            latitude=ping.latitude,
            longitude=ping.longitude,
            heading=ping.heading,
            speed_kph=ping.speed_kph,
            accuracy_m=ping.accuracy_m,
        ),
        store=RedisDriverLocationStore(state.redis),
        publisher=state.realtime_publisher,
    )


@router.patch(
    "/{route_id}/status",
    response_model=RouteResponse,
    summary="Update route status",
    dependencies=[Depends(require_permission("routes:manage"))],
)
async def update_route_status(
    route_id: uuid.UUID,
    request: UpdateRouteStatusRequest,
    repository: Annotated[RouteRepository, Depends(get_route_repository)],
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> RouteResponse:
    command = UpdateRouteStatusCommand(
        route_id=route_id,
        new_status=request.status,
    )
    use_case = UpdateRouteStatusUseCase(repository, uow)
    route = await use_case.execute(command)
    return RouteResponse.model_validate(route)
