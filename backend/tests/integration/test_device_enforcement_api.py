"""Device control, end to end through the real ASGI stack and a real
PostgreSQL + Redis (ADR-071): sign-in binding, the per-request check, blocking
a running session, refresh, the three agency modes, the seat limit, and
tenant isolation.

A driver signs in with email + password here only because it is the simplest
way to get a `driver`-role session; the rules under test do not depend on how
the login happened.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy import text

from tests.integration.device_support import (
    PASSWORD,
    Agency,
    login_headers,
    seed_agency,
    set_device_cap,
)

if TYPE_CHECKING:
    from httpx import AsyncClient, Response
    from sqlalchemy.ext.asyncio import AsyncEngine

    from lpg.infrastructure.identity.password_hasher import Argon2PasswordHasher
    from lpg.infrastructure.persistence.database import Database

pytestmark = pytest.mark.integration


@pytest.fixture
def client(devices_client: AsyncClient) -> AsyncClient:
    return devices_client


@pytest.fixture
def hasher(devices_hasher: Argon2PasswordHasher) -> Argon2PasswordHasher:
    return devices_hasher


@pytest.fixture
def database(devices_database: Database) -> Database:
    return devices_database


_DEVICES = "/api/v1/admin/license/devices"
_ME = "/api/v1/auth/me"


async def _seed_driver(engine: AsyncEngine, hasher: Argon2PasswordHasher, agency: Agency) -> str:
    email = f"driver-{uuid.uuid4().hex[:10]}@devices.example"
    async with engine.begin() as conn:
        user_id = (
            await conn.execute(
                text(
                    "INSERT INTO identity.identity_user "
                    "(id, tenant_id, email, password_hash, role) "
                    "VALUES (gen_random_uuid(), :t, :e, :h, 'driver') RETURNING id"
                ),
                {"t": str(agency.tenant_id), "e": email, "h": hasher.hash(PASSWORD)},
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


def _phone(install_id: str | None, app_type: str | None = None) -> dict[str, str]:
    headers: dict[str, str] = {}
    if install_id is not None:
        headers["X-Device-Id"] = install_id
    if app_type is not None:
        headers["X-App-Type"] = app_type
    return headers


def _new_install_id() -> str:
    return uuid.uuid4().hex + uuid.uuid4().hex[:8]


async def _set_mode(client: AsyncClient, admin: dict[str, str], mode: str) -> None:
    response = await client.post(
        "/api/v1/admin/tenant-configuration",
        headers=admin,
        json={"config_key": "device_control", "config_value": mode},
    )
    assert response.status_code == 201, response.text


async def _sign_in(
    client: AsyncClient,
    email: str,
    install_id: str | None,
    *,
    app_type: str | None = None,
    name: str | None = "Ravi's phone",
) -> Response:
    body: dict[str, Any] = {"email": email, "password": PASSWORD}
    if install_id is not None:
        body["device"] = {
            "name": name,
            "manufacturer": "Xiaomi",
            "model": "Redmi 12",
            "os_version": "Android 13",
            "app_version": "1.4.0",
            "platform": "android",
            "hardware_id": "android-id-" + install_id[:6],
        }
    return await client.post("/api/v1/auth/login", json=body, headers=_phone(install_id, app_type))


def _bearer(
    response: Response, install_id: str | None, app_type: str | None = None
) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {response.json()['access_token']}",
        **_phone(install_id, app_type),
    }


async def _devices(
    client: AsyncClient, admin: dict[str, str], **params: str
) -> list[dict[str, Any]]:
    response = await client.get(_DEVICES, headers=admin, params=params)
    assert response.status_code == 200, response.text
    body: list[dict[str, Any]] = response.json()
    return body


class TestOffByDefault:
    async def test_nothing_is_enforced_or_recorded_until_an_admin_switches_it_on(
        self, client: AsyncClient, admin_engine: AsyncEngine, hasher: Argon2PasswordHasher
    ) -> None:
        agency = await seed_agency(admin_engine, hasher)
        driver = await _seed_driver(admin_engine, hasher, agency)
        admin = await login_headers(client, agency.admin_email)
        install_id = _new_install_id()

        # An old app that sends nothing, and a new one that sends its phone.
        old = await _sign_in(client, driver, None)
        new = await _sign_in(client, driver, install_id)

        assert old.status_code == 200, old.text
        assert new.status_code == 200, new.text
        assert (await client.get(_ME, headers=_bearer(old, None))).status_code == 200
        assert (await client.get(_ME, headers=_bearer(new, install_id))).status_code == 200
        assert await _devices(client, admin) == []
        mine = await client.get("/api/v1/devices/me", headers=_bearer(new, install_id))
        assert mine.json()["control"] == "off"
        assert mine.json()["allowed"] is True


class TestObserve:
    async def test_phones_register_themselves_as_approved_and_nobody_is_blocked(
        self, client: AsyncClient, admin_engine: AsyncEngine, hasher: Argon2PasswordHasher
    ) -> None:
        agency = await seed_agency(admin_engine, hasher)
        driver = await _seed_driver(admin_engine, hasher, agency)
        admin = await login_headers(client, agency.admin_email)
        await _set_mode(client, admin, "observe")
        install_id = _new_install_id()

        signed_in = await _sign_in(client, driver, install_id)

        assert signed_in.status_code == 200, signed_in.text
        [device] = await _devices(client, admin)
        assert device["status"] == "approved"
        assert device["app_type"] == "driver_app"
        assert device["model"] == "Redmi 12"
        assert device["os_version"] == "Android 13"
        assert device["app_version"] == "1.4.0"
        assert device["display_name"] == "Ravi's phone"
        assert device["last_user_name"] == driver
        assert install_id not in str(device)  # only a short reference is exposed
        assert (await client.get(_ME, headers=_bearer(signed_in, install_id))).status_code == 200

        # Even a phone the admin then blocks is not stopped while only observing.
        block = await client.post(f"{_DEVICES}/{device['id']}/block", headers=admin)
        assert block.status_code == 200
        assert (await client.get(_ME, headers=_bearer(signed_in, install_id))).status_code == 200

    async def test_a_full_plan_leaves_the_extra_phone_waiting_but_still_not_blocked(
        self, client: AsyncClient, admin_engine: AsyncEngine, hasher: Argon2PasswordHasher
    ) -> None:
        agency = await seed_agency(admin_engine, hasher)
        driver = await _seed_driver(admin_engine, hasher, agency)
        admin = await login_headers(client, agency.admin_email)
        await set_device_cap(admin_engine, agency.tenant_id, {"driver_app": 1})
        await _set_mode(client, admin, "observe")
        first, second = _new_install_id(), _new_install_id()

        await _sign_in(client, driver, first)
        late = await _sign_in(client, driver, second)

        statuses = sorted(d["status"] for d in await _devices(client, admin))
        assert statuses == ["approved", "pending"]
        assert (await client.get(_ME, headers=_bearer(late, second))).status_code == 200

    async def test_the_admin_app_is_recorded_when_it_says_so_and_the_dashboard_is_not(
        self, client: AsyncClient, admin_engine: AsyncEngine, hasher: Argon2PasswordHasher
    ) -> None:
        agency = await seed_agency(admin_engine, hasher)
        admin = await login_headers(client, agency.admin_email)
        await _set_mode(client, admin, "observe")

        dashboard = await _sign_in(client, agency.manager_email, None)
        install_id = _new_install_id()
        app = await _sign_in(client, agency.manager_email, install_id, app_type="admin_app")

        assert dashboard.status_code == 200
        assert app.status_code == 200
        [device] = await _devices(client, admin)
        assert device["app_type"] == "admin_app"


class TestEnforce:
    async def _enforcing(
        self, client: AsyncClient, admin_engine: AsyncEngine, hasher: Argon2PasswordHasher
    ) -> tuple[Agency, str, dict[str, str]]:
        agency = await seed_agency(admin_engine, hasher)
        driver = await _seed_driver(admin_engine, hasher, agency)
        admin = await login_headers(client, agency.admin_email)
        await _set_mode(client, admin, "enforce")
        return agency, driver, admin

    async def test_a_new_phone_waits_then_works_once_approved(
        self, client: AsyncClient, admin_engine: AsyncEngine, hasher: Argon2PasswordHasher
    ) -> None:
        _agency, driver, admin = await self._enforcing(client, admin_engine, hasher)
        install_id = _new_install_id()

        signed_in = await _sign_in(client, driver, install_id)
        assert signed_in.status_code == 200, signed_in.text
        mine = _bearer(signed_in, install_id)

        waiting = await client.get(_ME, headers=mine)
        assert waiting.status_code == 403
        assert waiting.json()["error_code"] == "DEVICE_PENDING"
        state = await client.get("/api/v1/devices/me", headers=mine)
        assert state.status_code == 200, state.text
        assert state.json()["status"] == "pending"
        assert state.json()["allowed"] is False

        [device] = await _devices(client, admin, status="pending")
        assert (await client.get(f"{_DEVICES}/pending-count", headers=admin)).json() == {"count": 1}
        approve = await client.post(f"{_DEVICES}/{device['id']}/approve", headers=admin)
        assert approve.status_code == 200, approve.text

        # The very next request sees the approval (the admin action cleared the cache).
        assert (await client.get(_ME, headers=mine)).status_code == 200
        state = await client.get("/api/v1/devices/me", headers=mine)
        assert state.json()["status"] == "approved"
        assert state.json()["allowed"] is True

    async def test_blocking_stops_a_running_session_at_once_and_ends_its_refresh_token(
        self, client: AsyncClient, admin_engine: AsyncEngine, hasher: Argon2PasswordHasher
    ) -> None:
        _agency, driver, admin = await self._enforcing(client, admin_engine, hasher)
        install_id = _new_install_id()
        signed_in = await _sign_in(client, driver, install_id)
        [device] = await _devices(client, admin)
        await client.post(f"{_DEVICES}/{device['id']}/approve", headers=admin)
        mine = _bearer(signed_in, install_id)
        assert (await client.get(_ME, headers=mine)).status_code == 200

        await client.post(f"{_DEVICES}/{device['id']}/block", headers=admin)

        blocked = await client.get(_ME, headers=mine)
        assert blocked.status_code == 403
        assert blocked.json()["error_code"] == "DEVICE_BLOCKED"
        # The blocked phone can still ask what happened, to show the right screen.
        state = await client.get("/api/v1/devices/me", headers=mine)
        assert state.json()["status"] == "blocked"
        assert state.json()["allowed"] is False
        # Its refresh token no longer works, and signing in again is refused.
        refresh = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": signed_in.json()["refresh_token"]},
            headers=_phone(install_id),
        )
        assert refresh.status_code == 401
        again = await _sign_in(client, driver, install_id)
        assert again.status_code == 403
        assert again.json()["error_code"] == "DEVICE_BLOCKED"

        # Unblocking lets the user sign in again.
        await client.post(f"{_DEVICES}/{device['id']}/unblock", headers=admin)
        back = await _sign_in(client, driver, install_id)
        assert back.status_code == 200, back.text
        assert (await client.get(_ME, headers=_bearer(back, install_id))).status_code == 200

    async def test_removing_a_phone_signs_it_out_and_it_must_ask_again(
        self, client: AsyncClient, admin_engine: AsyncEngine, hasher: Argon2PasswordHasher
    ) -> None:
        _agency, driver, admin = await self._enforcing(client, admin_engine, hasher)
        install_id = _new_install_id()
        signed_in = await _sign_in(client, driver, install_id)
        [device] = await _devices(client, admin)
        await client.post(f"{_DEVICES}/{device['id']}/approve", headers=admin)

        await client.post(f"{_DEVICES}/{device['id']}/remove", headers=admin)

        gone = await client.get(_ME, headers=_bearer(signed_in, install_id))
        assert gone.status_code == 403
        assert gone.json()["error_code"] == "DEVICE_REMOVED"
        again = await _sign_in(client, driver, install_id)
        assert again.status_code == 200
        assert (await client.get(_ME, headers=_bearer(again, install_id))).json()[
            "error_code"
        ] == "DEVICE_PENDING"
        [reopened] = await _devices(client, admin)
        assert reopened["id"] == device["id"]
        assert reopened["status"] == "pending"

    async def test_a_driver_cannot_sign_in_without_identifying_the_phone(
        self, client: AsyncClient, admin_engine: AsyncEngine, hasher: Argon2PasswordHasher
    ) -> None:
        _agency, driver, admin = await self._enforcing(client, admin_engine, hasher)

        response = await _sign_in(client, driver, None)

        assert response.status_code == 401
        assert response.json()["error_code"] == "DEVICE_REQUIRED"
        assert await _devices(client, admin) == []

    async def test_a_session_cannot_be_moved_to_another_phone(
        self, client: AsyncClient, admin_engine: AsyncEngine, hasher: Argon2PasswordHasher
    ) -> None:
        _agency, driver, admin = await self._enforcing(client, admin_engine, hasher)
        install_id = _new_install_id()
        signed_in = await _sign_in(client, driver, install_id)
        [device] = await _devices(client, admin)
        await client.post(f"{_DEVICES}/{device['id']}/approve", headers=admin)
        thief = _new_install_id()

        for headers in (_bearer(signed_in, thief), _bearer(signed_in, None)):
            response = await client.get(_ME, headers=headers)
            assert response.status_code == 401
            assert response.json()["error_code"] == "DEVICE_REQUIRED"
            same = await client.get("/api/v1/devices/me", headers=headers)
            assert same.status_code == 401
        stolen_refresh = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": signed_in.json()["refresh_token"]},
            headers=_phone(thief),
        )
        assert stolen_refresh.status_code == 401
        assert stolen_refresh.json()["error_code"] == "DEVICE_REQUIRED"

    async def test_refresh_keeps_the_session_bound_to_its_phone(
        self, client: AsyncClient, admin_engine: AsyncEngine, hasher: Argon2PasswordHasher
    ) -> None:
        _agency, driver, admin = await self._enforcing(client, admin_engine, hasher)
        install_id = _new_install_id()
        signed_in = await _sign_in(client, driver, install_id)
        [device] = await _devices(client, admin)
        await client.post(f"{_DEVICES}/{device['id']}/approve", headers=admin)

        refreshed = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": signed_in.json()["refresh_token"]},
            headers=_phone(install_id),
        )

        assert refreshed.status_code == 200, refreshed.text
        assert (await client.get(_ME, headers=_bearer(refreshed, install_id))).status_code == 200
        assert len(await _devices(client, admin)) == 1

    async def test_a_session_opened_before_control_was_switched_on_binds_itself_at_refresh(
        self, client: AsyncClient, admin_engine: AsyncEngine, hasher: Argon2PasswordHasher
    ) -> None:
        agency = await seed_agency(admin_engine, hasher)
        driver = await _seed_driver(admin_engine, hasher, agency)
        admin = await login_headers(client, agency.admin_email)
        install_id = _new_install_id()
        old_session = await _sign_in(client, driver, None)  # control is off: no phone
        await _set_mode(client, admin, "enforce")

        # The unbound driver token is refused with a 401 the app answers by refreshing.
        refused = await client.get(_ME, headers=_bearer(old_session, install_id))
        assert refused.status_code == 401
        assert refused.json()["error_code"] == "DEVICE_REQUIRED"
        refreshed = await client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": old_session.json()["refresh_token"],
                "device": {"model": "Redmi 12"},
            },
            headers=_phone(install_id),
        )

        assert refreshed.status_code == 200, refreshed.text
        [device] = await _devices(client, admin)
        assert device["status"] == "pending"
        waiting = await client.get(_ME, headers=_bearer(refreshed, install_id))
        assert waiting.json()["error_code"] == "DEVICE_PENDING"

    async def test_staff_on_the_web_dashboard_and_customers_are_not_affected(
        self, client: AsyncClient, admin_engine: AsyncEngine, hasher: Argon2PasswordHasher
    ) -> None:
        agency, _, admin = await self._enforcing(client, admin_engine, hasher)

        manager = await _sign_in(client, agency.manager_email, None)

        assert manager.status_code == 200
        assert (await client.get(_ME, headers=_bearer(manager, None))).status_code == 200
        assert (await client.get(_ME, headers=admin)).status_code == 200

    async def test_a_waiting_admin_app_phone_is_refused_until_approved(
        self, client: AsyncClient, admin_engine: AsyncEngine, hasher: Argon2PasswordHasher
    ) -> None:
        agency, _, _admin = await self._enforcing(client, admin_engine, hasher)
        install_id = _new_install_id()

        signed_in = await _sign_in(client, agency.manager_email, install_id, app_type="admin_app")

        assert signed_in.status_code == 200, signed_in.text
        waiting = await client.get(_ME, headers=_bearer(signed_in, install_id, "admin_app"))
        assert waiting.status_code == 403
        assert waiting.json()["error_code"] == "DEVICE_PENDING"

    async def test_going_back_to_off_lets_everyone_in_again_at_once(
        self, client: AsyncClient, admin_engine: AsyncEngine, hasher: Argon2PasswordHasher
    ) -> None:
        _agency, driver, admin = await self._enforcing(client, admin_engine, hasher)
        install_id = _new_install_id()
        signed_in = await _sign_in(client, driver, install_id)
        mine = _bearer(signed_in, install_id)
        assert (await client.get(_ME, headers=mine)).status_code == 403

        await _set_mode(client, admin, "off")

        assert (await client.get(_ME, headers=mine)).status_code == 200


class TestSettingAndAlerts:
    async def test_an_invalid_mode_is_rejected_and_changes_nothing(
        self, client: AsyncClient, admin_engine: AsyncEngine, hasher: Argon2PasswordHasher
    ) -> None:
        agency = await seed_agency(admin_engine, hasher)
        admin = await login_headers(client, agency.admin_email)

        response = await client.post(
            "/api/v1/admin/tenant-configuration",
            headers=admin,
            json={"config_key": "device_control", "config_value": "lockdown"},
        )

        assert response.status_code == 422, response.text

    async def test_a_new_waiting_phone_alerts_the_agency_admin_but_not_a_manager(
        self, client: AsyncClient, admin_engine: AsyncEngine, hasher: Argon2PasswordHasher
    ) -> None:
        agency = await seed_agency(admin_engine, hasher)
        driver = await _seed_driver(admin_engine, hasher, agency)
        admin = await login_headers(client, agency.admin_email)
        manager = await login_headers(client, agency.manager_email)
        await _set_mode(client, admin, "enforce")

        await _sign_in(client, driver, _new_install_id())

        async def alerts(headers: dict[str, str]) -> list[dict[str, Any]]:
            response = await client.get("/api/v1/notifications", headers=headers)
            assert response.status_code == 200, response.text
            body = response.json()
            items = body["items"] if isinstance(body, dict) else body
            return [n for n in items if n["notification_type"] == "device_pending_staff"]

        [alert] = await alerts(admin)
        assert "waiting" in alert["body"]
        assert await alerts(manager) == []


class TestTenantIsolation:
    async def test_one_agency_enforcing_does_not_touch_another(
        self, client: AsyncClient, admin_engine: AsyncEngine, hasher: Argon2PasswordHasher
    ) -> None:
        strict = await seed_agency(admin_engine, hasher)
        relaxed = await seed_agency(admin_engine, hasher)
        strict_driver = await _seed_driver(admin_engine, hasher, strict)
        relaxed_driver = await _seed_driver(admin_engine, hasher, relaxed)
        await _set_mode(client, await login_headers(client, strict.admin_email), "enforce")
        install_id = _new_install_id()

        refused = await _sign_in(client, strict_driver, None)
        fine = await _sign_in(client, relaxed_driver, None)

        assert refused.status_code == 401
        assert fine.status_code == 200
        assert (await client.get(_ME, headers=_bearer(fine, install_id))).status_code == 200

    async def test_the_same_phone_in_two_agencies_is_two_separate_records(
        self, client: AsyncClient, admin_engine: AsyncEngine, hasher: Argon2PasswordHasher
    ) -> None:
        one = await seed_agency(admin_engine, hasher)
        two = await seed_agency(admin_engine, hasher)
        driver_one = await _seed_driver(admin_engine, hasher, one)
        driver_two = await _seed_driver(admin_engine, hasher, two)
        admin_one = await login_headers(client, one.admin_email)
        admin_two = await login_headers(client, two.admin_email)
        await _set_mode(client, admin_one, "enforce")
        await _set_mode(client, admin_two, "enforce")
        shared_phone = _new_install_id()

        await _sign_in(client, driver_one, shared_phone)
        await _sign_in(client, driver_two, shared_phone)
        [device_one] = await _devices(client, admin_one)
        [device_two] = await _devices(client, admin_two)
        await client.post(f"{_DEVICES}/{device_one['id']}/approve", headers=admin_one)

        assert device_one["id"] != device_two["id"]
        assert [d["status"] for d in await _devices(client, admin_two)] == ["pending"]

    async def test_one_agencys_token_cannot_borrow_anothers_device(
        self,
        client: AsyncClient,
        admin_engine: AsyncEngine,
        hasher: Argon2PasswordHasher,
        database: Database,
    ) -> None:
        # Raw SQL as the application role: agency B's session cannot even see
        # agency A's device row, so a forged `did` can never resolve to it.
        one = await seed_agency(admin_engine, hasher)
        two = await seed_agency(admin_engine, hasher)
        driver = await _seed_driver(admin_engine, hasher, one)
        admin = await login_headers(client, one.admin_email)
        await _set_mode(client, admin, "observe")
        await _sign_in(client, driver, _new_install_id())
        [device] = await _devices(client, admin)

        async for session in database.open_session(tenant_id=two.tenant_id):
            seen = await session.execute(
                text("SELECT count(*) FROM platform.linked_device WHERE id = :i"),
                {"i": device["id"]},
            )
            assert seen.scalar_one() == 0
            tokens = await session.execute(text("SELECT count(*) FROM identity.refresh_token"))
            assert tokens.scalar_one() == 0
