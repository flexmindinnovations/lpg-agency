"""The customer-facing tool menu for the WhatsApp assistant (ADR-052).

Every tool acts for exactly one customer: the one whose phone number sent the
message. No tool takes a customer id, phone number or tenant from the model,
so a prompt-injected "show me order X for customer Y" has nothing to reach
another customer with: orders are looked up only among this customer's own
orders, and RLS scopes every query to the agency that owns the WhatsApp
number. That backend boundary, not the system prompt, is the safety line
(the same rule ADR-045 set for the AI Command Center).

Booking is two calls: `prepare_order` prices an order and stores it as a
pending quote, and `place_order` books the pending quote only when the quote
was made before the message being answered. The customer has therefore read
the quote and replied before anything is booked; the model cannot propose and
book in one turn.

Each tool opens its own `WhatsAppScope` (one transaction), because a
`UnitOfWork` commits once.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from lpg.application.ai.ports import ToolDeclaration
from lpg.application.common.errors import ApplicationError
from lpg.application.common.tenant import RequestTenantContext
from lpg.application.complaint.use_cases import RaiseComplaintCommand, RaiseComplaintUseCase
from lpg.application.order.use_cases import (
    CancelOrderCommand,
    CancelOrderUseCase,
    CreateOrderCommand,
    CreateOrderLine,
    CreateOrderUseCase,
)
from lpg.application.whatsapp.ports import PaymentLinkRequest, PendingOrderQuote
from lpg.config.logging import get_logger
from lpg.domain.common.base import DomainError
from lpg.domain.complaint.value_objects import ComplaintCategory, ComplaintPriority
from lpg.domain.order.order import DeliveryAddress
from lpg.domain.tenant.price_list import EffectivePriceResolver

if TYPE_CHECKING:
    from contextlib import AbstractAsyncContextManager
    from decimal import Decimal

    from lpg.application.whatsapp.ports import PaymentLinkPort, WhatsAppScope
    from lpg.domain.customer.customer import Customer, CustomerAddress
    from lpg.domain.order.order import Order

_logger = get_logger(__name__)

#: The booking channel recorded on orders placed here.
WHATSAPP_BOOKING_SOURCE = "whatsapp"

#: A quote older than this is stale (prices or the customer's mind may have
#: changed) and must be prepared again before it can be placed.
QUOTE_TTL = timedelta(minutes=30)

MAX_QUANTITY_PER_ORDER = 5
MAX_ADVANCE_BOOKING_DAYS = 7
_RECENT_ORDER_LOOKUP_LIMIT = 20
_PAYMENT_METHODS = ("cash", "upi", "online_gateway")
_OPEN_ORDER_STATUSES = frozenset(
    {"booked", "confirmed", "assigned", "ready_for_dispatch", "out_for_delivery"}
)

WhatsAppScopeFactory = Callable[[], "AbstractAsyncContextManager[WhatsAppScope]"]


class ToolInputError(Exception):
    """The model sent arguments a tool cannot use. The message goes back to
    the model, which can correct itself or ask the customer."""


@dataclass(frozen=True, slots=True)
class CustomerToolContext:
    """Who the tools act for, fixed by the inbound message, never by the
    model."""

    tenant_id: uuid.UUID
    customer_id: uuid.UUID
    customer_phone: str
    #: Recorded as `created_by`/`changed_by` on what the assistant writes: the
    #: customer's Customer App login when they have one, else the customer id
    #: itself (orders and complaints do not foreign-key these columns).
    actor_id: uuid.UUID
    #: When the message being answered arrived, on this server's clock. A
    #: pending quote is placeable only if it is older than this.
    turn_started_at: datetime
    scope_factory: WhatsAppScopeFactory
    payment_links: PaymentLinkPort


ToolHandler = Callable[[CustomerToolContext, dict[str, Any]], Awaitable[dict[str, object]]]


@dataclass(frozen=True, slots=True)
class CustomerTool:
    declaration: ToolDeclaration
    handler: ToolHandler


# ==========================================================================
# Argument helpers
# ==========================================================================


def _str_arg(args: dict[str, Any], name: str, *, required: bool = True) -> str | None:
    value = args.get(name)
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            msg = f"'{name}' is required."
            raise ToolInputError(msg)
        return None
    if not isinstance(value, str):
        msg = f"'{name}' must be a string."
        raise ToolInputError(msg)
    return value.strip()


def _uuid_arg(args: dict[str, Any], name: str, *, required: bool = True) -> uuid.UUID | None:
    raw = _str_arg(args, name, required=required)
    if raw is None:
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:
        msg = f"'{name}' must be an id returned by an earlier tool call."
        raise ToolInputError(msg) from None


def _int_arg(args: dict[str, Any], name: str, *, default: int) -> int:
    value = args.get(name, default)
    if isinstance(value, bool) or not isinstance(value, int):
        msg = f"'{name}' must be a whole number."
        raise ToolInputError(msg)
    return value


def _format_address(address: CustomerAddress) -> str:
    parts = [
        address.line_1,
        address.line_2,
        address.landmark,
        address.area,
        address.city,
        address.pincode,
    ]
    return ", ".join(part for part in parts if part)


def _delivery_addresses(customer: Customer) -> list[CustomerAddress]:
    return [a for a in customer.addresses if a.address_type in ("delivery", "both")]


async def _load_customer(scope: WhatsAppScope, ctx: CustomerToolContext) -> Customer:
    customer = await scope.customers.get_by_id(ctx.customer_id)
    if customer is None:
        msg = "The customer account could not be found."
        raise ToolInputError(msg)
    return customer


async def _find_own_order(scope: WhatsAppScope, ctx: CustomerToolContext, number: str) -> Order:
    """Looks an order up by its number among this customer's recent orders
    only, so a guessed number belonging to someone else is simply not
    found."""
    orders = await scope.orders.list_orders(
        skip=0, limit=_RECENT_ORDER_LOOKUP_LIMIT, customer_id=ctx.customer_id
    )
    wanted = number.strip().upper()
    for order in orders:
        if order.order_number is not None and order.order_number.upper() == wanted:
            return order
    msg = f"No recent order {number} was found for this customer."
    raise ToolInputError(msg)


async def _cylinder_prices(
    scope: WhatsAppScope, customer: Customer, cylinder_type_id: uuid.UUID
) -> Decimal | None:
    entries = await scope.price_lists.list_for_tenant_and_cylinder_type(
        customer.tenant_id, cylinder_type_id, customer.customer_type
    )
    resolved = EffectivePriceResolver.resolve(
        entries,
        cylinder_type_id=cylinder_type_id,
        customer_type=customer.customer_type,
        branch_id=customer.branch_id,
        at=datetime.now(UTC),
    )
    return resolved.price if resolved is not None else None


def _order_summary(order: Order) -> dict[str, object]:
    return {
        "order_number": order.order_number,
        "status": order.status,
        "requested_date": order.requested_date.date().isoformat(),
        "total_amount": str(order.total_amount) if order.total_amount is not None else None,
        "payment_method": order.payment_method_preference,
        "items": [
            {"cylinder_type_id": str(line.cylinder_type_id), "quantity": line.quantity_ordered}
            for line in order.lines
        ],
    }


# ==========================================================================
# Tools
# ==========================================================================


async def _get_my_account(ctx: CustomerToolContext, _args: dict[str, Any]) -> dict[str, object]:
    async with ctx.scope_factory() as scope:
        customer = await _load_customer(scope, ctx)
    return {
        "name": customer.full_name,
        "consumer_number": customer.consumer_number,
        "account_status": customer.status,
        "delivery_addresses": [
            {
                "address_id": str(address.id),
                "address": _format_address(address),
                "is_primary": address.is_primary,
            }
            for address in _delivery_addresses(customer)
        ],
    }


async def _list_cylinder_options(
    ctx: CustomerToolContext, _args: dict[str, Any]
) -> dict[str, object]:
    async with ctx.scope_factory() as scope:
        customer = await _load_customer(scope, ctx)
        cylinder_types = await scope.cylinder_types.list_for_tenant(ctx.tenant_id)
        options = []
        for cylinder_type in cylinder_types:
            if not cylinder_type.is_active:
                continue
            price = await _cylinder_prices(scope, customer, cylinder_type.id)
            options.append(
                {
                    "cylinder_type_id": str(cylinder_type.id),
                    "name": cylinder_type.name,
                    "weight_kg": str(cylinder_type.weight_kg),
                    "price": str(price) if price is not None else None,
                }
            )
    return {"cylinder_options": options, "currency": "INR"}


async def _prepare_order(ctx: CustomerToolContext, args: dict[str, Any]) -> dict[str, object]:
    cylinder_type_id = _uuid_arg(args, "cylinder_type_id")
    quantity = _int_arg(args, "quantity", default=1)
    address_id = _uuid_arg(args, "address_id", required=False)
    payment_method = _str_arg(args, "payment_method", required=False) or "cash"
    preferred_date_raw = _str_arg(args, "preferred_date", required=False)

    if not 1 <= quantity <= MAX_QUANTITY_PER_ORDER:
        msg = f"Quantity must be between 1 and {MAX_QUANTITY_PER_ORDER}."
        raise ToolInputError(msg)
    if payment_method not in _PAYMENT_METHODS:
        msg = f"payment_method must be one of {', '.join(_PAYMENT_METHODS)}."
        raise ToolInputError(msg)
    today = datetime.now(UTC).date()
    requested_date = today
    if preferred_date_raw is not None:
        try:
            requested_date = date.fromisoformat(preferred_date_raw)
        except ValueError:
            msg = "preferred_date must be a date in YYYY-MM-DD form."
            raise ToolInputError(msg) from None
        if not today <= requested_date <= today + timedelta(days=MAX_ADVANCE_BOOKING_DAYS):
            msg = f"preferred_date must be within the next {MAX_ADVANCE_BOOKING_DAYS} days."
            raise ToolInputError(msg)

    async with ctx.scope_factory() as scope:
        customer = await _load_customer(scope, ctx)
        if customer.status != "active":
            msg = (
                "This account is not active yet, so it cannot book refills on WhatsApp. "
                "The customer should contact the agency."
            )
            raise ToolInputError(msg)

        addresses = _delivery_addresses(customer)
        if address_id is not None:
            address = next((a for a in addresses if a.id == address_id), None)
        else:
            address = next((a for a in addresses if a.is_primary), None) or (
                addresses[0] if len(addresses) == 1 else None
            )
        if address is None:
            msg = (
                "Choose one of the customer's delivery addresses (get_my_account lists them)."
                if addresses
                else "This account has no delivery address; the customer should contact the agency."
            )
            raise ToolInputError(msg)

        cylinder_type = await scope.cylinder_types.get(cylinder_type_id)  # type: ignore[arg-type]
        if cylinder_type is None or not cylinder_type.is_active:
            msg = "Unknown cylinder type; use an id from list_cylinder_options."
            raise ToolInputError(msg)
        unit_price = await _cylinder_prices(scope, customer, cylinder_type.id)

        quote = PendingOrderQuote(
            cylinder_type_id=cylinder_type.id,
            cylinder_type_name=cylinder_type.name,
            quantity=quantity,
            address_id=address.id,
            address_line=_format_address(address),
            latitude=address.latitude,
            longitude=address.longitude,
            requested_date=requested_date,
            payment_method=payment_method,
            estimated_unit_price=unit_price,
            quoted_at=datetime.now(UTC),
        )
        await scope.conversations.set_pending_quote(ctx.customer_phone, quote)
        await scope.unit_of_work.commit()

    estimated_total = unit_price * quantity if unit_price is not None else None
    return {
        "quote": {
            "cylinder": cylinder_type.name,
            "quantity": quantity,
            "delivery_address": quote.address_line,
            "delivery_date": requested_date.isoformat(),
            "payment_method": payment_method,
            "estimated_unit_price": str(unit_price) if unit_price is not None else None,
            "estimated_total": str(estimated_total) if estimated_total is not None else None,
        },
        "next_step": (
            "Read this quote back to the customer and ask them to confirm. Call "
            "place_order only after they reply confirming it."
        ),
    }


async def _place_order(ctx: CustomerToolContext, _args: dict[str, Any]) -> dict[str, object]:
    async with ctx.scope_factory() as scope:
        quote = await scope.conversations.get_pending_quote(ctx.customer_phone)
        if quote is None:
            msg = "There is no pending order. Use prepare_order first."
            raise ToolInputError(msg)
        if quote.quoted_at >= ctx.turn_started_at:
            msg = (
                "The quote was only just prepared. Show it to the customer and wait for "
                "their confirmation before calling place_order."
            )
            raise ToolInputError(msg)
        if ctx.turn_started_at - quote.quoted_at > QUOTE_TTL:
            await scope.conversations.set_pending_quote(ctx.customer_phone, None)
            await scope.unit_of_work.commit()
            msg = "The quote has expired. Prepare it again and ask the customer to confirm."
            raise ToolInputError(msg)

        customer = await _load_customer(scope, ctx)
        # Cleared in the same transaction the order is created in (the use
        # case commits it), so a repeated "yes" cannot book the quote twice,
        # and a failed booking rolls the clear back with it.
        await scope.conversations.set_pending_quote(ctx.customer_phone, None)
        order = await CreateOrderUseCase(
            scope.orders, scope.unit_of_work, scope.order_numbers
        ).execute(
            CreateOrderCommand(
                tenant_id=ctx.tenant_id,
                branch_id=customer.branch_id,
                customer_id=customer.id,
                address_id=quote.address_id,
                delivery_address=DeliveryAddress(
                    address_line=quote.address_line,
                    latitude=quote.latitude,
                    longitude=quote.longitude,
                ),
                booking_source=WHATSAPP_BOOKING_SOURCE,
                requested_date=datetime.combine(quote.requested_date, datetime.min.time(), UTC),
                lines=[
                    CreateOrderLine(
                        cylinder_type_id=quote.cylinder_type_id, quantity=quote.quantity
                    )
                ],
                created_by=ctx.actor_id,
                payment_method_preference=quote.payment_method,
            )
        )
    return {
        "placed": True,
        "order_number": order.order_number,
        "status": order.status,
        "payment_method": order.payment_method_preference,
        "note": "The agency confirms the final price when it confirms the order.",
    }


async def _list_my_orders(ctx: CustomerToolContext, args: dict[str, Any]) -> dict[str, object]:
    limit = _int_arg(args, "limit", default=5)
    limit = max(1, min(limit, 10))
    async with ctx.scope_factory() as scope:
        orders = await scope.orders.list_orders(skip=0, limit=limit, customer_id=ctx.customer_id)
    return {"orders": [_order_summary(order) for order in orders]}


async def _track_order(ctx: CustomerToolContext, args: dict[str, Any]) -> dict[str, object]:
    number = _str_arg(args, "order_number")
    async with ctx.scope_factory() as scope:
        order = await _find_own_order(scope, ctx, number)  # type: ignore[arg-type]
        history = await scope.orders.list_status_history(order.id)
        delivery: dict[str, object] | None = None
        if order.route_stop_id is not None:
            owner = await scope.routes.get_stop_owner(order.route_stop_id)
            if owner is not None:
                route = await scope.routes.get_by_id(owner.route_id)
                driver = await scope.drivers.get_by_id(owner.driver_id)
                employee = (
                    await scope.employees.get_by_id(driver.employee_id)
                    if driver is not None
                    else None
                )
                vehicle = await scope.vehicles.get_by_id(owner.vehicle_id)
                delivery = {
                    "route_status": route.status if route is not None else None,
                    "driver_name": (
                        f"{employee.first_name} {employee.last_name}".strip()
                        if employee is not None
                        else None
                    ),
                    "vehicle_number": vehicle.registration_number if vehicle else None,
                }
    return {
        **_order_summary(order),
        "delivery_address": order.delivery_address.address_line,
        "status_history": [
            {"status": entry.to_status, "at": entry.changed_at.isoformat()} for entry in history
        ],
        "delivery": delivery,
    }


async def _cancel_order(ctx: CustomerToolContext, args: dict[str, Any]) -> dict[str, object]:
    number = _str_arg(args, "order_number")
    reason = _str_arg(args, "reason", required=False) or "Cancelled by customer on WhatsApp"
    async with ctx.scope_factory() as scope:
        order = await _find_own_order(scope, ctx, number)  # type: ignore[arg-type]
        if order.status not in _OPEN_ORDER_STATUSES:
            msg = f"Order {number} is {order.status} and can no longer be cancelled."
            raise ToolInputError(msg)
        result = await CancelOrderUseCase(
            scope.orders,
            scope.routes,
            scope.inventory,
            scope.cancellations,
            scope.unit_of_work,
        ).execute(
            CancelOrderCommand(order_id=order.id, reason=reason[:500], cancelled_by=ctx.actor_id)
        )
    if result.pending_approval:
        return {
            "cancelled": False,
            "pending_approval": True,
            "note": "The order is already on its way, so the agency must approve the cancellation.",
        }
    return {"cancelled": True, "order_number": order.order_number}


async def _get_payment_link(ctx: CustomerToolContext, args: dict[str, Any]) -> dict[str, object]:
    number = _str_arg(args, "order_number")
    async with ctx.scope_factory() as scope:
        order = await _find_own_order(scope, ctx, number)  # type: ignore[arg-type]
        customer = await _load_customer(scope, ctx)
    if order.status not in _OPEN_ORDER_STATUSES and order.status != "delivered":
        msg = f"Order {number} is {order.status}; there is nothing to pay."
        raise ToolInputError(msg)
    link = await ctx.payment_links.create_payment_link(
        PaymentLinkRequest(
            order_id=order.id,
            order_number=order.order_number or "",
            amount=order.total_amount,
            customer_name=customer.full_name,
            customer_phone=customer.phone_number,
        )
    )
    if link is None:
        return {
            "available": False,
            "note": "Online payment is not available for this order yet. "
            "The customer can pay by cash or UPI on delivery.",
        }
    return {"available": True, "payment_url": link.url, "amount": str(link.amount)}


_COMPLAINT_CATEGORIES = {category.value: category for category in ComplaintCategory}


async def _raise_complaint(ctx: CustomerToolContext, args: dict[str, Any]) -> dict[str, object]:
    raw_category = _str_arg(args, "category")
    description = _str_arg(args, "description")
    number = _str_arg(args, "order_number", required=False)
    category = _COMPLAINT_CATEGORIES.get(raw_category or "")
    if category is None:
        msg = f"category must be one of {', '.join(_COMPLAINT_CATEGORIES)}."
        raise ToolInputError(msg)

    async with ctx.scope_factory() as scope:
        order_id = (await _find_own_order(scope, ctx, number)).id if number else None
        complaint_id = await RaiseComplaintUseCase(
            scope.complaints, scope.complaint_numbers
        ).execute(
            RequestTenantContext(tenant_id=ctx.tenant_id, user_id=ctx.actor_id),
            RaiseComplaintCommand(
                customer_id=ctx.customer_id,
                category=category,
                priority=ComplaintPriority.MEDIUM,
                description=f"[WhatsApp] {description}"[:2000],
                order_id=order_id,
            ),
        )
    return {"raised": True, "complaint_id": str(complaint_id)}


def _schema(properties: dict[str, object], required: list[str] | None = None) -> dict[str, object]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


_ORDER_NUMBER = {"type": "string", "description": "The order number, e.g. ORD-000123."}

CUSTOMER_TOOLS: tuple[CustomerTool, ...] = (
    CustomerTool(
        ToolDeclaration(
            name="get_my_account",
            description=(
                "The customer's name, consumer number, account status and saved "
                "delivery addresses (with address ids)."
            ),
            parameters_schema=_schema({}),
        ),
        _get_my_account,
    ),
    CustomerTool(
        ToolDeclaration(
            name="list_cylinder_options",
            description=(
                "The cylinder types the customer can order, with ids and their "
                "current price in INR."
            ),
            parameters_schema=_schema({}),
        ),
        _list_cylinder_options,
    ),
    CustomerTool(
        ToolDeclaration(
            name="prepare_order",
            description=(
                "Price a refill order and save it as a pending quote. Does NOT book it. "
                "Show the returned quote to the customer and ask them to confirm."
            ),
            parameters_schema=_schema(
                {
                    "cylinder_type_id": {
                        "type": "string",
                        "description": "An id from list_cylinder_options.",
                    },
                    "quantity": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": MAX_QUANTITY_PER_ORDER,
                    },
                    "address_id": {
                        "type": "string",
                        "description": "A delivery address id from get_my_account. "
                        "Omit to use the primary address.",
                    },
                    "payment_method": {
                        "type": "string",
                        "enum": list(_PAYMENT_METHODS),
                        "description": "cash or upi on delivery, or online_gateway to pay by link.",
                    },
                    "preferred_date": {
                        "type": "string",
                        "description": "Delivery date, YYYY-MM-DD. Omit for today.",
                    },
                },
                ["cylinder_type_id", "quantity"],
            ),
        ),
        _prepare_order,
    ),
    CustomerTool(
        ToolDeclaration(
            name="place_order",
            description=(
                "Book the pending quote from prepare_order. Only call this after the "
                "customer has replied confirming the quote."
            ),
            parameters_schema=_schema({}),
        ),
        _place_order,
    ),
    CustomerTool(
        ToolDeclaration(
            name="list_my_orders",
            description="The customer's most recent orders, newest first, with status.",
            parameters_schema=_schema({"limit": {"type": "integer", "minimum": 1, "maximum": 10}}),
        ),
        _list_my_orders,
    ),
    CustomerTool(
        ToolDeclaration(
            name="track_order",
            description=(
                "Live status of one of the customer's orders: status history, and the "
                "driver and vehicle once it is assigned."
            ),
            parameters_schema=_schema({"order_number": _ORDER_NUMBER}, ["order_number"]),
        ),
        _track_order,
    ),
    CustomerTool(
        ToolDeclaration(
            name="cancel_order",
            description=(
                "Cancel one of the customer's open orders. Confirm with the customer first."
            ),
            parameters_schema=_schema(
                {"order_number": _ORDER_NUMBER, "reason": {"type": "string"}},
                ["order_number"],
            ),
        ),
        _cancel_order,
    ),
    CustomerTool(
        ToolDeclaration(
            name="get_payment_link",
            description="An online payment link for one of the customer's orders, if available.",
            parameters_schema=_schema({"order_number": _ORDER_NUMBER}, ["order_number"]),
        ),
        _get_payment_link,
    ),
    CustomerTool(
        ToolDeclaration(
            name="raise_complaint",
            description="Log a complaint for the agency's staff to follow up.",
            parameters_schema=_schema(
                {
                    "category": {"type": "string", "enum": list(_COMPLAINT_CATEGORIES)},
                    "description": {
                        "type": "string",
                        "description": "What happened, in the customer's words.",
                    },
                    "order_number": {
                        **_ORDER_NUMBER,
                        "description": "The related order, if any.",
                    },
                },
                ["category", "description"],
            ),
        ),
        _raise_complaint,
    ),
)


async def execute_customer_tool(
    ctx: CustomerToolContext, name: str, arguments: dict[str, Any]
) -> dict[str, object]:
    """Runs one tool call. Every failure comes back to the model as an
    `error` it can explain to the customer; nothing here raises."""
    tool = next((t for t in CUSTOMER_TOOLS if t.declaration.name == name), None)
    if tool is None:
        return {"error": f"Tool '{name}' is not available."}
    try:
        return await tool.handler(ctx, arguments)
    except ToolInputError as exc:
        return {"error": str(exc)}
    except (ApplicationError, DomainError) as exc:
        return {"error": str(exc)}
    except Exception:
        _logger.exception("whatsapp_tool_failed", tool=name)
        return {"error": "Something went wrong on our side. Please try again shortly."}
