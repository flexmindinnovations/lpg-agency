"""Route repository implementation.

All queries are automatically tenant-scoped via Row-Level Security (RLS) —
same convention `SqlAlchemyOrderRepository`/inventory repositories already
use; `tenant_id` parameters here are for constructing new rows, not
defense-in-depth `WHERE` filtering (RLS is the single source of truth for
tenant isolation in this codebase).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from lpg.application.delivery.ports import RouteStopOwner
from lpg.domain.delivery.route import LoadedLine, ProofOfDelivery, Route, RouteStop
from lpg.infrastructure.persistence.models.delivery import RouteModel, RouteStopModel

if TYPE_CHECKING:
    import datetime

    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


class SqlAlchemyRouteRepository:
    """SQLAlchemy implementation of the RouteRepository port."""

    def __init__(self, unit_of_work: SqlAlchemyUnitOfWork) -> None:
        self._uow = unit_of_work

    def next_id(self) -> uuid.UUID:
        return uuid.uuid4()

    async def save(self, route: Route) -> None:
        loaded_lines = [
            {"cylinder_type_id": str(line.cylinder_type_id), "quantity": line.quantity}
            for line in route.loaded_lines
        ] or None

        model = await self._uow.session.get(RouteModel, route.id)
        if model is None:
            model = RouteModel(
                id=route.id,
                tenant_id=route.tenant_id,
                branch_id=route.branch_id,
                driver_id=route.driver_id,
                vehicle_id=route.vehicle_id,
                route_date=route.date,
                status=route.status,
                loaded_lines=loaded_lines,
                load_confirmed_at=route.load_confirmed_at,
                version=route.version,
            )
            self._uow.session.add(model)
        else:
            model.status = route.status
            model.loaded_lines = loaded_lines
            model.load_confirmed_at = route.load_confirmed_at
            model.version = route.version

        # Handle stops
        stmt = select(RouteStopModel).where(RouteStopModel.route_id == route.id)
        result = await self._uow.session.scalars(stmt)
        existing_stops = {s.id: s for s in result}

        for stop in route.stops:
            if stop.id in existing_stops:
                stop_model = existing_stops[stop.id]
                stop_model.status = stop.status
                stop_model.failure_reason = stop.failure_reason
                if stop.proof_of_delivery:
                    stop_model.otp_verified = stop.proof_of_delivery.otp_verified
                    stop_model.signature_url = stop.proof_of_delivery.signature_url
                    stop_model.photo_url = stop.proof_of_delivery.photo_url
                    stop_model.gps_lat = stop.proof_of_delivery.gps_lat
                    stop_model.gps_lon = stop.proof_of_delivery.gps_lon
                # Remove from dict so we know it was processed
                existing_stops.pop(stop.id)
            else:
                stop_model = RouteStopModel(
                    id=stop.id,
                    route_id=route.id,
                    order_id=stop.order_id,
                    sequence_number=stop.sequence_number,
                    status=stop.status,
                    failure_reason=stop.failure_reason,
                )
                if stop.proof_of_delivery:
                    stop_model.otp_verified = stop.proof_of_delivery.otp_verified
                    stop_model.signature_url = stop.proof_of_delivery.signature_url
                    stop_model.photo_url = stop.proof_of_delivery.photo_url
                    stop_model.gps_lat = stop.proof_of_delivery.gps_lat
                    stop_model.gps_lon = stop.proof_of_delivery.gps_lon
                self._uow.session.add(stop_model)

        # `RouteStop`s are never removed once created — a stop can only ever
        # be cancelled (`status="cancelled"`), which is itself a value in
        # `existing_stops`'s update path above. Nothing is left to delete.

        self._uow.session.add(model)
        # `Session.get()` (used both above and by `get_by_id()`/other
        # lookups on this same session) deliberately bypasses autoflush —
        # without an explicit flush here, a route created and saved earlier
        # in the same request (e.g. `AssignOrderUseCase`'s find-or-create
        # path, which saves a freshly-planned `Route` and then immediately
        # calls `AssignOrderToRouteUseCase`, which looks it up again by id)
        # would be invisible until the surrounding transaction committed,
        # surfacing as a spurious 404. Same reasoning `SqlAlchemyOrder
        # Repository.save()` already documents for its own flush.
        await self._uow.session.flush()
        # Registers `route` with the Unit of Work so `commit()` collects and
        # dispatches its domain events after the transaction lands — the
        # same mechanism `SqlAlchemyOrderRepository`/inventory repositories
        # use; writing events onto `session.info` directly (as this method
        # used to) is never read by `SqlAlchemyUnitOfWork.collect_events()`,
        # which only walks `_tracked_aggregates`.
        self._uow.register_aggregate(route)

    async def get_by_id(self, route_id: uuid.UUID) -> Route | None:
        # No relationship mapped between RouteModel and RouteStopModel yet —
        # two queries rather than a single `selectinload()`.
        model = await self._uow.session.get(RouteModel, route_id)
        if model is None:
            return None

        stmt = (
            select(RouteStopModel)
            .where(RouteStopModel.route_id == route_id)
            .order_by(RouteStopModel.sequence_number)
        )
        result = await self._uow.session.scalars(stmt)
        stops_models = result.all()

        return self._to_domain(model, list(stops_models))

    async def get_active_route_for_driver(self, driver_id: uuid.UUID) -> Route | None:
        stmt = (
            select(RouteModel)
            .where(RouteModel.driver_id == driver_id)
            .where(RouteModel.status.in_(["planned", "loaded", "in_progress"]))
            .order_by(RouteModel.created_at.desc())
            .limit(1)
        )
        model = await self._uow.session.scalar(stmt)
        if model is None:
            return None

        stmt_stops = (
            select(RouteStopModel)
            .where(RouteStopModel.route_id == model.id)
            .order_by(RouteStopModel.sequence_number)
        )
        stops_models = (await self._uow.session.scalars(stmt_stops)).all()

        return self._to_domain(model, list(stops_models))

    async def get_route_with_open_stop_for(
        self, driver_id: uuid.UUID, vehicle_id: uuid.UUID, route_date: datetime.date
    ) -> Route | None:
        stmt = (
            select(RouteModel)
            .where(RouteModel.driver_id == driver_id)
            .where(RouteModel.vehicle_id == vehicle_id)
            .where(func.date(RouteModel.route_date) == route_date)
            .where(RouteModel.status.in_(["planned", "loaded"]))
            .order_by(RouteModel.created_at.desc())
            .limit(1)
        )
        model = await self._uow.session.scalar(stmt)
        if model is None:
            return None

        stmt_stops = (
            select(RouteStopModel)
            .where(RouteStopModel.route_id == model.id)
            .order_by(RouteStopModel.sequence_number)
        )
        stops_models = (await self._uow.session.scalars(stmt_stops)).all()
        return self._to_domain(model, list(stops_models))

    async def count_active_routes_for_order(self, order_id: uuid.UUID) -> int:
        stmt = (
            select(func.count(RouteStopModel.id))
            .join(RouteModel, RouteModel.id == RouteStopModel.route_id)
            .where(RouteStopModel.order_id == order_id)
            .where(RouteStopModel.status != "cancelled")
            .where(RouteModel.status.notin_(["cancelled"]))
        )
        return int(await self._uow.session.scalar(stmt) or 0)

    async def get_stop_owner(self, route_stop_id: uuid.UUID) -> RouteStopOwner | None:
        stmt = (
            select(RouteModel.id, RouteModel.driver_id, RouteModel.vehicle_id)
            .join(RouteStopModel, RouteStopModel.route_id == RouteModel.id)
            .where(RouteStopModel.id == route_stop_id)
        )
        row = (await self._uow.session.execute(stmt)).first()
        if row is None:
            return None
        return RouteStopOwner(route_id=row[0], driver_id=row[1], vehicle_id=row[2])

    async def list_routes(
        self,
        skip: int = 0,
        limit: int = 100,
        status: str | None = None,
        branch_id: uuid.UUID | None = None,
        date_from: datetime.date | None = None,
        date_to: datetime.date | None = None,
    ) -> list[Route]:
        stmt = select(RouteModel).order_by(RouteModel.created_at.desc())
        stmt = self._apply_filters(stmt, status, branch_id, date_from, date_to)
        stmt = stmt.offset(skip).limit(limit)

        models = (await self._uow.session.scalars(stmt)).all()
        if not models:
            return []

        route_ids = [m.id for m in models]
        stmt_stops = (
            select(RouteStopModel)
            .where(RouteStopModel.route_id.in_(route_ids))
            .order_by(RouteStopModel.route_id, RouteStopModel.sequence_number)
        )
        stops_models = (await self._uow.session.scalars(stmt_stops)).all()

        stops_by_route: dict[uuid.UUID, list[RouteStopModel]] = {}
        for sm in stops_models:
            stops_by_route.setdefault(sm.route_id, []).append(sm)

        return [self._to_domain(m, stops_by_route.get(m.id, [])) for m in models]

    async def count_routes(
        self,
        status: str | None = None,
        branch_id: uuid.UUID | None = None,
        date_from: datetime.date | None = None,
        date_to: datetime.date | None = None,
    ) -> int:
        stmt = select(func.count(RouteModel.id))
        stmt = self._apply_filters(stmt, status, branch_id, date_from, date_to)
        return int(await self._uow.session.scalar(stmt) or 0)

    def _apply_filters(
        self,
        stmt: Any,
        status: str | None,
        branch_id: uuid.UUID | None,
        date_from: datetime.date | None,
        date_to: datetime.date | None,
    ) -> Any:
        if status:
            stmt = stmt.where(RouteModel.status == status)
        if branch_id:
            stmt = stmt.where(RouteModel.branch_id == branch_id)
        if date_from:
            stmt = stmt.where(RouteModel.route_date >= date_from)
        if date_to:
            stmt = stmt.where(RouteModel.route_date <= date_to)
        return stmt

    def _to_domain(self, model: RouteModel, stop_models: list[RouteStopModel]) -> Route:
        stops = []
        for sm in stop_models:
            pod = None
            if sm.status == "delivered":
                pod = ProofOfDelivery(
                    otp_verified=sm.otp_verified,
                    signature_url=sm.signature_url,
                    photo_url=sm.photo_url,
                    gps_lat=sm.gps_lat,
                    gps_lon=sm.gps_lon,
                )
            stops.append(
                RouteStop(
                    stop_id=sm.id,
                    route_id=sm.route_id,
                    order_id=sm.order_id,
                    sequence_number=sm.sequence_number,
                    status=sm.status,
                    proof_of_delivery=pod,
                    failure_reason=sm.failure_reason,
                )
            )

        loaded_lines = [
            LoadedLine(
                cylinder_type_id=uuid.UUID(row["cylinder_type_id"]),
                quantity=int(row["quantity"]),
            )
            for row in (model.loaded_lines or [])
        ]

        route = Route(
            route_id=model.id,
            tenant_id=model.tenant_id,
            branch_id=model.branch_id,
            driver_id=model.driver_id,
            vehicle_id=model.vehicle_id,
            route_date=model.route_date,
            status=model.status,
            stops=stops,
            loaded_lines=loaded_lines,
            load_confirmed_at=model.load_confirmed_at,
            version=model.version,
        )
        self._uow.register_aggregate(route)
        return route
