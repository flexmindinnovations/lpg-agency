"""`POST /employees/{id}/enable-login` through the real ASGI stack.

The user-visible outcome is the point: a driver employee with no login gets
"No account is associated with this number" from Driver App sign-in, and after
an admin enables the login the same sign-in succeeds.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from lpg.api.v1.dependencies.identity import get_otp_delivery
from lpg.infrastructure.identity.password_hasher import Argon2PasswordHasher

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncEngine

    from lpg.config.settings import Settings

pytestmark = pytest.mark.integration

_PASSWORD = "correct-horse-battery-staple"


class _CapturingOtpDelivery:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def send(
        self,
        phone_number: str,
        code: str,
        *,
        purpose: str = "login",  # noqa: ARG002
    ) -> None:
        self.sent.append((phone_number, code))


@dataclass
class _Stack:
    client: AsyncClient
    otp_delivery: _CapturingOtpDelivery


@pytest.fixture
async def stack(
    integration_settings: Settings,
    postgres_available: bool,
    redis_available: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[_Stack]:
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable")
    if not redis_available:
        pytest.skip("Redis is not reachable")

    monkeypatch.setenv("LPG_ENVIRONMENT", "local")
    monkeypatch.setenv("LPG_DATABASE_URL", str(integration_settings.database_url))
    monkeypatch.setenv("LPG_REDIS_URL", str(integration_settings.redis_url))

    import redis.asyncio as redis_asyncio

    redis_client = redis_asyncio.from_url(  # type: ignore[no-untyped-call]
        str(integration_settings.redis_url)
    )
    await redis_client.flushdb()
    await redis_client.aclose()

    from lpg.api.app import create_app
    from lpg.config.settings import get_settings

    get_settings.cache_clear()
    app: FastAPI = create_app(integration_settings)
    otp_delivery = _CapturingOtpDelivery()
    app.dependency_overrides[get_otp_delivery] = lambda: otp_delivery
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield _Stack(client=client, otp_delivery=otp_delivery)
    get_settings.cache_clear()


@pytest.fixture
async def admin_engine_lpg_test(postgres_available: bool) -> AsyncIterator[AsyncEngine]:
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable")
    engine = create_async_engine(
        "postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:5433/lpg_test"
    )
    try:
        yield engine
    finally:
        await engine.dispose()


@dataclass
class _Agency:
    tenant_id: uuid.UUID
    slug: str
    branch_id: uuid.UUID
    admin_email: str


async def _seed_agency(engine: AsyncEngine) -> _Agency:
    from lpg.config.settings import Settings

    slug = f"enable-login-{uuid.uuid4().hex[:10]}"
    email = f"admin-{uuid.uuid4().hex[:8]}@example.com"
    password_hash = Argon2PasswordHasher(Settings(environment="local", log_json=False)).hash(
        _PASSWORD
    )
    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug) "
                    "VALUES (gen_random_uuid(), 'Enable Login Test', :slug) RETURNING id"
                ),
                {"slug": slug},
            )
        ).scalar_one()
        branch_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.branch (id, tenant_id, name) "
                    "VALUES (gen_random_uuid(), :tenant_id, 'Main') RETURNING id"
                ),
                {"tenant_id": str(tenant_id)},
            )
        ).scalar_one()
        user_id = (
            await conn.execute(
                text(
                    "INSERT INTO identity.identity_user "
                    "(id, tenant_id, branch_id, email, password_hash, role) "
                    "VALUES (gen_random_uuid(), :tenant_id, :branch_id, :email, :hash, "
                    "'agency_admin') RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "branch_id": str(branch_id),
                    "email": email,
                    "hash": password_hash,
                },
            )
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO identity.identity_user_permission "
                "(id, user_id, permission_id, created_at) "
                "SELECT gen_random_uuid(), :user_id, rp.permission_id, now() "
                "FROM identity.role_permission rp JOIN identity.role r ON r.id = rp.role_id "
                "WHERE r.code = 'agency_admin'"
            ),
            {"user_id": user_id},
        )
    return _Agency(
        tenant_id=uuid.UUID(str(tenant_id)),
        slug=slug,
        branch_id=uuid.UUID(str(branch_id)),
        admin_email=email,
    )


async def _seed_employee(
    engine: AsyncEngine, agency: _Agency, *, phone_number: str, role: str = "driver"
) -> uuid.UUID:
    employee_id = uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO tenant.employee "
                "(id, tenant_id, branch_id, employee_code, first_name, last_name, "
                "phone_number, role, status) "
                "VALUES (:id, :tenant_id, :branch_id, :code, 'Vijay', 'Naidu', :phone, :role, "
                "'active')"
            ),
            {
                "id": str(employee_id),
                "tenant_id": str(agency.tenant_id),
                "branch_id": str(agency.branch_id),
                "code": f"EMP-{uuid.uuid4().hex[:6]}",
                "phone": phone_number,
                "role": role,
            },
        )
    return employee_id


async def _login(client: AsyncClient, agency: _Agency) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login", json={"email": agency.admin_email, "password": _PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _driver_app_sign_in(stack: _Stack, agency: _Agency, phone_number: str) -> int:
    """The Driver App flow: request an OTP for (agency code, phone), then verify it."""
    stack.otp_delivery.sent.clear()
    request = await stack.client.post(
        "/api/v1/auth/otp/request", json={"tenant_id": agency.slug, "phone_number": phone_number}
    )
    assert request.status_code == 204, request.text
    _phone, code = stack.otp_delivery.sent[-1]
    verify = await stack.client.post(
        "/api/v1/auth/otp/verify",
        json={"tenant_id": agency.slug, "phone_number": phone_number, "code": code},
    )
    return verify.status_code


def _phone() -> str:
    return f"+91{uuid.uuid4().int % 10**10:010d}"


class TestEnableDriverLoginEndpoint:
    async def test_a_driver_with_no_login_can_sign_in_to_the_driver_app_once_enabled(
        self, stack: _Stack, admin_engine_lpg_test: AsyncEngine
    ) -> None:
        agency = await _seed_agency(admin_engine_lpg_test)
        phone = _phone()
        employee_id = await _seed_employee(admin_engine_lpg_test, agency, phone_number=phone)
        headers = await _login(stack.client, agency)

        # Before: exactly the failure drivers reported.
        assert await _driver_app_sign_in(stack, agency, phone) == 401

        response = await stack.client.post(
            f"/api/v1/employees/{employee_id}/enable-login", headers=headers
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["employee_id"] == str(employee_id)
        assert body["login_created"] is True
        assert body["driver_created"] is True
        # After: the same sign-in now works.
        assert await _driver_app_sign_in(stack, agency, phone) == 200

    async def test_repeating_it_is_a_harmless_no_op(
        self, stack: _Stack, admin_engine_lpg_test: AsyncEngine
    ) -> None:
        agency = await _seed_agency(admin_engine_lpg_test)
        employee_id = await _seed_employee(admin_engine_lpg_test, agency, phone_number=_phone())
        headers = await _login(stack.client, agency)
        first = await stack.client.post(
            f"/api/v1/employees/{employee_id}/enable-login", headers=headers
        )

        second = await stack.client.post(
            f"/api/v1/employees/{employee_id}/enable-login", headers=headers
        )

        assert second.status_code == 200, second.text
        assert second.json()["login_created"] is False
        assert second.json()["driver_created"] is False
        assert second.json()["driver_id"] == first.json()["driver_id"]

    async def test_a_staff_employee_is_rejected_with_422(
        self, stack: _Stack, admin_engine_lpg_test: AsyncEngine
    ) -> None:
        agency = await _seed_agency(admin_engine_lpg_test)
        employee_id = await _seed_employee(
            admin_engine_lpg_test, agency, phone_number=_phone(), role="manager"
        )
        headers = await _login(stack.client, agency)

        response = await stack.client.post(
            f"/api/v1/employees/{employee_id}/enable-login", headers=headers
        )

        assert response.status_code == 422, response.text
        assert "Users & Roles" in response.json()["detail"]

    async def test_a_login_already_linked_to_another_driver_is_a_409_with_a_clear_message(
        self, stack: _Stack, admin_engine_lpg_test: AsyncEngine
    ) -> None:
        agency = await _seed_agency(admin_engine_lpg_test)
        phone = _phone()
        first_employee = await _seed_employee(admin_engine_lpg_test, agency, phone_number=phone)
        second_employee = await _seed_employee(admin_engine_lpg_test, agency, phone_number=phone)
        headers = await _login(stack.client, agency)
        enabled = await stack.client.post(
            f"/api/v1/employees/{first_employee}/enable-login", headers=headers
        )
        assert enabled.status_code == 200, enabled.text

        response = await stack.client.post(
            f"/api/v1/employees/{second_employee}/enable-login", headers=headers
        )

        assert response.status_code == 409, response.text
        assert "already linked to another driver" in response.json()["detail"]

    async def test_an_unknown_employee_is_a_404(
        self, stack: _Stack, admin_engine_lpg_test: AsyncEngine
    ) -> None:
        agency = await _seed_agency(admin_engine_lpg_test)
        headers = await _login(stack.client, agency)

        response = await stack.client.post(
            f"/api/v1/employees/{uuid.uuid4()}/enable-login", headers=headers
        )

        assert response.status_code == 404, response.text

    async def test_it_requires_a_signed_in_user(self, stack: _Stack) -> None:
        response = await stack.client.post(f"/api/v1/employees/{uuid.uuid4()}/enable-login")

        assert response.status_code == 401
