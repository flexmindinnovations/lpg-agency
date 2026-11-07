"""One record per phone, and a name asked only for phones the agency has not
seen (ADR-072), through the real ASGI stack, PostgreSQL and Redis."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy import text

from tests.integration.device_support import PASSWORD, login_headers, seed_agency

if TYPE_CHECKING:
    from httpx import AsyncClient, Response
    from sqlalchemy.ext.asyncio import AsyncEngine

    from lpg.infrastructure.identity.password_hasher import Argon2PasswordHasher
    from lpg.infrastructure.persistence.database import Database

pytestmark = pytest.mark.integration

_DEVICES = "/api/v1/admin/license/devices"
_ME = "/api/v1/devices/me"


@pytest.fixture
def client(devices_client: AsyncClient) -> AsyncClient:
    return devices_client


@pytest.fixture
def hasher(devices_hasher: Argon2PasswordHasher) -> Argon2PasswordHasher:
    return devices_hasher


@pytest.fixture
def database(devices_database: Database) -> Database:
    return devices_database


def _install_id() -> str:
    return uuid.uuid4().hex + uuid.uuid4().hex[:8]


async def _driver(engine: AsyncEngine, hasher: Argon2PasswordHasher, tenant_id: uuid.UUID) -> str:
    email = f"driver-{uuid.uuid4().hex[:10]}@devices.example"
    async with engine.begin() as conn:
        user_id = (
            await conn.execute(
                text(
                    "INSERT INTO identity.identity_user "
                    "(id, tenant_id, email, password_hash, role) "
                    "VALUES (gen_random_uuid(), :t, :e, :h, 'driver') RETURNING id"
                ),
                {"t": str(tenant_id), "e": email, "h": hasher.hash(PASSWORD)},
            )
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO identity.identity_user_permission "
                "(id, user_id, permission_id, created_at) "
                "SELECT gen_random_uuid(), :u, rp.permission_id, now() "
                "FROM identity.role_permission rp "
                "JOIN identity.role r ON r.id = rp.role_id WHERE r.code = 'driver'"
            ),
            {"u": user_id},
        )
    return email


async def _sign_in(
    client: AsyncClient, email: str, install_id: str, hardware_id: str, name: str | None = None
) -> Response:
    device: dict[str, Any] = {
        "manufacturer": "Xiaomi",
        "model": "Redmi 12",
        "platform": "android",
        "hardware_id": hardware_id,
    }
    if name is not None:
        device["name"] = name
    return await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD, "device": device},
        headers={"X-Device-Id": install_id, "X-App-Type": "driver_app"},
    )


def _bearer(response: Response, install_id: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {response.json()['access_token']}",
        "X-Device-Id": install_id,
        "X-App-Type": "driver_app",
    }


async def _enforce(client: AsyncClient, admin: dict[str, str]) -> None:
    response = await client.post(
        "/api/v1/admin/tenant-configuration",
        headers=admin,
        json={"config_key": "device_control", "config_value": "enforce"},
    )
    assert response.status_code == 201, response.text


async def test_a_new_phone_gets_a_default_name_and_is_asked_to_pick_one(
    client: AsyncClient, admin_engine: AsyncEngine, hasher: Argon2PasswordHasher
) -> None:
    agency = await seed_agency(admin_engine, hasher)
    admin = await login_headers(client, agency.admin_email)
    await _enforce(client, admin)
    driver = await _driver(admin_engine, hasher, agency.tenant_id)
    install_id = _install_id()

    signed_in = await _sign_in(client, driver, install_id, "android-id-1")
    mine = await client.get(_ME, headers=_bearer(signed_in, install_id))

    assert mine.status_code == 200, mine.text
    assert mine.json()["needs_name"] is True
    assert mine.json()["display_name"].startswith("device_")

    # A waiting phone can still name itself.
    named = await client.put(
        _ME + "/name", headers=_bearer(signed_in, install_id), json={"name": "Van 2"}
    )
    assert named.status_code == 200, named.text
    assert named.json()["display_name"] == "Van 2"
    assert named.json()["needs_name"] is False
    assert named.json()["status"] == "pending"


async def test_a_reinstalled_phone_is_the_same_record_and_is_not_asked_again(
    client: AsyncClient, admin_engine: AsyncEngine, hasher: Argon2PasswordHasher
) -> None:
    agency = await seed_agency(admin_engine, hasher)
    admin = await login_headers(client, agency.admin_email)
    await _enforce(client, admin)
    driver = await _driver(admin_engine, hasher, agency.tenant_id)
    first_install = _install_id()
    first = await _sign_in(client, driver, first_install, "android-id-same")
    await client.put(_ME + "/name", headers=_bearer(first, first_install), json={"name": "Van 2"})
    [device] = (await client.get(_DEVICES, headers=admin)).json()
    approve = await client.post(f"{_DEVICES}/{device['id']}/approve", headers=admin)
    assert approve.status_code == 200, approve.text

    # App reinstalled: new random install ID, same Android ID.
    second_install = _install_id()
    second = await _sign_in(client, driver, second_install, "android-id-same")
    mine = await client.get(_ME, headers=_bearer(second, second_install))

    assert mine.json()["needs_name"] is False
    assert mine.json()["display_name"] == "Van 2"
    assert mine.json()["status"] == "approved"
    devices = (await client.get(_DEVICES, headers=admin)).json()
    assert len(devices) == 1
    assert devices[0]["id"] == device["id"]
    # The old install no longer matches the record.
    stale = await client.get(_ME, headers=_bearer(second, first_install))
    assert stale.status_code == 401


async def test_two_phones_cannot_share_a_name(
    client: AsyncClient, admin_engine: AsyncEngine, hasher: Argon2PasswordHasher
) -> None:
    agency = await seed_agency(admin_engine, hasher)
    admin = await login_headers(client, agency.admin_email)
    await _enforce(client, admin)
    driver = await _driver(admin_engine, hasher, agency.tenant_id)
    one, two = _install_id(), _install_id()
    first = await _sign_in(client, driver, one, "android-id-a")
    second = await _sign_in(client, driver, two, "android-id-b")
    ok = await client.put(_ME + "/name", headers=_bearer(first, one), json={"name": "Van 2"})
    assert ok.status_code == 200, ok.text

    clash = await client.put(_ME + "/name", headers=_bearer(second, two), json={"name": "  van 2 "})

    assert clash.status_code == 409
    assert clash.json()["error_code"] == "DUPLICATE_DEVICE_NAME"
    assert "van 2 2" in clash.json()["detail"]


async def test_the_database_refuses_two_records_for_one_phone(
    client: AsyncClient, admin_engine: AsyncEngine, hasher: Argon2PasswordHasher
) -> None:
    from sqlalchemy.exc import IntegrityError

    agency = await seed_agency(admin_engine, hasher)
    admin = await login_headers(client, agency.admin_email)
    await _enforce(client, admin)
    driver = await _driver(admin_engine, hasher, agency.tenant_id)
    install_id = _install_id()
    await _sign_in(client, driver, install_id, "android-id-dup")

    with pytest.raises(IntegrityError):
        async with admin_engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO platform.linked_device (id, tenant_id, license_id, app_type, "
                    "device_identifier, display_name, status, hardware_ref) "
                    "SELECT gen_random_uuid(), tenant_id, license_id, app_type, 'other', 'x', "
                    "status, hardware_ref FROM platform.linked_device WHERE tenant_id = :t"
                ),
                {"t": str(agency.tenant_id)},
            )
