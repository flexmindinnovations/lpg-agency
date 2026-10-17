"""Unit tests for online payments (ADR-053): the `OnlinePayment` aggregate,
the payment-link use cases, prepayment application at invoice generation,
and the Razorpay adapter (against `httpx.MockTransport`, never the network).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from lpg.application.accounting.online_payments import (
    CreateOrderPaymentLinkCommand,
    CreateOrderPaymentLinkUseCase,
    HandlePaymentWebhookUseCase,
    OrderPaymentScope,
    RefreshOnlinePaymentCommand,
    RefreshOnlinePaymentUseCase,
)
from lpg.application.accounting.payment_gateway import (
    InvalidWebhookSignatureError,
    PaymentGatewayError,
    PaymentLink,
    PaymentLinkRequest,
    PaymentLinkStatus,
)
from lpg.application.accounting.use_cases import (
    GenerateInvoiceForOrderUseCase,
    apply_online_payments_to_invoice,
)
from lpg.application.common.errors import (
    ConflictError,
    NotFoundError,
    ServiceUnavailableError,
)
from lpg.domain.accounting.invoice import Invoice, InvoiceLine
from lpg.domain.accounting.online_payment import OnlinePayment, OnlinePaymentReceived
from lpg.domain.common.base import InvariantViolation
from lpg.domain.order.order import OrderLine
from lpg.infrastructure.payments.razorpay import RazorpayPaymentGateway, to_paise

TENANT_ID = uuid.uuid4()
NOW = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _payment(
    *,
    amount: Decimal = Decimal("500.00"),
    status: str = "created",
    order_id: uuid.UUID | None = None,
    expires_at: datetime | None = None,
) -> OnlinePayment:
    return OnlinePayment(
        online_payment_id=uuid.uuid4(),
        tenant_id=TENANT_ID,
        order_id=order_id or uuid.uuid4(),
        customer_id=uuid.uuid4(),
        amount=amount,
        currency="INR",
        provider="razorpay",
        provider_link_id=f"plink_{uuid.uuid4().hex[:14]}",
        short_url="https://rzp.io/i/abc",
        status=status,
        created_by=uuid.uuid4(),
        created_at=NOW,
        expires_at=expires_at,
        paid_at=NOW if status == "paid" else None,
    )


def _invoice(total: Decimal = Decimal("500.00"), order_id: uuid.UUID | None = None) -> Invoice:
    line = InvoiceLine(
        line_id=uuid.uuid4(),
        cylinder_type_id=uuid.uuid4(),
        quantity=1,
        unit_price=total,
        subtotal=total,
        tax_amount=Decimal("0"),
        total_amount=total,
    )
    return Invoice(
        invoice_id=uuid.uuid4(),
        tenant_id=TENANT_ID,
        invoice_number="INV-2026-000001",
        customer_id=uuid.uuid4(),
        order_id=order_id or uuid.uuid4(),
        status="issued",
        subtotal=total,
        tax_amount=Decimal("0"),
        total_amount=total,
        issued_at=NOW,
        lines=[line],
    )


def _order(
    *,
    status: str = "confirmed",
    lines: list[OrderLine] | None = None,
    customer_id: uuid.UUID | None = None,
    branch_id: uuid.UUID | None = None,
) -> MagicMock:
    order = MagicMock()
    order.id = uuid.uuid4()
    order.order_number = "ORD-000001"
    order.status = status
    order.customer_id = customer_id or uuid.uuid4()
    order.branch_id = branch_id or uuid.uuid4()
    order.lines = lines or [
        OrderLine(
            line_id=uuid.uuid4(),
            cylinder_type_id=uuid.uuid4(),
            quantity_ordered=2,
            unit_price=Decimal("450.00"),
        )
    ]
    return order


class _FakeGateway:
    provider = "razorpay"

    def __init__(self, *, configured: bool = True) -> None:
        self.is_configured = configured
        self.requests: list[PaymentLinkRequest] = []
        self.status = PaymentLinkStatus(link_id="", status="created")
        self.fail = False

    async def create_payment_link(self, request: PaymentLinkRequest) -> PaymentLink:
        if self.fail:
            msg = "boom"
            raise PaymentGatewayError(msg)
        self.requests.append(request)
        return PaymentLink(link_id=f"plink_{len(self.requests)}", short_url="https://rzp.io/i/x")

    async def fetch_payment_link(self, link_id: str) -> PaymentLinkStatus:  # noqa: ARG002
        return self.status

    def parse_webhook(self, body: bytes, signature: str | None) -> PaymentLinkStatus | None:
        raise NotImplementedError


def _repos(
    order: MagicMock, *, invoice: Invoice | None = None, existing: list[OnlinePayment] | None = None
) -> dict[str, MagicMock]:
    order_repo = MagicMock()
    order_repo.get_by_id = AsyncMock(return_value=order)
    invoice_repo = MagicMock()
    invoice_repo.get_by_order_id = AsyncMock(return_value=invoice)
    invoice_repo.save = AsyncMock()
    online_repo = MagicMock()
    online_repo.next_id = MagicMock(side_effect=uuid.uuid4)
    online_repo.list_for_order = AsyncMock(return_value=existing or [])
    online_repo.add = AsyncMock()
    online_repo.save = AsyncMock()
    customer_repo = MagicMock()
    customer = MagicMock(full_name="Asha", phone_number="+919800000000", email=None)
    customer_repo.get_by_id = AsyncMock(return_value=customer)
    config_repo = MagicMock()
    config_repo.list_for_tenant_and_key = AsyncMock(return_value=[])
    uow = MagicMock()
    uow.commit = AsyncMock()
    return {
        "order_repository": order_repo,
        "invoice_repository": invoice_repo,
        "online_payment_repository": online_repo,
        "customer_repository": customer_repo,
        "tenant_config_repository": config_repo,
        "unit_of_work": uow,
    }


def _create_use_case(
    repos: dict[str, MagicMock], gateway: _FakeGateway
) -> CreateOrderPaymentLinkUseCase:
    return CreateOrderPaymentLinkUseCase(**repos, gateway=gateway, link_ttl=timedelta(hours=24))


def _command(
    order: MagicMock, scope: OrderPaymentScope | None = None
) -> CreateOrderPaymentLinkCommand:
    return CreateOrderPaymentLinkCommand(
        tenant_id=TENANT_ID,
        order_id=order.id,
        requested_by=uuid.uuid4(),
        scope=scope or OrderPaymentScope(),
    )


# ---------------------------------------------------------------------------
# Domain
# ---------------------------------------------------------------------------


class TestOnlinePaymentAggregate:
    def test_rejects_non_positive_and_sub_paise_amounts(self) -> None:
        with pytest.raises(InvariantViolation):
            _payment(amount=Decimal("0"))
        with pytest.raises(InvariantViolation):
            _payment(amount=Decimal("10.005"))

    def test_mark_paid_records_event_once(self) -> None:
        payment = _payment()
        assert payment.mark_paid(provider_payment_id="pay_1", payment_method="upi", paid_at=NOW)
        assert not payment.mark_paid(provider_payment_id="pay_1", payment_method="upi", paid_at=NOW)
        assert payment.status == "paid"
        assert [type(e) for e in payment.events] == [OnlinePaymentReceived]

    def test_paid_wins_over_a_locally_expired_link(self) -> None:
        payment = _payment()
        assert payment.mark_closed("expired")
        assert payment.mark_paid(provider_payment_id="pay_1", payment_method=None, paid_at=NOW)
        assert payment.status == "paid"

    def test_cannot_close_a_paid_payment(self) -> None:
        payment = _payment(status="paid")
        assert not payment.mark_closed("cancelled")
        assert payment.status == "paid"

    def test_apply_requires_paid_and_happens_once(self) -> None:
        with pytest.raises(InvariantViolation):
            _payment().mark_applied(invoice_id=uuid.uuid4(), payment_id=uuid.uuid4())
        payment = _payment(status="paid")
        payment.mark_applied(invoice_id=uuid.uuid4(), payment_id=uuid.uuid4())
        with pytest.raises(InvariantViolation):
            payment.mark_applied(invoice_id=uuid.uuid4(), payment_id=uuid.uuid4())

    def test_reusable_only_when_open_unexpired_and_same_amount(self) -> None:
        payment = _payment(expires_at=NOW + timedelta(hours=1))
        assert payment.is_reusable(amount=Decimal("500.00"), now=NOW)
        assert not payment.is_reusable(amount=Decimal("400.00"), now=NOW)
        assert not payment.is_reusable(amount=Decimal("500.00"), now=NOW + timedelta(hours=2))


# ---------------------------------------------------------------------------
# Applying payments to invoices
# ---------------------------------------------------------------------------


class TestApplyOnlinePaymentsToInvoice:
    def test_applies_paid_payment_as_online_gateway(self) -> None:
        invoice = _invoice()
        payment = _payment(status="paid")
        changed = apply_online_payments_to_invoice(invoice, [payment])
        assert changed == [payment]
        assert invoice.status == "paid"
        assert invoice.payments[0].method == "online_gateway"
        assert payment.applied_payment_id == invoice.payments[0].id
        assert payment.invoice_id == invoice.id

    def test_caps_a_prepayment_larger_than_the_invoice(self) -> None:
        invoice = _invoice(total=Decimal("450.00"))
        payment = _payment(amount=Decimal("900.00"), status="paid")
        apply_online_payments_to_invoice(invoice, [payment])
        assert invoice.amount_paid == Decimal("450.00")
        assert invoice.status == "paid"

    def test_skips_unpaid_and_already_applied(self) -> None:
        invoice = _invoice()
        applied = _payment(status="paid")
        applied.mark_applied(invoice_id=uuid.uuid4(), payment_id=uuid.uuid4())
        assert apply_online_payments_to_invoice(invoice, [_payment(), applied]) == []
        assert invoice.status == "issued"

    async def test_invoice_generation_applies_prepayment(self) -> None:
        order = _order(status="out_for_delivery")
        order.lines[0].quantity_delivered = 2
        prepayment = _payment(amount=Decimal("900.00"), status="paid", order_id=order.id)
        invoice_repo = MagicMock()
        invoice_repo.get_by_order_id = AsyncMock(return_value=None)
        invoice_repo.add = AsyncMock()
        order_repo = MagicMock()
        order_repo.get_by_id = AsyncMock(return_value=order)
        config_repo = MagicMock()
        config_repo.list_for_tenant_and_key = AsyncMock(return_value=[])
        customer_repo = MagicMock()
        customer_repo.get_by_id = AsyncMock(return_value=None)
        sequence = MagicMock()
        sequence.next = AsyncMock(return_value="INV-2026-000009")
        online_repo = MagicMock()
        online_repo.list_for_order = AsyncMock(return_value=[prepayment])
        online_repo.save = AsyncMock()

        await GenerateInvoiceForOrderUseCase(
            invoice_repository=invoice_repo,
            order_repository=order_repo,
            customer_repository=customer_repo,
            tenant_config_repository=config_repo,
            invoice_number_sequence=sequence,
            online_payment_repository=online_repo,
        ).execute(tenant_id=TENANT_ID, order_id=order.id, delivered_at=NOW)

        invoice: Invoice = invoice_repo.add.call_args.args[0]
        assert invoice.status == "paid"
        assert invoice.payments[0].method == "online_gateway"
        online_repo.save.assert_awaited_once_with(prepayment)


# ---------------------------------------------------------------------------
# Create payment link
# ---------------------------------------------------------------------------


class TestCreateOrderPaymentLink:
    async def test_prepayment_amount_is_order_total_plus_gst(self) -> None:
        order = _order()
        repos = _repos(order)
        config = MagicMock(config_value="5")
        config.effective_from = NOW - timedelta(days=1)
        config.config_key = "gst_rate_percent"
        repos["tenant_config_repository"].list_for_tenant_and_key = AsyncMock(return_value=[config])
        gateway = _FakeGateway()

        payment = await _create_use_case(repos, gateway).execute(_command(order))

        # 2 x 450 = 900, + 5% GST = 945.00
        assert payment.amount == Decimal("945.00")
        assert payment.invoice_id is None
        request = gateway.requests[0]
        assert request.notes["tenant_id"] == str(TENANT_ID)
        assert request.notes["online_payment_id"] == str(payment.id)
        assert request.reference_id == str(payment.id)
        assert request.customer_phone == "+919800000000"
        repos["online_payment_repository"].add.assert_awaited_once()
        repos["unit_of_work"].commit.assert_awaited_once()

    async def test_invoice_outstanding_is_charged_once_invoiced(self) -> None:
        order = _order(status="delivered")
        invoice = _invoice(total=Decimal("500.00"), order_id=order.id)
        invoice.record_payment(
            payment_id=uuid.uuid4(),
            method="cash",
            amount=Decimal("200.00"),
            collected_by=uuid.uuid4(),
            collected_at=NOW,
        )
        repos = _repos(order, invoice=invoice)

        payment = await _create_use_case(repos, _FakeGateway()).execute(_command(order))

        assert payment.amount == Decimal("300.00")
        assert payment.invoice_id == invoice.id

    async def test_reuses_open_link_for_same_amount(self) -> None:
        order = _order()
        existing = _payment(
            amount=Decimal("900.00"),
            order_id=order.id,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        repos = _repos(order, existing=[existing])
        gateway = _FakeGateway()

        payment = await _create_use_case(repos, gateway).execute(_command(order))

        assert payment is existing
        assert gateway.requests == []

    async def test_nothing_due_when_fully_prepaid(self) -> None:
        order = _order()
        repos = _repos(order, existing=[_payment(amount=Decimal("900.00"), status="paid")])
        with pytest.raises(ConflictError):
            await _create_use_case(repos, _FakeGateway()).execute(_command(order))

    async def test_unconfirmed_order_cannot_be_prepaid(self) -> None:
        order = _order(status="booked")
        with pytest.raises(ConflictError):
            await _create_use_case(_repos(order), _FakeGateway()).execute(_command(order))

    async def test_other_customers_order_is_not_found(self) -> None:
        order = _order()
        scope = OrderPaymentScope(customer_id=uuid.uuid4())
        with pytest.raises(NotFoundError):
            await _create_use_case(_repos(order), _FakeGateway()).execute(_command(order, scope))

    async def test_other_branch_order_is_not_found(self) -> None:
        order = _order()
        scope = OrderPaymentScope(branch_id=uuid.uuid4())
        with pytest.raises(NotFoundError):
            await _create_use_case(_repos(order), _FakeGateway()).execute(_command(order, scope))

    async def test_unconfigured_gateway_is_503(self) -> None:
        order = _order()
        with pytest.raises(ServiceUnavailableError):
            await _create_use_case(_repos(order), _FakeGateway(configured=False)).execute(
                _command(order)
            )

    async def test_gateway_failure_is_503_and_nothing_saved(self) -> None:
        order = _order()
        repos = _repos(order)
        gateway = _FakeGateway()
        gateway.fail = True
        with pytest.raises(ServiceUnavailableError):
            await _create_use_case(repos, gateway).execute(_command(order))
        repos["online_payment_repository"].add.assert_not_awaited()


# ---------------------------------------------------------------------------
# Refresh / webhook
# ---------------------------------------------------------------------------


class TestSettlement:
    async def test_webhook_paid_applies_to_existing_invoice(self) -> None:
        order = _order(status="delivered")
        invoice = _invoice(order_id=order.id)
        payment = _payment(order_id=order.id)
        repos = _repos(order, invoice=invoice)
        repos["online_payment_repository"].get_by_provider_link_id = AsyncMock(return_value=payment)

        await HandlePaymentWebhookUseCase(
            invoice_repository=repos["invoice_repository"],
            online_payment_repository=repos["online_payment_repository"],
            unit_of_work=repos["unit_of_work"],
        ).execute(
            PaymentLinkStatus(
                link_id=payment.provider_link_id,
                status="paid",
                provider_payment_id="pay_9",
                payment_method="upi",
                paid_at=NOW,
            )
        )

        assert payment.status == "paid"
        assert payment.payment_method == "upi"
        assert invoice.status == "paid"
        repos["invoice_repository"].save.assert_awaited_once_with(invoice)

    async def test_webhook_for_unknown_link_is_ignored(self) -> None:
        repos = _repos(_order())
        repos["online_payment_repository"].get_by_provider_link_id = AsyncMock(return_value=None)
        result = await HandlePaymentWebhookUseCase(
            invoice_repository=repos["invoice_repository"],
            online_payment_repository=repos["online_payment_repository"],
            unit_of_work=repos["unit_of_work"],
        ).execute(PaymentLinkStatus(link_id="plink_x", status="paid"))
        assert result is None
        repos["unit_of_work"].commit.assert_not_awaited()

    async def test_refresh_pulls_status_from_gateway(self) -> None:
        order = _order()
        payment = _payment(order_id=order.id)
        repos = _repos(order)
        repos["online_payment_repository"].get_by_id = AsyncMock(return_value=payment)
        gateway = _FakeGateway()
        gateway.status = PaymentLinkStatus(link_id=payment.provider_link_id, status="expired")

        result = await RefreshOnlinePaymentUseCase(
            order_repository=repos["order_repository"],
            invoice_repository=repos["invoice_repository"],
            online_payment_repository=repos["online_payment_repository"],
            gateway=gateway,
            unit_of_work=repos["unit_of_work"],
        ).execute(RefreshOnlinePaymentCommand(tenant_id=TENANT_ID, online_payment_id=payment.id))

        assert result.status == "expired"


# ---------------------------------------------------------------------------
# Razorpay adapter
# ---------------------------------------------------------------------------

WEBHOOK_SECRET = "whsec_test"


def _gateway(handler: httpx.MockTransport | None = None) -> RazorpayPaymentGateway:
    return RazorpayPaymentGateway(
        key_id="rzp_test_key",
        key_secret="secret",
        webhook_secret=WEBHOOK_SECRET,
        api_base_url="https://api.razorpay.com/v1",
        callback_url="",
        timeout_seconds=5,
        transport=handler,
    )


def _sign(body: bytes) -> str:
    return hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


class TestRazorpayAdapter:
    def test_to_paise(self) -> None:
        assert to_paise(Decimal("945.00")) == 94500
        assert to_paise(Decimal("0.01")) == 1

    async def test_create_payment_link_payload(self) -> None:
        seen: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["path"] = request.url.path
            seen["auth"] = request.headers["Authorization"]
            seen["body"] = json.loads(request.content)
            return httpx.Response(
                200, json={"id": "plink_1", "short_url": "https://rzp.io/i/1", "status": "created"}
            )

        link = await _gateway(httpx.MockTransport(handler)).create_payment_link(
            PaymentLinkRequest(
                amount=Decimal("945.00"),
                currency="INR",
                reference_id="ref-1",
                description="LPG order ORD-1",
                notes={"tenant_id": "t"},
                customer_phone="+919800000000",
                expires_at=NOW,
            )
        )

        assert link == PaymentLink(link_id="plink_1", short_url="https://rzp.io/i/1")
        assert seen["path"] == "/v1/payment_links"
        assert str(seen["auth"]).startswith("Basic ")
        body = seen["body"]
        assert isinstance(body, dict)
        assert body["amount"] == 94500
        assert body["accept_partial"] is False
        assert body["notify"] == {"sms": False, "email": False}
        assert body["customer"] == {"contact": "+919800000000"}
        assert body["expire_by"] == int(NOW.timestamp())

    async def test_gateway_error_is_raised_as_payment_gateway_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": {"description": "Authentication failed"}})

        with pytest.raises(PaymentGatewayError):
            await _gateway(httpx.MockTransport(handler)).fetch_payment_link("plink_1")

    async def test_fetch_paid_link(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "id": "plink_1",
                    "status": "paid",
                    "notes": {"tenant_id": "t"},
                    "payments": [
                        {"payment_id": "pay_1", "status": "captured", "created_at": 1760000000}
                    ],
                },
            )

        status = await _gateway(httpx.MockTransport(handler)).fetch_payment_link("plink_1")
        assert status.status == "paid"
        assert status.provider_payment_id == "pay_1"
        assert status.notes == {"tenant_id": "t"}

    def test_webhook_signature_is_required(self) -> None:
        body = b'{"event": "payment_link.paid"}'
        with pytest.raises(InvalidWebhookSignatureError):
            _gateway().parse_webhook(body, None)
        with pytest.raises(InvalidWebhookSignatureError):
            _gateway().parse_webhook(body, "deadbeef")

    def test_webhook_paid_event_is_normalised(self) -> None:
        body = json.dumps(
            {
                "event": "payment_link.paid",
                "payload": {
                    "payment_link": {
                        "entity": {"id": "plink_1", "status": "paid", "notes": {"tenant_id": "t"}}
                    },
                    "payment": {
                        "entity": {"id": "pay_1", "method": "upi", "created_at": 1760000000}
                    },
                },
            }
        ).encode()
        status = _gateway().parse_webhook(body, _sign(body))
        assert status is not None
        assert (status.link_id, status.status, status.payment_method) == ("plink_1", "paid", "upi")
        assert status.provider_payment_id == "pay_1"
        assert status.notes["tenant_id"] == "t"

    def test_unhandled_event_is_ignored_after_verification(self) -> None:
        body = b'{"event": "payment.authorized", "payload": {}}'
        assert _gateway().parse_webhook(body, _sign(body)) is None
