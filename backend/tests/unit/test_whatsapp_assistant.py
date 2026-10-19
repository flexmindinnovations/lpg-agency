"""Unit tests for the WhatsApp customer assistant (ADR-055):
`HandleInboundWhatsAppMessageUseCase` and its customer tools, against
in-memory fakes. The model is a scripted fake that calls tools in a fixed
order, so these tests pin the backend's own rules (dedupe, kill switch,
budget, customer scoping, the two-step booking guard) independent of any
model's behaviour."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock

import pytest

from lpg.application.ai.ports import (
    AgentRunResult,
    AssistantRun,
    ConversationTurn,
    ToolDeclaration,
    ToolExecutor,
)
from lpg.application.whatsapp.ports import (
    ConversationEntry,
    InboundWhatsAppMessage,
    PaymentLink,
    PaymentLinkRequest,
    PendingOrderQuote,
    WhatsAppScope,
)
from lpg.application.whatsapp.tools import QUOTE_TTL, CustomerToolContext, execute_customer_tool
from lpg.application.whatsapp.use_cases import (
    UNAVAILABLE_REPLY,
    UNKNOWN_CUSTOMER_REPLY,
    HandleInboundWhatsAppMessageUseCase,
)
from lpg.domain.customer.customer import Customer, CustomerAddress
from lpg.domain.order.order import DeliveryAddress, Order, OrderLine
from lpg.domain.tenant.cylinder_type import CylinderType
from lpg.domain.tenant.price_list import PriceListEntry
from lpg.domain.tenant.tenant_configuration import TenantConfiguration

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

TENANT_ID = uuid.uuid4()
PHONE = "+919876543210"


# ==========================================================================
# Fakes
# ==========================================================================


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self) -> FakeUnitOfWork:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1

    def collect_events(self) -> Sequence[Any]:
        return ()


@dataclass
class FakeConversations:
    seen_ids: set[str] = field(default_factory=set)
    log: list[tuple[str, str, ConversationEntry]] = field(default_factory=list)
    quotes: dict[str, PendingOrderQuote] = field(default_factory=dict)

    async def record_inbound(self, message: InboundWhatsAppMessage) -> bool:
        if message.wa_message_id in self.seen_ids:
            return False
        self.seen_ids.add(message.wa_message_id)
        self.log.append(
            (message.from_phone, "received", ConversationEntry("inbound", message.text, _now()))
        )
        return True

    async def record_outbound(
        self,
        *,
        to_phone: str,
        body: str,
        wa_message_id: str | None,  # noqa: ARG002
        status: str,
    ) -> None:
        self.log.append((to_phone, status, ConversationEntry("outbound", body, _now())))

    async def list_recent(
        self, phone: str, *, since: datetime, limit: int
    ) -> list[ConversationEntry]:
        entries = [e for p, _s, e in self.log if p == phone and e.created_at >= since]
        return entries[-limit:]

    async def get_pending_quote(self, phone: str) -> PendingOrderQuote | None:
        return self.quotes.get(phone)

    async def set_pending_quote(self, phone: str, quote: PendingOrderQuote | None) -> None:
        if quote is None:
            self.quotes.pop(phone, None)
        else:
            self.quotes[phone] = quote


@dataclass
class FakeCustomers:
    customers: list[Customer]

    async def get_by_id(self, customer_id: uuid.UUID) -> Customer | None:
        return next((c for c in self.customers if c.id == customer_id), None)

    async def get_by_phone(self, phone_number: str) -> Customer | None:
        return next((c for c in self.customers if c.phone_number == phone_number), None)


@dataclass
class FakeOrders:
    orders: list[Order] = field(default_factory=list)

    def next_id(self) -> uuid.UUID:
        return uuid.uuid4()

    async def save(self, order: Order) -> None:
        if order not in self.orders:
            self.orders.insert(0, order)

    async def get_by_id(self, order_id: uuid.UUID) -> Order | None:
        return next((o for o in self.orders if o.id == order_id), None)

    async def list_orders(
        self, skip: int = 0, limit: int = 50, customer_id: uuid.UUID | None = None, **_: Any
    ) -> list[Order]:
        rows = [o for o in self.orders if customer_id is None or o.customer_id == customer_id]
        return rows[skip : skip + limit]

    async def list_status_history(self, order_id: uuid.UUID) -> list[Any]:  # noqa: ARG002
        return []


class FakeOrderNumbers:
    def __init__(self) -> None:
        self._n = 0

    async def next(self) -> str:
        self._n += 1
        return f"ORD{self._n:06d}"


@dataclass
class FakeCylinderTypes:
    types: list[CylinderType]

    async def get(self, cylinder_type_id: uuid.UUID) -> CylinderType | None:
        return next((t for t in self.types if t.id == cylinder_type_id), None)

    async def list_for_tenant(self, tenant_id: uuid.UUID) -> list[CylinderType]:  # noqa: ARG002
        return self.types


@dataclass
class FakePriceLists:
    entries: list[PriceListEntry]

    async def list_for_tenant_and_cylinder_type(
        self, tenant_id: uuid.UUID, cylinder_type_id: uuid.UUID, customer_type: str
    ) -> list[PriceListEntry]:
        return [
            e
            for e in self.entries
            if e.tenant_id == tenant_id
            and e.cylinder_type_id == cylinder_type_id
            and e.customer_type == customer_type
        ]

    async def list_for_tenant(self, tenant_id: uuid.UUID) -> list[PriceListEntry]:
        return [e for e in self.entries if e.tenant_id == tenant_id]


@dataclass
class FakeBranchStock:
    available: dict[uuid.UUID, int]

    async def lock_branch_for_booking(self, branch_id: uuid.UUID) -> None:
        pass

    async def available_filled_by_cylinder_type(
        self,
        branch_id: uuid.UUID,  # noqa: ARG002
        *,
        exclude_order_id: uuid.UUID | None = None,  # noqa: ARG002
    ) -> dict[uuid.UUID, int]:
        return dict(self.available)


@dataclass
class FakeTenantConfiguration:
    values: dict[str, Any]

    async def list_for_tenant_and_key(
        self, tenant_id: uuid.UUID, config_key: str
    ) -> list[TenantConfiguration]:
        if config_key not in self.values:
            return []
        return [
            TenantConfiguration(
                uuid.uuid4(),
                tenant_id,
                config_key,
                self.values[config_key],
                _now() - timedelta(days=1),
            )
        ]


@dataclass
class FakeAssistantRuns:
    runs: list[AssistantRun] = field(default_factory=list)
    used_today: int = 0

    def next_id(self) -> uuid.UUID:
        return uuid.uuid4()

    async def add(self, run: AssistantRun) -> None:
        self.runs.append(run)

    async def get_todays_token_usage(self) -> int:
        return self.used_today


class FakeSender:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def send_text(self, *, phone_number_id: str, to: str, body: str) -> str | None:  # noqa: ARG002
        self.sent.append((to, body))
        return f"wamid.out{len(self.sent)}"


class FakePaymentLinks:
    def __init__(self, link: PaymentLink | None = None) -> None:
        self.link = link
        self.requests: list[PaymentLinkRequest] = []

    async def create_payment_link(self, request: PaymentLinkRequest) -> PaymentLink | None:
        self.requests.append(request)
        return self.link


@dataclass
class World:
    customer: Customer
    other_customer: Customer
    cylinder: CylinderType
    conversations: FakeConversations
    orders: FakeOrders
    config: FakeTenantConfiguration
    runs: FakeAssistantRuns
    stock: FakeBranchStock
    uows: list[FakeUnitOfWork] = field(default_factory=list)
    actors: list[uuid.UUID | None] = field(default_factory=list)

    def scope_factories(self, actor_id: uuid.UUID | None) -> Any:
        self.actors.append(actor_id)

        @asynccontextmanager
        async def open_scope() -> AsyncIterator[WhatsAppScope]:
            uow = FakeUnitOfWork()
            self.uows.append(uow)
            yield WhatsAppScope(
                unit_of_work=uow,
                conversations=self.conversations,
                customers=FakeCustomers([self.customer, self.other_customer]),  # type: ignore[arg-type]
                orders=self.orders,  # type: ignore[arg-type]
                order_numbers=FakeOrderNumbers(),
                cancellations=MagicMock(),
                cylinder_types=FakeCylinderTypes([self.cylinder]),  # type: ignore[arg-type]
                price_lists=FakePriceLists(  # type: ignore[arg-type]
                    [
                        PriceListEntry(
                            uuid.uuid4(),
                            TENANT_ID,
                            self.cylinder.id,
                            "domestic",
                            Decimal("903.00"),
                            _now() - timedelta(days=30),
                        )
                    ]
                ),
                tenant_configuration=self.config,  # type: ignore[arg-type]
                routes=MagicMock(),
                drivers=MagicMock(),
                vehicles=MagicMock(),
                employees=MagicMock(),
                inventory=MagicMock(),
                branch_stock=self.stock,
                complaints=MagicMock(),
                complaint_numbers=MagicMock(),
                assistant_runs=self.runs,
            )

        return open_scope


def _now() -> datetime:
    return datetime.now(UTC)


def _customer(phone: str) -> Customer:
    return Customer(
        customer_id=uuid.uuid4(),
        tenant_id=TENANT_ID,
        branch_id=uuid.uuid4(),
        full_name="Asha Rao",
        phone_number=phone,
        consumer_number="CN-1",
        status="active",
        addresses=[CustomerAddress(uuid.uuid4(), "12 MG Road", city="Pune", is_primary=True)],
        identity_user_id=uuid.uuid4(),
    )


@pytest.fixture
def world() -> World:
    cylinder = CylinderType(uuid.uuid4(), TENANT_ID, "14.2 kg Domestic", Decimal("14.2"))
    return World(
        customer=_customer(PHONE),
        other_customer=_customer("+919000000001"),
        cylinder=cylinder,
        conversations=FakeConversations(),
        orders=FakeOrders(),
        config=FakeTenantConfiguration({"whatsapp_ai_enabled": True}),
        runs=FakeAssistantRuns(),
        stock=FakeBranchStock({cylinder.id: 20}),
    )


@dataclass
class ScriptedGateway:
    """Calls the given tools in order, then answers `answer`."""

    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    answer: str | None = "Done."
    results: list[dict[str, object]] = field(default_factory=list)
    seen_history: list[ConversationTurn] = field(default_factory=list)
    seen_tools: tuple[ToolDeclaration, ...] = ()

    async def run_with_tools(
        self,
        *,
        system_prompt: str,  # noqa: ARG002
        user_prompt: str,  # noqa: ARG002
        tools: tuple[ToolDeclaration, ...],
        tool_executor: ToolExecutor,
        history: Sequence[ConversationTurn] = (),
    ) -> AgentRunResult | None:
        self.seen_history = list(history)
        self.seen_tools = tools
        for name, args in self.calls:
            self.results.append(await tool_executor(name, args))
        if self.answer is None:
            return None
        return AgentRunResult(
            final_answer=self.answer,
            tools_used=tuple(name for name, _ in self.calls),
            prompt_tokens=100,
            completion_tokens=20,
            tool_turns=len(self.calls),
            provider="fake",
            model="fake-1",
        )


def _message(text: str, wa_id: str = "wamid.1", phone: str = PHONE) -> InboundWhatsAppMessage:
    return InboundWhatsAppMessage(
        phone_number_id="1111",
        wa_message_id=wa_id,
        from_phone=phone,
        profile_name="Asha",
        text=text,
    )


def _use_case(
    world: World,
    gateway: ScriptedGateway,
    sender: FakeSender,
    payment_links: FakePaymentLinks | None = None,
) -> HandleInboundWhatsAppMessageUseCase:
    return HandleInboundWhatsAppMessageUseCase(
        tenant_id=TENANT_ID,
        gateway=gateway,
        sender=sender,
        scope_factories=world.scope_factories,
        payment_links=payment_links or FakePaymentLinks(),
    )


def _tool_ctx(world: World, *, turn_started_at: datetime | None = None) -> CustomerToolContext:
    return CustomerToolContext(
        tenant_id=TENANT_ID,
        customer_id=world.customer.id,
        customer_phone=PHONE,
        actor_id=world.customer.identity_user_id,  # type: ignore[arg-type]
        turn_started_at=turn_started_at or _now(),
        scope_factory=world.scope_factories(world.customer.identity_user_id),
        payment_links=FakePaymentLinks(),
    )


def _order_for(customer: Customer, number: str) -> Order:
    order = Order(
        order_id=uuid.uuid4(),
        tenant_id=TENANT_ID,
        branch_id=customer.branch_id,
        customer_id=customer.id,
        address_id=customer.addresses[0].id,
        order_number=number,
        delivery_address=DeliveryAddress(address_line="12 MG Road"),
        booking_source="staff",
        requested_date=_now(),
        lines=[OrderLine(line_id=uuid.uuid4(), cylinder_type_id=uuid.uuid4(), quantity_ordered=1)],
    )
    order.submit(changed_by=uuid.uuid4())
    return order


# ==========================================================================
# Use case
# ==========================================================================


async def test_answers_a_registered_customer_and_logs_the_run(world: World) -> None:
    sender = FakeSender()
    gateway = ScriptedGateway(calls=[("get_my_account", {})], answer="Hi Asha!")

    result = await _use_case(world, gateway, sender).execute(_message("hi"))

    assert result.outcome == "answered"
    assert sender.sent == [(PHONE, "Hi Asha!")]
    assert gateway.results[0]["name"] == "Asha Rao"
    [run] = world.runs.runs
    assert run.status == "success"
    assert run.role == "whatsapp_customer"
    assert run.user_id == world.customer.identity_user_id
    assert run.tools_used == ["get_my_account"]
    # Tools act as the customer; the preflight runs before they are known.
    assert world.actors == [None, world.customer.identity_user_id]
    assert [entry.direction for _p, _s, entry in world.conversations.log] == [
        "inbound",
        "outbound",
    ]


async def test_a_redelivered_message_is_answered_once(world: World) -> None:
    sender = FakeSender()
    use_case = _use_case(world, ScriptedGateway(answer="Hello"), sender)

    first = await use_case.execute(_message("hi"))
    second = await use_case.execute(_message("hi"))

    assert first.outcome == "answered"
    assert second.outcome == "duplicate"
    assert len(sender.sent) == 1


async def test_history_is_passed_oldest_first(world: World) -> None:
    sender = FakeSender()
    use_case = _use_case(world, ScriptedGateway(answer="Which size?"), sender)
    await use_case.execute(_message("book a cylinder", "wamid.1"))

    gateway = ScriptedGateway(answer="Booked")
    await _use_case(world, gateway, sender).execute(_message("14.2 kg", "wamid.2"))

    assert gateway.seen_history == [
        ConversationTurn(role="user", text="book a cylinder"),
        ConversationTurn(role="assistant", text="Which size?"),
    ]


async def test_disabled_assistant_records_but_does_not_reply(world: World) -> None:
    world.config.values["whatsapp_ai_enabled"] = "false"
    sender = FakeSender()
    gateway = ScriptedGateway()

    result = await _use_case(world, gateway, sender).execute(_message("hi"))

    assert result.outcome == "assistant_disabled"
    assert sender.sent == []
    assert world.conversations.seen_ids == {"wamid.1"}
    assert world.runs.runs == []


async def test_unknown_number_gets_a_fixed_reply_without_a_model_call(world: World) -> None:
    sender = FakeSender()
    gateway = ScriptedGateway(calls=[("get_my_account", {})])

    result = await _use_case(world, gateway, sender).execute(_message("hi", phone="+911234567890"))

    assert result.outcome == "unknown_customer"
    assert sender.sent == [("+911234567890", UNKNOWN_CUSTOMER_REPLY)]
    assert gateway.results == []


async def test_spent_budget_gets_a_fixed_reply_without_a_model_call(world: World) -> None:
    world.runs.used_today = 10_000_000
    sender = FakeSender()
    gateway = ScriptedGateway(calls=[("get_my_account", {})])

    result = await _use_case(world, gateway, sender).execute(_message("hi"))

    assert result.outcome == "budget_exceeded"
    assert sender.sent == [(PHONE, UNAVAILABLE_REPLY)]
    assert gateway.results == []
    assert world.runs.runs[0].status == "budget_exceeded"


async def test_provider_failure_still_replies(world: World) -> None:
    sender = FakeSender()

    result = await _use_case(world, ScriptedGateway(answer=None), sender).execute(_message("hi"))

    assert result.outcome == "provider_error"
    assert sender.sent == [(PHONE, UNAVAILABLE_REPLY)]
    assert world.runs.runs[0].status == "provider_error"


# ==========================================================================
# Booking: prepare, then place in a later turn
# ==========================================================================


async def test_prepare_then_place_in_the_next_turn_books_the_order(world: World) -> None:
    sender = FakeSender()
    prepare = ScriptedGateway(
        calls=[("prepare_order", {"cylinder_type_id": str(world.cylinder.id), "quantity": 1})]
    )
    await _use_case(world, prepare, sender).execute(_message("book one cylinder", "wamid.1"))

    quote = prepare.results[0]["quote"]
    assert quote["estimated_total"] == "903.00"  # type: ignore[index]
    assert quote["delivery_address"] == "12 MG Road, Pune"  # type: ignore[index]
    assert world.orders.orders == []

    place = ScriptedGateway(calls=[("place_order", {})])
    await _use_case(world, place, sender).execute(_message("yes", "wamid.2"))

    assert place.results[0]["placed"] is True
    [order] = world.orders.orders
    assert order.booking_source == "whatsapp"
    assert order.customer_id == world.customer.id
    assert order.status == "booked"
    assert world.conversations.quotes == {}


async def test_place_order_in_the_same_turn_as_the_quote_is_refused(world: World) -> None:
    sender = FakeSender()
    gateway = ScriptedGateway(
        calls=[
            ("prepare_order", {"cylinder_type_id": str(world.cylinder.id), "quantity": 1}),
            ("place_order", {}),
        ]
    )

    await _use_case(world, gateway, sender).execute(_message("book and confirm"))

    assert "error" in gateway.results[1]
    assert world.orders.orders == []


async def test_expired_quote_cannot_be_placed(world: World) -> None:
    ctx = _tool_ctx(world)
    await execute_customer_tool(
        ctx, "prepare_order", {"cylinder_type_id": str(world.cylinder.id), "quantity": 1}
    )
    quote = world.conversations.quotes[PHONE]
    world.conversations.quotes[PHONE] = replace(
        quote, quoted_at=_now() - QUOTE_TTL - timedelta(minutes=1)
    )

    result = await execute_customer_tool(_tool_ctx(world), "place_order", {})

    assert "expired" in str(result["error"])
    assert world.orders.orders == []


async def test_out_of_stock_cylinder_is_neither_offered_nor_quoted(world: World) -> None:
    ctx = _tool_ctx(world)
    listed = await execute_customer_tool(ctx, "list_cylinder_options", {})
    options = cast("list[dict[str, object]]", listed["cylinder_options"])
    assert [o["name"] for o in options] == ["14.2 kg Domestic"]

    world.stock.available[world.cylinder.id] = 0
    listed = await execute_customer_tool(ctx, "list_cylinder_options", {})
    quoted = await execute_customer_tool(
        ctx, "prepare_order", {"cylinder_type_id": str(world.cylinder.id), "quantity": 1}
    )

    assert listed["cylinder_options"] == []
    assert "out of stock" in str(quoted["error"])
    assert await world.conversations.get_pending_quote(PHONE) is None


async def test_prepare_order_validates_its_arguments(world: World) -> None:
    ctx = _tool_ctx(world)

    too_many = await execute_customer_tool(
        ctx, "prepare_order", {"cylinder_type_id": str(world.cylinder.id), "quantity": 50}
    )
    bad_id = await execute_customer_tool(
        ctx, "prepare_order", {"cylinder_type_id": "not-a-uuid", "quantity": 1}
    )
    unknown_type = await execute_customer_tool(
        ctx, "prepare_order", {"cylinder_type_id": str(uuid.uuid4()), "quantity": 1}
    )
    far_date = await execute_customer_tool(
        ctx,
        "prepare_order",
        {
            "cylinder_type_id": str(world.cylinder.id),
            "quantity": 1,
            "preferred_date": (_now() + timedelta(days=30)).date().isoformat(),
        },
    )

    for result in (too_many, bad_id, unknown_type, far_date):
        assert "error" in result
    assert world.conversations.quotes == {}


async def test_inactive_account_cannot_book(world: World) -> None:
    world.customer = Customer(
        customer_id=world.customer.id,
        tenant_id=TENANT_ID,
        branch_id=world.customer.branch_id,
        full_name="Asha Rao",
        phone_number=PHONE,
        status="onboarding",
    )

    result = await execute_customer_tool(
        _tool_ctx(world),
        "prepare_order",
        {"cylinder_type_id": str(world.cylinder.id), "quantity": 1},
    )

    assert "not active" in str(result["error"])


# ==========================================================================
# Customer scoping
# ==========================================================================


async def test_another_customers_order_is_not_found(world: World) -> None:
    world.orders.orders = [_order_for(world.other_customer, "ORD000777")]
    ctx = _tool_ctx(world)

    tracked = await execute_customer_tool(ctx, "track_order", {"order_number": "ORD000777"})
    cancelled = await execute_customer_tool(ctx, "cancel_order", {"order_number": "ORD000777"})
    listed = await execute_customer_tool(ctx, "list_my_orders", {})

    assert "No recent order" in str(tracked["error"])
    assert "No recent order" in str(cancelled["error"])
    assert listed == {"orders": []}
    assert world.orders.orders[0].status == "booked"


async def test_own_order_can_be_tracked(world: World) -> None:
    world.orders.orders = [_order_for(world.customer, "ORD000123")]

    result = await execute_customer_tool(
        _tool_ctx(world), "track_order", {"order_number": "ord000123"}
    )

    assert result["order_number"] == "ORD000123"
    assert result["status"] == "booked"
    assert result["delivery"] is None


async def test_payment_link_falls_back_when_unconfigured(world: World) -> None:
    world.orders.orders = [_order_for(world.customer, "ORD000123")]

    result = await execute_customer_tool(
        _tool_ctx(world), "get_payment_link", {"order_number": "ORD000123"}
    )

    assert result["available"] is False


async def test_payment_link_is_returned_when_a_provider_answers(world: World) -> None:
    world.orders.orders = [_order_for(world.customer, "ORD000123")]
    payments = FakePaymentLinks(PaymentLink(url="https://rzp.io/l/abc", amount=Decimal("903")))
    ctx = replace(_tool_ctx(world), payment_links=payments)

    result = await execute_customer_tool(ctx, "get_payment_link", {"order_number": "ORD000123"})

    assert result == {"available": True, "payment_url": "https://rzp.io/l/abc", "amount": "903"}
    assert payments.requests[0].customer_phone == PHONE


async def test_unknown_tool_is_rejected(world: World) -> None:
    result = await execute_customer_tool(_tool_ctx(world), "delete_all_orders", {})
    assert result == {"error": "Tool 'delete_all_orders' is not available."}


async def test_no_tool_accepts_a_customer_or_phone_argument(world: World) -> None:
    gateway = ScriptedGateway()
    await _use_case(world, gateway, FakeSender()).execute(_message("hi"))

    for tool in gateway.seen_tools:
        properties = tool.parameters_schema["properties"]
        assert isinstance(properties, dict)
        assert not {"customer_id", "phone", "phone_number", "tenant_id"} & set(properties)
