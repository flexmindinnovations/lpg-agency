"""Turns a notification payload into recipients and readable text.

A payload is what an event handler or a cron knows: a type plus the ids it
is about (`order_id`, `route_id`, `complaint_id`, ...). This module looks
those up — inside the caller's tenant-scoped unit of work, so RLS keeps
every read inside the tenant — and produces a `PreparedNotification`: who
gets it, the title/body from `catalog.py`, and what a click should open.

Recipients follow the type's `Audience`:

- customer: the order's (or payment's) customer login;
- driver: the login of the driver whose trip the event is on;
- staff: everyone active holding the type's permission, limited to the
  event's branch for staff pinned to a branch (tenant-wide staff see all);
- assignee: the one staff member a complaint was just assigned to.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import structlog

from lpg.infrastructure.notification.catalog import (
    FAILED_DELIVERY_REASON_LABELS,
    Audience,
    NotificationSpec,
    spec_for,
)

if TYPE_CHECKING:
    from lpg.domain.delivery.route import Route
    from lpg.domain.order.order import Order
    from lpg.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

_logger = structlog.get_logger(__name__)

#: Route statuses in which the driver already has the trip in hand — a
#: change then is news to them. While a trip is still `planned` the office
#: is building it, and the one `route_ready` covers every stop added.
_DRIVER_LIVE_ROUTE_STATUSES = frozenset({"loaded", "in_progress"})


@dataclass(frozen=True, slots=True)
class PreparedNotification:
    notification_type: str
    spec: NotificationSpec
    recipient_user_ids: tuple[uuid.UUID, ...]
    title: str
    body: str
    reference_type: str
    reference_id: uuid.UUID | None
    facts: dict[str, str] = field(default_factory=dict)
    #: Overrides `spec.push` for types whose push is decided per instance.
    push: bool = False


def _humanize(value: str) -> str:
    """`ShortDelivery` -> `short delivery`."""
    return re.sub(r"(?<!^)(?=[A-Z])", " ", value).replace("_", " ").lower()


def _uuid(payload: dict[str, Any], key: str) -> uuid.UUID | None:
    raw = payload.get(key)
    if not raw:
        return None
    try:
        return uuid.UUID(str(raw))
    except ValueError:
        return None


class NotificationResolver:
    """Resolves payloads against one tenant-scoped unit of work."""

    def __init__(self, uow: SqlAlchemyUnitOfWork, tenant_id: uuid.UUID) -> None:
        self._uow = uow
        self._tenant_id = tenant_id

    async def prepare(self, payload: dict[str, Any]) -> PreparedNotification | None:
        notification_type = str(payload.get("type", ""))
        spec = spec_for(notification_type)
        if spec is None:
            _logger.warning("notification_type_unknown", notification_type=notification_type)
            return None

        facts: dict[str, str] = {
            k: str(v) for k, v in payload.items() if isinstance(v, (str, int)) and v != ""
        }
        branch_id: uuid.UUID | None = None
        customer_id: uuid.UUID | None = None
        route: Route | None = None
        reference_id: uuid.UUID | None = None
        push = spec.push

        invoice_id = _uuid(payload, "invoice_id")
        if invoice_id is not None:
            invoice = await self._invoice(invoice_id)
            if invoice is not None:
                if invoice.invoice_number:
                    facts["invoice_ref"] = invoice.invoice_number
                payload = {"order_id": str(invoice.order_id), **payload}

        order = await self._order(payload)
        if order is not None:
            branch_id = order.branch_id
            customer_id = order.customer_id
            reference_id = order.id
            if order.order_number:
                facts["order_ref"] = order.order_number
            if order.route_stop_id is not None and spec.audience is Audience.DRIVER:
                route = await self._route_for_stop(order.route_stop_id)
            if spec.audience is Audience.DRIVER and order.delivery_address.address_line:
                facts["address"] = order.delivery_address.address_line
        elif "order_id" in payload and payload.get("order_id"):
            _logger.warning("notification_order_not_found", order_id=payload.get("order_id"))
            return None

        if "reason_code" in payload:
            code = str(payload["reason_code"])
            facts["reason"] = FAILED_DELIVERY_REASON_LABELS.get(code, _humanize(code))

        route_id = _uuid(payload, "route_id")
        if route is None and route_id is not None:
            route = await self._route_repo().get_by_id(route_id)
        if route is not None:
            branch_id = branch_id or route.branch_id
            facts["stop_count"] = str(len([s for s in route.stops if s.status != "cancelled"]))
            await self._add_route_facts(route, facts)
            if spec.reference_type == "route":
                reference_id = route.id

        complaint_id = _uuid(payload, "complaint_id")
        if complaint_id is not None:
            complaint = await self._complaint(complaint_id)
            if complaint is None:
                return None
            customer_id = complaint.customer_id
            reference_id = complaint.id
            facts["complaint_ref"] = complaint.complaint_number or "A complaint"
            facts["category"] = _humanize(str(complaint.category))
            facts["priority"] = str(complaint.priority).lower()

        if "customer_id" in payload and customer_id is None:
            customer_id = _uuid(payload, "customer_id")
        customer = await self._customer(customer_id) if customer_id else None
        if customer is not None:
            facts["customer_name"] = customer.full_name
            if spec.reference_type == "customer":
                reference_id = customer.id
            branch_id = branch_id or customer.branch_id

        if spec.reference_type in ("cash_handover", "compliance_document", "inventory_location"):
            key = {
                "cash_handover": "cash_handover_id",
                "compliance_document": "document_id",
                "inventory_location": "inventory_location_id",
            }[spec.reference_type]
            reference_id = _uuid(payload, key)
        if spec.reference_type == "inventory_location" and reference_id is not None:
            branch_id = await self._add_stock_facts(reference_id, payload, facts)
        if spec.reference_type == "price_list_proposal":
            reference_id = None

        recipients: list[uuid.UUID] = []
        if spec.audience is Audience.CUSTOMER:
            if customer is not None and customer.identity_user_id is not None:
                recipients = [customer.identity_user_id]
        elif spec.audience is Audience.DRIVER:
            recipients, push = await self._driver_recipients(
                notification_type, payload, route, push
            )
        elif spec.audience is Audience.ASSIGNEE:
            assignee = _uuid(payload, "assigned_to")
            if assignee is not None and await self._recipient_repo().is_active_staff(
                tenant_id=self._tenant_id, user_id=assignee
            ):
                recipients = [assignee]
        else:
            assert spec.permission is not None
            recipients = await self._recipient_repo().staff_with_permission(
                tenant_id=self._tenant_id,
                permission_code=spec.permission,
                branch_id=branch_id,
            )
            # The person who caused the event doesn't need telling about it.
            actor = _uuid(payload, "actor_id")
            recipients = [r for r in recipients if r != actor]

        if not recipients:
            _logger.info("notification_no_recipients", notification_type=notification_type)
            return None

        return PreparedNotification(
            notification_type=notification_type,
            spec=spec,
            recipient_user_ids=tuple(dict.fromkeys(recipients)),
            title=spec.title,
            body=spec.body(facts),
            reference_type=spec.reference_type,
            reference_id=reference_id,
            facts=facts,
            push=push,
        )

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------

    async def _driver_recipients(
        self,
        notification_type: str,
        payload: dict[str, Any],
        route: Route | None,
        push: bool,
    ) -> tuple[list[uuid.UUID], bool]:
        driver_id = route.driver_id if route is not None else _uuid(payload, "driver_id")
        if driver_id is None:
            return [], push
        # Mid-trip changes only matter once the driver has the trip; while
        # it is being built `route_ready` will cover it.
        if notification_type in ("driver_assigned", "stop_cancelled", "route_resequenced") and (
            route is None or route.status not in _DRIVER_LIVE_ROUTE_STATUSES
        ):
            return [], push
        if notification_type == "driver_assigned":
            push = route is not None and route.status == "in_progress"
        from lpg.infrastructure.persistence.repositories.driver import SqlAlchemyDriverRepository

        driver = await SqlAlchemyDriverRepository(self._uow).get_by_id(driver_id)
        if driver is None or driver.identity_user_id is None:
            return [], push
        return [driver.identity_user_id], push

    async def _order(self, payload: dict[str, Any]) -> Order | None:
        order_id = _uuid(payload, "order_id")
        if order_id is None:
            return None
        from lpg.infrastructure.persistence.repositories.order import SqlAlchemyOrderRepository

        return await SqlAlchemyOrderRepository(self._uow).get_by_id(order_id)

    def _route_repo(self) -> Any:
        from lpg.infrastructure.persistence.repositories.route import SqlAlchemyRouteRepository

        return SqlAlchemyRouteRepository(self._uow)

    async def _route_for_stop(self, route_stop_id: uuid.UUID) -> Route | None:
        repo = self._route_repo()
        owner = await repo.get_stop_owner(route_stop_id)
        if owner is None:
            return None
        route: Route | None = await repo.get_by_id(owner.route_id)
        return route

    async def _add_route_facts(self, route: Route, facts: dict[str, str]) -> None:
        from lpg.infrastructure.persistence.repositories.driver import SqlAlchemyDriverRepository
        from lpg.infrastructure.persistence.repositories.employee import (
            SqlAlchemyEmployeeRepository,
        )
        from lpg.infrastructure.persistence.repositories.vehicle import (
            SqlAlchemyVehicleRepository,
        )

        vehicle = await SqlAlchemyVehicleRepository(self._uow).get_by_id(route.vehicle_id)
        if vehicle is not None:
            facts["vehicle_ref"] = vehicle.registration_number
        driver = await SqlAlchemyDriverRepository(self._uow).get_by_id(route.driver_id)
        if driver is not None:
            employee = await SqlAlchemyEmployeeRepository(self._uow).get_by_id(driver.employee_id)
            if employee is not None:
                facts["driver_name"] = f"{employee.first_name} {employee.last_name}".strip()

    async def _invoice(self, invoice_id: uuid.UUID) -> Any:
        from lpg.infrastructure.persistence.repositories.accounting import (
            SqlAlchemyInvoiceRepository,
        )

        return await SqlAlchemyInvoiceRepository(self._uow).get_by_id(invoice_id)

    async def _complaint(self, complaint_id: uuid.UUID) -> Any:
        from lpg.infrastructure.persistence.repositories.complaint import (
            SqlAlchemyComplaintRepository,
        )

        return await SqlAlchemyComplaintRepository(self._uow).get_by_id(
            self._tenant_id, complaint_id
        )

    async def _customer(self, customer_id: uuid.UUID) -> Any:
        from lpg.config.settings import get_settings
        from lpg.infrastructure.persistence.repositories.customer import (
            SqlAlchemyCustomerRepository,
        )
        from lpg.infrastructure.security.field_encryption import FernetFieldEncryptor

        repo = SqlAlchemyCustomerRepository(self._uow, FernetFieldEncryptor(get_settings()))
        return await repo.get_by_id(customer_id)

    async def _add_stock_facts(
        self, location_id: uuid.UUID, payload: dict[str, Any], facts: dict[str, str]
    ) -> uuid.UUID | None:
        """Names the godown and cylinder; returns the godown's branch."""
        from lpg.infrastructure.persistence.repositories.inventory import (
            SqlAlchemyInventoryLocationRepository,
        )
        from lpg.infrastructure.persistence.repositories.tenant import (
            SqlAlchemyCylinderTypeRepository,
            SqlAlchemyWarehouseRepository,
        )

        branch_id: uuid.UUID | None = None
        location = await SqlAlchemyInventoryLocationRepository(self._uow).get_by_id(location_id)
        if location is not None and location.location_type == "warehouse":
            warehouse = await SqlAlchemyWarehouseRepository(self._uow).get(location.location_ref_id)
            if warehouse is not None:
                facts["location_name"] = warehouse.name
                branch_id = warehouse.branch_id
        cylinder_type_id = _uuid(payload, "cylinder_type_id")
        if cylinder_type_id is not None:
            cylinder = await SqlAlchemyCylinderTypeRepository(self._uow).get(cylinder_type_id)
            if cylinder is not None:
                facts["cylinder_name"] = cylinder.name
        return branch_id

    def _recipient_repo(self) -> Any:
        from lpg.infrastructure.persistence.repositories.notification import (
            SqlAlchemyNotificationRecipientRepository,
        )

        return SqlAlchemyNotificationRecipientRepository(self._uow.session)
