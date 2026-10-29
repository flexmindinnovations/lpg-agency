"""Staff reminders to a customer about their order.

- `POST /orders/{order_id}/reminders` — push a short message (a preset or
  free text) to the customer's app. `orders:dispatch`.
- `GET /orders/{order_id}/reminders` — what has been sent, newest first.
  `orders:read`, staff only (customers get the push, not the log).
- `GET /orders/reminder-presets` — the ready-made messages.

Rate limited per order (see `lpg.application.order.reminders`); each send is
recorded, which is what the order page's timeline shows.
"""

from __future__ import annotations

import typing
import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from lpg.api.v1.dependencies.admin import get_employee_repository
from lpg.api.v1.dependencies.customer import get_customer_repository
from lpg.api.v1.dependencies.delivery import get_driver_repository, get_route_repository
from lpg.api.v1.dependencies.identity import get_current_principal, require_permission
from lpg.api.v1.dependencies.order import (
    get_order_reminder_repository,
    get_order_repository,
    get_reminder_notifier,
)
from lpg.application.common.errors import ConflictError, NotFoundError
from lpg.application.customer.ports import CustomerRepository
from lpg.application.delivery.ports import DriverRepository, RouteRepository
from lpg.application.identity.ports import AuthenticatedPrincipal
from lpg.application.order.ports import OrderRepository
from lpg.application.order.reminders import (
    CUSTOM,
    PRESETS,
    Notifier,
    OrderReminderRepository,
    check_rate_limit,
    compose_message,
    new_reminder,
)
from lpg.application.tenant_admin.ports import EmployeeRepository

if typing.TYPE_CHECKING:
    from lpg.application.order.reminders import OrderReminder

router = APIRouter(tags=["Orders"])


class ReminderPresetResponse(BaseModel):
    key: str
    label: str


class SendReminderRequest(BaseModel):
    preset: Literal["delivery_today", "on_the_way", "empty_ready", "payment_due", "custom"]
    message: str | None = Field(default=None, max_length=600)


class ReminderResponse(BaseModel):
    id: uuid.UUID
    sent_by: uuid.UUID
    preset: str
    message: str
    sent_at: datetime


def _to_response(reminder: OrderReminder) -> ReminderResponse:
    return ReminderResponse(
        id=reminder.id,
        sent_by=reminder.sent_by,
        preset=reminder.preset,
        message=reminder.message,
        sent_at=reminder.sent_at,
    )


async def _visible_order(
    order_id: uuid.UUID,
    principal: AuthenticatedPrincipal,
    order_repository: OrderRepository,
) -> typing.Any:
    order = await order_repository.get_by_id(order_id)
    branch_scoped = principal.role in ("dispatcher", "manager")
    if order is None or (branch_scoped and order.branch_id != principal.branch_id):
        msg = "Order not found."
        raise NotFoundError(msg, order_id=str(order_id))
    return order


@router.get(
    "/orders/reminder-presets",
    response_model=list[ReminderPresetResponse],
    dependencies=[Depends(require_permission("orders:dispatch"))],
    summary="The ready-made reminder messages",
)
async def list_reminder_presets() -> list[ReminderPresetResponse]:
    return [ReminderPresetResponse(key=key, label=label) for key, (label, _) in PRESETS.items()]


@router.get(
    "/orders/{order_id}/reminders",
    response_model=list[ReminderResponse],
    dependencies=[Depends(require_permission("orders:read"))],
    summary="Reminders sent to the customer about this order",
)
async def list_order_reminders(
    order_id: uuid.UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    order_repository: Annotated[OrderRepository, Depends(get_order_repository)],
    repository: Annotated[OrderReminderRepository, Depends(get_order_reminder_repository)],
) -> list[ReminderResponse]:
    if principal.role in ("customer", "driver"):
        msg = "Order not found."
        raise NotFoundError(msg, order_id=str(order_id))
    await _visible_order(order_id, principal, order_repository)
    return [_to_response(r) for r in await repository.list_for_order(order_id)]


@router.post(
    "/orders/{order_id}/reminders",
    response_model=ReminderResponse,
    status_code=201,
    dependencies=[Depends(require_permission("orders:dispatch"))],
    summary="Send the customer a reminder about this order",
    responses={
        409: {"description": "The order is finished or the customer has no app login."},
        429: {"description": "Too many reminders for this order."},
    },
)
async def send_order_reminder(
    order_id: uuid.UUID,
    body: SendReminderRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    order_repository: Annotated[OrderRepository, Depends(get_order_repository)],
    customer_repository: Annotated[CustomerRepository, Depends(get_customer_repository)],
    driver_repository: Annotated[DriverRepository, Depends(get_driver_repository)],
    route_repository: Annotated[RouteRepository, Depends(get_route_repository)],
    employee_repository: Annotated[EmployeeRepository, Depends(get_employee_repository)],
    repository: Annotated[OrderReminderRepository, Depends(get_order_reminder_repository)],
    notifier: Annotated[Notifier | None, Depends(get_reminder_notifier)],
) -> ReminderResponse:
    order = await _visible_order(order_id, principal, order_repository)
    if order.status in ("delivered", "closed", "cancelled"):
        msg = "This order is finished, so there is nothing to remind the customer about."
        raise ConflictError(msg)
    customer = await customer_repository.get_by_id(order.customer_id)
    if customer is None or customer.identity_user_id is None:
        msg = (
            "This customer has not signed in to the app, so they cannot receive "
            "notifications. Call them instead."
        )
        raise ConflictError(msg)

    driver_name: str | None = None
    if body.preset == "on_the_way":
        owner = (
            await route_repository.get_stop_owner(order.route_stop_id)
            if order.route_stop_id is not None
            else None
        )
        driver = await driver_repository.get_by_id(owner.driver_id) if owner else None
        if driver is None:
            msg = "This order is not on a trip yet, so it cannot be 'on the way'."
            raise ConflictError(msg)
        employee = await employee_repository.get_by_id(driver.employee_id)
        driver_name = employee.first_name if employee is not None else None

    message = compose_message(
        body.preset,
        body.message,
        order_ref=order.order_number or "your order",
        driver_name=driver_name,
    )
    check_rate_limit(await repository.list_for_order(order_id), datetime.now(UTC))

    reminder = new_reminder(
        order_id=order_id,
        sent_by=typing.cast("uuid.UUID", principal.user_id),
        preset=CUSTOM if body.preset == CUSTOM else body.preset,
        message=message,
    )
    await repository.add(reminder, principal.tenant_id)

    if notifier is not None:
        await notifier.notify(
            {
                "type": "order_reminder",
                "tenant_id": str(principal.tenant_id),
                "order_id": str(order_id),
                "message": message,
            }
        )
    return _to_response(reminder)
