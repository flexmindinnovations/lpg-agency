"""Per-agency Razorpay credentials (ADR-067): the use cases, gateway
resolution with fallback, audit redaction, and the per-agency webhook route.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lpg.api.v1.dependencies.payments import (
    get_gateway_builder,
    get_payment_credential_scope_factory,
    get_payment_webhook_tenant_resolver,
    get_payment_webhook_use_case_factory,
    get_platform_gateway,
)
from lpg.api.v1.routers import online_payment
from lpg.application.accounting.payment_credentials import (
    GetPaymentGatewaySettingsUseCase,
    RemovePaymentCredentialsUseCase,
    RotateWebhookTokenUseCase,
    SetPaymentCredentialsCommand,
    SetPaymentCredentialsUseCase,
    StoredPaymentCredentials,
    mask_key_id,
    mode_of,
)
from lpg.application.common.errors import NotFoundError, ValidationError
from lpg.config.settings import Settings
from lpg.infrastructure.payments.credentials import (
    gateway_from_credentials,
    platform_fallback,
    resolve_payment_gateway,
)
from lpg.infrastructure.payments.razorpay import RazorpayPaymentGateway
from lpg.infrastructure.persistence.audit import _audit_value

TENANT = uuid.uuid4()
LIVE_KEY = "rzp_live_AbCdEf123456"
TEST_KEY = "rzp_test_AbCdEf123456"


class FakeRepository:
    def __init__(self) -> None:
        self.row: StoredPaymentCredentials | None = None

    async def get(self) -> StoredPaymentCredentials | None:
        return self.row

    async def save(self, credentials: StoredPaymentCredentials) -> None:
        self.row = credentials

    async def delete(self) -> bool:
        existed = self.row is not None
        self.row = None
        return existed


def _set(repo: FakeRepository) -> SetPaymentCredentialsUseCase:
    return SetPaymentCredentialsUseCase(repo, AsyncMock(), fallback="none")


def _command(**overrides: str) -> SetPaymentCredentialsCommand:
    values = {"key_id": LIVE_KEY, "key_secret": "s3cret", "webhook_secret": "whsec"}
    values.update(overrides)
    return SetPaymentCredentialsCommand(tenant_id=TENANT, updated_by=None, **values)


def test_mode_and_mask() -> None:
    assert mode_of(LIVE_KEY) == "live"
    assert mode_of(TEST_KEY) == "test"
    assert mode_of("nonsense") is None
    assert mask_key_id(LIVE_KEY) == "rzp_live_••••••3456"
    assert "AbCdEf" not in mask_key_id(LIVE_KEY)


@pytest.mark.asyncio
async def test_save_returns_masked_view_without_secrets() -> None:
    repo = FakeRepository()
    result = await _set(repo).execute(_command())
    assert result.configured
    assert result.mode == "live"
    assert result.key_id_masked == "rzp_live_••••••3456"
    assert result.has_key_secret
    assert result.has_webhook_secret
    assert result.webhook_token
    assert "s3cret" not in repr(result)
    assert "whsec" not in repr(result)


@pytest.mark.asyncio
async def test_blank_secret_keeps_stored_one_when_key_unchanged() -> None:
    repo = FakeRepository()
    await _set(repo).execute(_command())
    first_token = repo.row.webhook_token  # type: ignore[union-attr]
    await _set(repo).execute(_command(key_secret="", webhook_secret=""))
    assert repo.row.key_secret == "s3cret"  # type: ignore[union-attr]
    assert repo.row.webhook_secret == "whsec"  # type: ignore[union-attr]
    assert repo.row.webhook_token == first_token  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_changing_key_id_requires_a_new_secret() -> None:
    repo = FakeRepository()
    await _set(repo).execute(_command())
    with pytest.raises(ValidationError):
        await _set(repo).execute(_command(key_id="rzp_live_ZzZzZz987654", key_secret=""))


@pytest.mark.asyncio
async def test_first_save_requires_a_secret() -> None:
    with pytest.raises(ValidationError):
        await _set(FakeRepository()).execute(_command(key_secret=""))


@pytest.mark.asyncio
async def test_malformed_key_id_is_refused() -> None:
    with pytest.raises(ValidationError):
        await _set(FakeRepository()).execute(_command(key_id="pk_live_abc"))


@pytest.mark.asyncio
async def test_test_key_is_accepted_and_reported_as_test_mode() -> None:
    result = await _set(FakeRepository()).execute(_command(key_id=TEST_KEY))
    assert result.mode == "test"


@pytest.mark.asyncio
async def test_blank_key_id_keeps_the_saved_one() -> None:
    repo = FakeRepository()
    await _set(repo).execute(_command())
    await _set(repo).execute(_command(key_id="", key_secret="", webhook_secret="newhook"))
    assert repo.row.key_id == LIVE_KEY  # type: ignore[union-attr]
    assert repo.row.webhook_secret == "newhook"  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_rotate_token_changes_only_the_token() -> None:
    repo = FakeRepository()
    await _set(repo).execute(_command())
    before = repo.row
    await RotateWebhookTokenUseCase(repo, AsyncMock(), fallback="none").execute(updated_by=None)
    assert repo.row.webhook_token != before.webhook_token  # type: ignore[union-attr]
    assert repo.row.key_secret == before.key_secret  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_rotate_and_remove_without_row_are_not_found() -> None:
    repo = FakeRepository()
    with pytest.raises(NotFoundError):
        await RotateWebhookTokenUseCase(repo, AsyncMock(), fallback="none").execute(updated_by=None)
    with pytest.raises(NotFoundError):
        await RemovePaymentCredentialsUseCase(repo, AsyncMock()).execute()


@pytest.mark.asyncio
async def test_remove_clears_the_row_and_reports_fallback() -> None:
    repo = FakeRepository()
    await _set(repo).execute(_command())
    await RemovePaymentCredentialsUseCase(repo, AsyncMock()).execute()
    view = await GetPaymentGatewaySettingsUseCase(repo).execute(fallback="platform")
    assert not view.configured
    assert view.source == "platform"


# -- gateway resolution ------------------------------------------------------


def _settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_agency_credentials_win_over_platform_default() -> None:
    repo = FakeRepository()
    await _set(repo).execute(_command())
    settings = _settings(razorpay_key_id="rzp_test_Platform1234", payments_allow_test_keys=True)
    gateway = await resolve_payment_gateway(settings, repo)
    assert isinstance(gateway, RazorpayPaymentGateway)
    assert gateway._key_id == LIVE_KEY
    assert gateway._key_secret == "s3cret"


@pytest.mark.asyncio
async def test_falls_back_to_platform_default_without_agency_key() -> None:
    settings = _settings(razorpay_key_id="rzp_test_Platform1234", payments_allow_test_keys=True)
    gateway = await resolve_payment_gateway(settings, FakeRepository())
    assert gateway._key_id == "rzp_test_Platform1234"  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_unconfigured_everywhere_is_not_configured() -> None:
    gateway = await resolve_payment_gateway(_settings(), FakeRepository())
    assert not gateway.is_configured
    assert platform_fallback(_settings()) == "none"
    assert platform_fallback(_settings(razorpay_key_id="rzp_test_x1234567")) == "platform"
    assert platform_fallback(_settings(payments_provider="mock")) == "demo"


# -- audit -------------------------------------------------------------------


def test_audit_never_records_secret_columns() -> None:
    assert _audit_value("key_secret_encrypted", "gAAAA-ciphertext") == "[redacted]"
    assert _audit_value("webhook_secret_encrypted", None) is None
    assert _audit_value("key_id", LIVE_KEY) == LIVE_KEY


# -- per-agency webhook route ------------------------------------------------


def _signed(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _paid_event(tenant_id: uuid.UUID) -> bytes:
    return json.dumps(
        {
            "event": "payment_link.paid",
            "payload": {
                "payment_link": {
                    "entity": {
                        "id": "plink_1",
                        "status": "paid",
                        "notes": {"tenant_id": str(tenant_id)},
                    }
                },
                "payment": {"entity": {"id": "pay_1", "method": "upi", "created_at": 1}},
            },
        }
    ).encode()


def _client(
    *, stored: StoredPaymentCredentials | None, resolved: uuid.UUID | None
) -> tuple[TestClient, AsyncMock]:
    use_case = AsyncMock()

    @asynccontextmanager
    async def use_case_factory(_tenant_id: uuid.UUID):  # type: ignore[no-untyped-def]
        yield use_case

    repo = FakeRepository()
    repo.row = stored

    @asynccontextmanager
    async def scope(_tenant_id: uuid.UUID):  # type: ignore[no-untyped-def]
        yield repo

    resolver = MagicMock()
    resolver.resolve = AsyncMock(return_value=resolved)
    app = FastAPI()
    app.include_router(online_payment.router)
    app.dependency_overrides[get_payment_webhook_tenant_resolver] = lambda: resolver
    app.dependency_overrides[get_payment_credential_scope_factory] = lambda: scope
    app.dependency_overrides[get_payment_webhook_use_case_factory] = lambda: use_case_factory
    app.dependency_overrides[get_gateway_builder] = lambda: (
        lambda creds: gateway_from_credentials(_settings(), creds)
    )
    app.dependency_overrides[get_platform_gateway] = lambda: MagicMock()
    return TestClient(app), use_case


def _stored(secret: str | None = "whsec") -> StoredPaymentCredentials:  # noqa: S107
    return StoredPaymentCredentials(
        tenant_id=TENANT,
        key_id=LIVE_KEY,
        key_secret="s3cret",
        webhook_secret=secret,
        webhook_token="tok",
        updated_at=datetime.now(UTC),
    )


def test_agency_webhook_applies_event_signed_with_its_own_secret() -> None:
    client, use_case = _client(stored=_stored(), resolved=TENANT)
    body = _paid_event(TENANT)
    response = client.post(
        "/payments/razorpay/webhook/tok",
        content=body,
        headers={"X-Razorpay-Signature": _signed(body, "whsec")},
    )
    assert response.status_code == 200
    use_case.execute.assert_awaited_once()


def test_agency_webhook_rejects_another_agencys_secret() -> None:
    client, use_case = _client(stored=_stored(), resolved=TENANT)
    body = _paid_event(TENANT)
    response = client.post(
        "/payments/razorpay/webhook/tok",
        content=body,
        headers={"X-Razorpay-Signature": _signed(body, "someone-elses")},
    )
    assert response.status_code == 400
    use_case.execute.assert_not_awaited()


def test_agency_webhook_ignores_event_naming_a_different_tenant() -> None:
    client, use_case = _client(stored=_stored(), resolved=TENANT)
    body = _paid_event(uuid.uuid4())
    response = client.post(
        "/payments/razorpay/webhook/tok",
        content=body,
        headers={"X-Razorpay-Signature": _signed(body, "whsec")},
    )
    assert response.status_code == 200
    use_case.execute.assert_not_awaited()


def test_agency_webhook_unknown_token_is_404() -> None:
    client, _ = _client(stored=None, resolved=None)
    assert client.post("/payments/razorpay/webhook/nope", content=b"{}").status_code == 404


def test_agency_webhook_without_webhook_secret_is_refused() -> None:
    client, use_case = _client(stored=_stored(secret=None), resolved=TENANT)
    body = _paid_event(TENANT)
    response = client.post(
        "/payments/razorpay/webhook/tok",
        content=body,
        headers={"X-Razorpay-Signature": _signed(body, "")},
    )
    assert response.status_code == 400
    use_case.execute.assert_not_awaited()
