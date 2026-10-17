"""The WhatsApp customer assistant (ADR-054) against a real Postgres + Redis.

Covers what the unit tests cannot: the webhook through the real ASGI stack
(signature check, Meta's verify handshake, enqueue), tenant routing by the
`tenant.whatsapp_resolve_tenant_id` SECURITY DEFINER function, RLS on the
`messaging.*` tables, and a full two-message booking through the real job,
real repositories and real order creation. The model is a scripted fake, so
no network call is made.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncEngine

    from lpg.application.ai.ports import AgentRunResult, ToolExecutor
    from lpg.config.settings import Settings

pytestmark = pytest.mark.integration

_ADMIN_URL = "postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:5433/lpg_test"
_APP_SECRET = "test-app-secret"
_VERIFY_TOKEN = "test-verify-token"


@pytest.fixture
async def admin(postgres_available: bool) -> AsyncIterator[AsyncEngine]:
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable")
    engine = create_async_engine(_ADMIN_URL)
    try:
        yield engine
    finally:
        await engine.dispose()


@dataclass
class _Seed:
    tenant_id: uuid.UUID
    phone_number_id: str
    customer_id: uuid.UUID
    customer_phone: str
    cylinder_type_id: uuid.UUID


async def _seed_tenant(engine: AsyncEngine, *, enabled: bool = True) -> _Seed:
    phone_number_id = str(uuid.uuid4().int % 10**15)
    customer_phone = f"+91{uuid.uuid4().int % 10**10:010d}"
    async with engine.begin() as conn:

        async def scalar(sql: str, **params: Any) -> uuid.UUID:
            value = (await conn.execute(text(sql), params)).scalar_one()
            return uuid.UUID(str(value))

        tenant_id = await scalar(
            "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
            "VALUES (gen_random_uuid(), 'WhatsApp Smoke', :slug, 'ops@example.com') RETURNING id",
            slug=f"wa-smoke-{uuid.uuid4().hex[:10]}",
        )
        branch_id = await scalar(
            "INSERT INTO tenant.branch (id, tenant_id, name) "
            "VALUES (gen_random_uuid(), :t, 'Main') RETURNING id",
            t=str(tenant_id),
        )
        customer_id = await scalar(
            "INSERT INTO customer.customer (id, tenant_id, branch_id, customer_type, full_name, "
            "phone_number, consumer_number, status) VALUES (gen_random_uuid(), :t, :b, "
            "'domestic', 'Asha Rao', :phone, :cn, 'active') RETURNING id",
            t=str(tenant_id),
            b=str(branch_id),
            phone=customer_phone,
            cn=f"CN{uuid.uuid4().hex[:10]}",
        )
        await conn.execute(
            text(
                "INSERT INTO customer.customer_address "
                "(id, tenant_id, customer_id, line_1, city, is_primary) "
                "VALUES (gen_random_uuid(), :t, :c, '12 MG Road', 'Pune', true)"
            ),
            {"t": str(tenant_id), "c": str(customer_id)},
        )
        cylinder_type_id = await scalar(
            "INSERT INTO tenant.cylinder_type (id, tenant_id, name, weight_kg) "
            "VALUES (gen_random_uuid(), :t, '14.2 kg Domestic', 14.2) RETURNING id",
            t=str(tenant_id),
        )
        await conn.execute(
            text(
                "INSERT INTO tenant.price_list (id, tenant_id, cylinder_type_id, customer_type, "
                "branch_id, price, effective_from) VALUES (gen_random_uuid(), :t, :ct, "
                "'domestic', NULL, 903.00, :ef)"
            ),
            {
                "t": str(tenant_id),
                "ct": str(cylinder_type_id),
                "ef": datetime.now(UTC) - timedelta(days=1),
            },
        )
        config = {
            "whatsapp_phone_number_id": json.dumps(phone_number_id),
            "whatsapp_ai_enabled": json.dumps(enabled),
        }
        for key, value in config.items():
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant_configuration "
                    "(id, tenant_id, config_key, config_value, effective_from) "
                    "VALUES (gen_random_uuid(), :t, :k, CAST(:v AS jsonb), now())"
                ),
                {"t": str(tenant_id), "k": key, "v": value},
            )
    return _Seed(tenant_id, phone_number_id, customer_id, customer_phone, cylinder_type_id)


# ==========================================================================
# Tenant routing
# ==========================================================================


async def _resolve(integration_settings: Settings, phone_number_id: str) -> uuid.UUID | None:
    from lpg.infrastructure.persistence.database import build_database
    from lpg.infrastructure.whatsapp.tenant_resolver import SqlAlchemyWhatsAppTenantResolver

    database = build_database(integration_settings)
    database.connect()
    try:
        return await SqlAlchemyWhatsAppTenantResolver(database).resolve(phone_number_id)
    finally:
        await database.disconnect()


async def test_phone_number_id_routes_to_its_tenant(
    admin: AsyncEngine, integration_settings: Settings
) -> None:
    seed = await _seed_tenant(admin)

    assert await _resolve(integration_settings, seed.phone_number_id) == seed.tenant_id
    assert await _resolve(integration_settings, "000") is None


async def test_a_number_claimed_by_two_tenants_routes_nowhere(
    admin: AsyncEngine, integration_settings: Settings
) -> None:
    first = await _seed_tenant(admin)
    second = await _seed_tenant(admin)
    async with admin.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO tenant.tenant_configuration "
                "(id, tenant_id, config_key, config_value, effective_from) "
                "VALUES (gen_random_uuid(), :t, 'whatsapp_phone_number_id', "
                "CAST(:v AS jsonb), now())"
            ),
            {"t": str(second.tenant_id), "v": json.dumps(first.phone_number_id)},
        )

    assert await _resolve(integration_settings, first.phone_number_id) is None


# ==========================================================================
# The job, end to end
# ==========================================================================


@dataclass
class _ScriptedGateway:
    """Each `run_with_tools` call pops the next list of tool calls."""

    turns: list[list[tuple[str, dict[str, Any]]]]
    results: list[dict[str, object]] = field(default_factory=list)

    async def run_with_tools(
        self, *, tool_executor: ToolExecutor, **_kwargs: Any
    ) -> AgentRunResult | None:
        from lpg.application.ai.ports import AgentRunResult

        calls = self.turns.pop(0)
        for name, args in calls:
            self.results.append(await tool_executor(name, args))
        return AgentRunResult(
            final_answer=f"ok: {[name for name, _ in calls]}",
            tools_used=tuple(name for name, _ in calls),
            prompt_tokens=50,
            completion_tokens=10,
            tool_turns=len(calls),
            provider="fake",
            model="fake-1",
        )


class _RecordingSender:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    async def send_text(self, *, phone_number_id: str, to: str, body: str) -> str | None:
        self.sent.append((phone_number_id, to, body))
        return f"wamid.out.{uuid.uuid4().hex}"


async def _run_job(
    integration_settings: Settings,
    gateway: _ScriptedGateway,
    sender: _RecordingSender,
    message: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> str:
    from lpg.infrastructure.jobs import whatsapp_jobs
    from lpg.infrastructure.persistence.database import build_database

    monkeypatch.setattr(whatsapp_jobs, "get_model_gateway", lambda _settings: gateway)
    monkeypatch.setattr(whatsapp_jobs, "get_settings", lambda: integration_settings)
    database = build_database(integration_settings)
    database.connect()
    try:
        return await whatsapp_jobs.handle_whatsapp_message(
            {"database": database, "whatsapp_sender": sender}, message
        )
    finally:
        await database.disconnect()


def _message(seed: _Seed, text_body: str) -> dict[str, Any]:
    return {
        "phone_number_id": seed.phone_number_id,
        "wa_message_id": f"wamid.{uuid.uuid4().hex}",
        "from_phone": seed.customer_phone,
        "profile_name": "Asha",
        "text": text_body,
    }


async def test_a_customer_books_a_refill_over_two_messages(
    admin: AsyncEngine,
    integration_settings: Settings,
    redis_available: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not redis_available:
        pytest.skip("Redis is not reachable")
    seed = await _seed_tenant(admin)
    sender = _RecordingSender()
    gateway = _ScriptedGateway(
        turns=[
            [
                ("list_cylinder_options", {}),
                ("prepare_order", {"cylinder_type_id": str(seed.cylinder_type_id), "quantity": 1}),
            ],
            [("place_order", {}), ("list_my_orders", {})],
        ]
    )

    first = _message(seed, "I need a cylinder")
    assert await _run_job(integration_settings, gateway, sender, first, monkeypatch) == "answered"
    # Meta re-delivers the same message: no second answer.
    assert await _run_job(integration_settings, gateway, sender, first, monkeypatch) == "duplicate"
    second = _message(seed, "Yes, confirm")
    assert await _run_job(integration_settings, gateway, sender, second, monkeypatch) == "answered"

    options, quote, placed, listed = gateway.results
    assert options["cylinder_options"][0]["price"] == "903.00"  # type: ignore[index]
    assert quote["quote"]["estimated_total"] == "903.00"  # type: ignore[index]
    assert placed["placed"] is True, placed
    assert len(listed["orders"]) == 1  # type: ignore[arg-type]
    assert [to for _id, to, _body in sender.sent] == [seed.customer_phone] * 2

    async with admin.connect() as conn:
        order = (
            await conn.execute(
                text(
                    "SELECT booking_source, status, customer_id FROM orders.order "
                    "WHERE tenant_id = :t"
                ),
                {"t": str(seed.tenant_id)},
            )
        ).one()
        directions = (
            await conn.execute(
                text(
                    "SELECT direction FROM messaging.whatsapp_message WHERE tenant_id = :t "
                    "ORDER BY created_at"
                ),
                {"t": str(seed.tenant_id)},
            )
        ).scalars()
        runs = (
            await conn.execute(
                text("SELECT role, status FROM ai.assistant_run WHERE tenant_id = :t"),
                {"t": str(seed.tenant_id)},
            )
        ).all()
        quote_row = (
            await conn.execute(
                text(
                    "SELECT pending_quote FROM messaging.whatsapp_conversation WHERE tenant_id = :t"
                ),
                {"t": str(seed.tenant_id)},
            )
        ).scalar_one()

    assert order.booking_source == "whatsapp"
    assert order.status == "booked"
    assert order.customer_id == seed.customer_id
    assert list(directions) == ["inbound", "outbound", "inbound", "outbound"]
    assert [tuple(r) for r in runs] == [("whatsapp_customer", "success")] * 2
    assert quote_row is None


async def test_messaging_rows_are_invisible_to_other_tenants(
    admin: AsyncEngine,
    integration_settings: Settings,
    redis_available: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not redis_available:
        pytest.skip("Redis is not reachable")
    owner = await _seed_tenant(admin)
    other = await _seed_tenant(admin)
    await _run_job(
        integration_settings,
        _ScriptedGateway(turns=[[]]),
        _RecordingSender(),
        _message(owner, "hello"),
        monkeypatch,
    )

    from lpg.infrastructure.persistence.database import build_database

    database = build_database(integration_settings)
    database.connect()
    try:
        counts = {}
        for tenant in (owner, other):
            async for session in database.open_session(tenant_id=tenant.tenant_id):
                counts[tenant.tenant_id] = (
                    await session.execute(text("SELECT count(*) FROM messaging.whatsapp_message"))
                ).scalar_one()
    finally:
        await database.disconnect()

    assert counts == {owner.tenant_id: 2, other.tenant_id: 0}


async def test_payment_link_goes_through_the_shared_razorpay_use_case(
    admin: AsyncEngine,
    integration_settings: Settings,
    redis_available: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not redis_available:
        pytest.skip("Redis is not reachable")
    from lpg.application.accounting.payment_gateway import PaymentLink
    from lpg.infrastructure.jobs import whatsapp_jobs
    from lpg.infrastructure.payments.razorpay import RazorpayPaymentGateway

    class _StubbedRazorpay(RazorpayPaymentGateway):
        def __init__(self) -> None:
            super().__init__(
                key_id="rzp_test_whatsapp",
                key_secret="secret",
                webhook_secret="whsec",
                api_base_url="https://api.razorpay.invalid/v1",
                callback_url="",
                timeout_seconds=1,
            )
            self.requests: list[Any] = []

        async def create_payment_link(self, request: Any) -> PaymentLink:
            self.requests.append(request)
            return PaymentLink(link_id="plink_wa", short_url="https://rzp.io/i/plink_wa")

    seed = await _seed_tenant(admin)
    order_number = f"ORD-WA-{uuid.uuid4().hex[:6]}"
    async with admin.begin() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT branch_id, (SELECT id FROM customer.customer_address "
                    "WHERE customer_id = c.id LIMIT 1) FROM customer.customer c WHERE id = :c"
                ),
                {"c": str(seed.customer_id)},
            )
        ).one()
        order_id = (
            await conn.execute(
                text(
                    "INSERT INTO orders.order (id, tenant_id, branch_id, customer_id, address_id, "
                    "delivery_address_line, status, booking_source, requested_date, "
                    "total_amount, order_number) VALUES (gen_random_uuid(), :t, :b, :c, :a, "
                    "'12 MG Road', 'confirmed', 'whatsapp', now(), 903.00, :n) RETURNING id"
                ),
                {
                    "t": str(seed.tenant_id),
                    "b": str(row[0]),
                    "c": str(seed.customer_id),
                    "a": str(row[1]),
                    "n": order_number,
                },
            )
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO orders.order_line (id, order_id, cylinder_type_id, "
                "quantity_ordered, unit_price) VALUES (gen_random_uuid(), :o, :ct, 1, 903)"
            ),
            {"o": str(order_id), "ct": str(seed.cylinder_type_id)},
        )

    razorpay = _StubbedRazorpay()
    monkeypatch.setattr(whatsapp_jobs, "get_payment_gateway", lambda _settings: razorpay)
    gateway = _ScriptedGateway(turns=[[("get_payment_link", {"order_number": order_number})]])
    message = _message(seed, "Send me a payment link")
    result = await _run_job(integration_settings, gateway, _RecordingSender(), message, monkeypatch)

    assert result == "answered"
    assert gateway.results == [
        {"available": True, "payment_url": "https://rzp.io/i/plink_wa", "amount": "903.00"}
    ]
    assert razorpay.requests[0].customer_phone == seed.customer_phone
    async with admin.connect() as conn:
        payment = (
            await conn.execute(
                text(
                    "SELECT order_id, customer_id, status, short_url "
                    "FROM accounting.online_payment WHERE tenant_id = :t"
                ),
                {"t": str(seed.tenant_id)},
            )
        ).one()
    assert (payment.order_id, payment.customer_id) == (order_id, seed.customer_id)
    assert payment.status == "created"


# ==========================================================================
# Webhook
# ==========================================================================


class _RecordingQueue:
    def __init__(self) -> None:
        self.jobs: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    async def enqueue(self, function_name: str, *args: Any, **kwargs: Any) -> str | None:
        self.jobs.append((function_name, args, kwargs))
        return "job"


@dataclass
class _Webhook:
    client: AsyncClient
    queue: _RecordingQueue


@pytest.fixture
async def webhook(
    integration_settings: Settings,
    postgres_available: bool,
    redis_available: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[_Webhook]:
    if not postgres_available or not redis_available:
        pytest.skip("infra not reachable")
    monkeypatch.setenv("LPG_ENVIRONMENT", "local")
    monkeypatch.setenv("LPG_DATABASE_URL", str(integration_settings.database_url))
    monkeypatch.setenv("LPG_REDIS_URL", str(integration_settings.redis_url))
    monkeypatch.setenv("LPG_WHATSAPP_APP_SECRET", _APP_SECRET)
    monkeypatch.setenv("LPG_WHATSAPP_VERIFY_TOKEN", _VERIFY_TOKEN)

    from lpg.api.app import create_app
    from lpg.api.v1.dependencies.order import get_job_queue
    from lpg.config.settings import get_settings

    get_settings.cache_clear()
    app = create_app(integration_settings)
    queue = _RecordingQueue()
    app.dependency_overrides[get_job_queue] = lambda: queue
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as http:
            yield _Webhook(client=http, queue=queue)
    get_settings.cache_clear()


def _signed(body: bytes, secret: str = _APP_SECRET) -> dict[str, str]:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return {"X-Hub-Signature-256": f"sha256={digest}", "Content-Type": "application/json"}


_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "changes": [
                {
                    "field": "messages",
                    "value": {
                        "metadata": {"phone_number_id": "1111"},
                        "contacts": [{"wa_id": "919876543210", "profile": {"name": "Asha"}}],
                        "messages": [
                            {
                                "from": "919876543210",
                                "id": "wamid.ABC",
                                "type": "text",
                                "text": {"body": "hi"},
                            }
                        ],
                    },
                }
            ]
        }
    ],
}


async def test_signed_webhook_enqueues_one_job_per_message(webhook: _Webhook) -> None:
    body = json.dumps(_PAYLOAD).encode()

    response = await webhook.client.post(
        "/api/v1/webhooks/whatsapp", content=body, headers=_signed(body)
    )

    assert response.status_code == 200
    assert response.json() == {"received": 1}
    [(name, args, kwargs)] = webhook.queue.jobs
    assert name == "handle_whatsapp_message"
    assert args[0]["from_phone"] == "+919876543210"
    assert kwargs == {"_job_id": "whatsapp:wamid.ABC"}


async def test_unsigned_or_forged_webhook_is_rejected(webhook: _Webhook) -> None:
    body = json.dumps(_PAYLOAD).encode()

    unsigned = await webhook.client.post("/api/v1/webhooks/whatsapp", content=body)
    forged = await webhook.client.post(
        "/api/v1/webhooks/whatsapp", content=body, headers=_signed(body, "wrong")
    )

    assert unsigned.status_code == 403
    assert forged.status_code == 403
    assert webhook.queue.jobs == []


async def test_verify_handshake_echoes_the_challenge(webhook: _Webhook) -> None:
    ok = await webhook.client.get(
        "/api/v1/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": _VERIFY_TOKEN,
            "hub.challenge": "12345",
        },
    )
    wrong = await webhook.client.get(
        "/api/v1/webhooks/whatsapp",
        params={"hub.mode": "subscribe", "hub.verify_token": "nope", "hub.challenge": "1"},
    )

    assert ok.status_code == 200
    assert ok.text == "12345"
    assert wrong.status_code == 403


async def test_blank_secrets_reject_every_webhook(
    webhook: _Webhook, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lpg.config.settings import get_settings

    monkeypatch.setenv("LPG_WHATSAPP_APP_SECRET", "")
    monkeypatch.setenv("LPG_WHATSAPP_VERIFY_TOKEN", "")
    get_settings.cache_clear()
    body = json.dumps({"object": "whatsapp_business_account", "entry": []}).encode()

    verify = await webhook.client.get(
        "/api/v1/webhooks/whatsapp",
        params={"hub.mode": "subscribe", "hub.verify_token": "", "hub.challenge": "1"},
    )
    forged = await webhook.client.post(
        "/api/v1/webhooks/whatsapp", content=body, headers=_signed(body, secret="")
    )

    assert verify.status_code == 403
    assert forged.status_code == 403
