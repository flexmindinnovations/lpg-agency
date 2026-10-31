"""Per-agency Razorpay credentials (ADR-067) through the real ASGI stack and
PostgreSQL: encrypted at rest, write-only, audited, row-level isolated, and
resolved by the per-agency webhook URL. Razorpay itself is never called.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from typing import TYPE_CHECKING

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from lpg.infrastructure.identity.password_hasher import Argon2PasswordHasher

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncEngine

    from lpg.config.settings import Settings

pytestmark = pytest.mark.integration

PASSWORD = "correct horse battery staple 42"
KEY_ID = "rzp_live_IntegrationKey1"
KEY_SECRET = "integration-key-secret-value"
WEBHOOK_SECRET = "integration-webhook-secret"


@pytest.fixture
async def client(
    integration_settings: Settings,
    postgres_available: bool,
    redis_available: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[AsyncClient]:
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable")
    if not redis_available:
        pytest.skip("Redis is not reachable")
    monkeypatch.setenv("LPG_ENVIRONMENT", "local")
    monkeypatch.setenv("LPG_DATABASE_URL", str(integration_settings.database_url))
    monkeypatch.setenv("LPG_REDIS_URL", str(integration_settings.redis_url))

    from lpg.api.app import create_app
    from lpg.config.settings import get_settings

    get_settings.cache_clear()
    app: FastAPI = create_app(integration_settings)
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
            yield http_client
    get_settings.cache_clear()


@pytest.fixture
async def admin(postgres_available: bool) -> AsyncIterator[AsyncEngine]:
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable")
    engine = create_async_engine(
        "postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:5433/lpg_test"
    )
    try:
        yield engine
    finally:
        await engine.dispose()


async def _seed_agency_admin(engine: AsyncEngine, settings: Settings) -> tuple[uuid.UUID, str]:
    email = f"{uuid.uuid4().hex}@payment-gateway.example"
    role = "agency_admin"
    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), 'Gateway Tenant', :slug, 'ops@example.com') "
                    "RETURNING id"
                ),
                {"slug": f"pay-gw-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
        user_id = (
            await conn.execute(
                text(
                    "INSERT INTO identity.identity_user "
                    "(id, tenant_id, email, password_hash, role) "
                    "VALUES (gen_random_uuid(), :tenant_id, :email, :hash, :role) RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "email": email,
                    "hash": Argon2PasswordHasher(settings).hash(PASSWORD),
                    "role": role,
                },
            )
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO identity.identity_user_permission "
                "(id, user_id, permission_id, created_at) "
                "SELECT gen_random_uuid(), :user_id, rp.permission_id, now() "
                "FROM identity.role_permission rp JOIN identity.role r ON r.id = rp.role_id "
                "WHERE r.code = :role"
            ),
            {"user_id": user_id, "role": role},
        )
    return uuid.UUID(str(tenant_id)), email


async def _headers(client: AsyncClient, email: str) -> dict[str, str]:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _event(tenant_id: uuid.UUID) -> bytes:
    return json.dumps(
        {
            "event": "payment_link.paid",
            "payload": {
                "payment_link": {
                    "entity": {
                        "id": "plink_unknown",
                        "status": "paid",
                        "notes": {"tenant_id": str(tenant_id)},
                    }
                },
                "payment": {"entity": {"id": "pay_1", "method": "upi", "created_at": 1}},
            },
        }
    ).encode()


@pytest.mark.asyncio
class TestPaymentGatewayCredentials:
    async def test_save_is_masked_encrypted_audited_and_resolves_webhook(
        self, client: AsyncClient, admin: AsyncEngine, integration_settings: Settings
    ) -> None:
        tenant_id, email = await _seed_agency_admin(admin, integration_settings)
        headers = await _headers(client, email)

        empty = (await client.get("/api/v1/payment-gateway", headers=headers)).json()
        assert empty["configured"] is False
        assert empty["webhook_path"] == ""

        saved = await client.put(
            "/api/v1/payment-gateway",
            headers=headers,
            json={
                "key_id": KEY_ID,
                "key_secret": KEY_SECRET,
                "webhook_secret": WEBHOOK_SECRET,
            },
        )
        assert saved.status_code == 200, saved.text
        view = saved.json()
        assert view["configured"] is True
        assert view["source"] == "agency"
        assert view["mode"] == "live"
        assert view["key_id_masked"].startswith("rzp_live_")
        assert KEY_ID not in saved.text
        assert KEY_SECRET not in saved.text
        assert WEBHOOK_SECRET not in saved.text
        assert view["webhook_path"].startswith("/api/v1/payments/razorpay/webhook/")

        # Ciphertext at rest, never the plaintext secrets.
        async with admin.begin() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT key_secret_encrypted, webhook_secret_encrypted "
                        "FROM accounting.payment_gateway_credential WHERE tenant_id = :t"
                    ),
                    {"t": str(tenant_id)},
                )
            ).one()
            assert KEY_SECRET not in row[0]
            assert WEBHOOK_SECRET not in row[1]

            audit = (
                (
                    await conn.execute(
                        text(
                            "SELECT after_state::text FROM audit.audit_log "
                            "WHERE tenant_id = :t AND entity_name = 'payment_gateway_credential'"
                        ),
                        {"t": str(tenant_id)},
                    )
                )
                .scalars()
                .all()
            )
        assert audit, "saving credentials must be audit-logged"
        for state in audit:
            assert KEY_SECRET not in state
            assert row[0] not in state
            assert "[redacted]" in state

        # A re-save with blank secrets keeps them and the webhook URL.
        resaved = await client.put(
            "/api/v1/payment-gateway", headers=headers, json={"key_id": KEY_ID}
        )
        assert resaved.status_code == 200
        assert resaved.json()["webhook_path"] == view["webhook_path"]

        # The per-agency URL verifies against this agency's own secret.
        body = _event(tenant_id)
        good = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
        accepted = await client.post(
            view["webhook_path"], content=body, headers={"X-Razorpay-Signature": good}
        )
        assert accepted.status_code == 200
        bad = hmac.new(b"other", body, hashlib.sha256).hexdigest()
        rejected = await client.post(
            view["webhook_path"], content=body, headers={"X-Razorpay-Signature": bad}
        )
        assert rejected.status_code == 400
        unknown = await client.post(
            "/api/v1/payments/razorpay/webhook/not-a-real-token", content=body
        )
        assert unknown.status_code == 404

        # Rotating the token retires the old URL.
        rotated = (
            await client.post("/api/v1/payment-gateway/rotate-webhook-token", headers=headers)
        ).json()
        assert rotated["webhook_path"] != view["webhook_path"]
        old = await client.post(
            view["webhook_path"], content=body, headers={"X-Razorpay-Signature": good}
        )
        assert old.status_code == 404

        # Removing falls back to the platform default.
        assert (await client.delete("/api/v1/payment-gateway", headers=headers)).status_code == 204
        gone = (await client.get("/api/v1/payment-gateway", headers=headers)).json()
        assert gone["configured"] is False

    async def test_agencies_cannot_see_each_others_credentials(
        self, client: AsyncClient, admin: AsyncEngine, integration_settings: Settings
    ) -> None:
        _, first_email = await _seed_agency_admin(admin, integration_settings)
        _, second_email = await _seed_agency_admin(admin, integration_settings)
        first = await _headers(client, first_email)
        second = await _headers(client, second_email)
        await client.put(
            "/api/v1/payment-gateway",
            headers=first,
            json={"key_id": KEY_ID, "key_secret": KEY_SECRET},
        )
        other = (await client.get("/api/v1/payment-gateway", headers=second)).json()
        assert other["configured"] is False

    async def test_availability_reflects_the_agencys_own_key(
        self, client: AsyncClient, admin: AsyncEngine, integration_settings: Settings
    ) -> None:
        _, email = await _seed_agency_admin(admin, integration_settings)
        headers = await _headers(client, email)
        before = await client.get("/api/v1/online-payments/availability", headers=headers)
        assert before.json()["available"] is False
        await client.put(
            "/api/v1/payment-gateway",
            headers=headers,
            json={"key_id": KEY_ID, "key_secret": KEY_SECRET},
        )
        after = await client.get("/api/v1/online-payments/availability", headers=headers)
        assert after.json()["available"] is True
