"""Device control, the whole matrix (ADR-071, story 11.10): every state a phone
can be in, against every way into the system — password sign-in, OTP sign-in,
refresh, an ordinary request, `GET /devices/me` and the realtime connection —
plus the cases a security review asked for: two sign-ins racing to register
the same phone, one login flooding the approval queue, a block that must not
touch the user's other phones, and a chatty realtime client that must not
outlive a block.

Real ASGI stack, real PostgreSQL (as the non-superuser role) and Redis.
"""

from __future__ import annotations

import asyncio
import json
import socket
import uuid
from typing import TYPE_CHECKING, Any, ClassVar

import httpx
import pytest
import websockets
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from tests.integration.device_support import (
    PASSWORD,
    login_headers,
    seed_agency,
    set_device_cap,
)
from tests.integration.test_device_enforcement_api import (
    _DEVICES,
    _ME,
    _bearer,
    _devices,
    _new_install_id,
    _phone,
    _seed_driver,
    _set_mode,
    _sign_in,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

    from lpg.config.settings import Settings
    from lpg.infrastructure.identity.password_hasher import Argon2PasswordHasher

pytestmark = pytest.mark.integration

_STATES = ["unknown", "pending", "approved", "blocked", "removed"]


async def _put_phone_in_state(
    client: AsyncClient, admin: dict[str, str], driver: str, install_id: str, state: str
) -> httpx.Response | None:
    """Sign the driver in on a phone and move it to `state` through the real
    admin API. Returns the sign-in response (None for a phone never seen)."""
    if state == "unknown":
        return None
    first = await _sign_in(client, driver, install_id)
    assert first.status_code == 200, first.text
    [device] = await _devices(client, admin, status="pending")
    base = f"{_DEVICES}/{device['id']}"
    if state == "approved":
        await client.post(f"{base}/approve", headers=admin)
    elif state == "blocked":
        await client.post(f"{base}/block", headers=admin)
    elif state == "removed":
        await client.post(f"{base}/remove", headers=admin)
    return first


class TestEveryStateAgainstEveryPath:
    # (sign in, request with an existing session, refresh, GET /devices/me)
    EXPECTED: ClassVar[dict[str, tuple[int, int | None, int | None, int | None]]] = {
        "unknown": (200, None, None, None),
        "pending": (200, 403, 200, 200),
        "approved": (200, 200, 200, 200),
        "blocked": (403, 403, 401, 200),
        "removed": (200, 403, 401, 200),
    }
    REQUEST_CODE: ClassVar[dict[str, str]] = {
        "pending": "DEVICE_PENDING",
        "blocked": "DEVICE_BLOCKED",
        "removed": "DEVICE_REMOVED",
    }

    @pytest.mark.parametrize("state", _STATES)
    async def test_driver_in_every_state(
        self,
        state: str,
        devices_client: AsyncClient,
        admin_engine: AsyncEngine,
        devices_hasher: Argon2PasswordHasher,
    ) -> None:
        client = devices_client
        agency = await seed_agency(admin_engine, devices_hasher)
        driver = await _seed_driver(admin_engine, devices_hasher, agency)
        admin = await login_headers(client, agency.admin_email)
        await _set_mode(client, admin, "enforce")
        install_id = _new_install_id()
        sign_in, request, refresh, me = self.EXPECTED[state]

        session = await _put_phone_in_state(client, admin, driver, install_id, state)

        if session is not None:
            headers = _bearer(session, install_id)
            response = await client.get(_ME, headers=headers)
            assert response.status_code == (request or 200), f"request as {state}"
            if state in self.REQUEST_CODE:
                assert response.json()["error_code"] == self.REQUEST_CODE[state]
            renewed = await client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": session.json()["refresh_token"]},
                headers=_phone(install_id),
            )
            assert renewed.status_code == refresh, f"refresh as {state}: {renewed.text}"
            state_call = await client.get("/api/v1/devices/me", headers=headers)
            assert state_call.status_code == me, f"/devices/me as {state}"

        again = await _sign_in(client, driver, install_id)
        assert again.status_code == sign_in, f"sign-in as {state}: {again.text}"
        if state == "blocked":
            assert again.json()["error_code"] == "DEVICE_BLOCKED"

    async def test_unknown_phone_signing_in_becomes_pending_then_is_refused(
        self,
        devices_client: AsyncClient,
        admin_engine: AsyncEngine,
        devices_hasher: Argon2PasswordHasher,
    ) -> None:
        client = devices_client
        agency = await seed_agency(admin_engine, devices_hasher)
        driver = await _seed_driver(admin_engine, devices_hasher, agency)
        admin = await login_headers(client, agency.admin_email)
        await _set_mode(client, admin, "enforce")
        install_id = _new_install_id()

        session = await _sign_in(client, driver, install_id)

        assert session.status_code == 200
        [device] = await _devices(client, admin)
        assert device["status"] == "pending"
        refused = await client.get(_ME, headers=_bearer(session, install_id))
        assert refused.json()["error_code"] == "DEVICE_PENDING"

    async def test_over_the_seat_limit_a_phone_cannot_be_approved_but_observe_does_not_block(
        self,
        devices_client: AsyncClient,
        admin_engine: AsyncEngine,
        devices_hasher: Argon2PasswordHasher,
    ) -> None:
        client = devices_client
        agency = await seed_agency(admin_engine, devices_hasher)
        driver = await _seed_driver(admin_engine, devices_hasher, agency)
        admin = await login_headers(client, agency.admin_email)
        await set_device_cap(admin_engine, agency.tenant_id, {"driver_app": 1})
        await _set_mode(client, admin, "enforce")
        first, second = _new_install_id(), _new_install_id()
        await _put_phone_in_state(client, admin, driver, first, "approved")
        late = await _sign_in(client, driver, second)
        [waiting] = await _devices(client, admin, status="pending")

        approve = await client.post(f"{_DEVICES}/{waiting['id']}/approve", headers=admin)

        assert approve.status_code == 409
        assert approve.json()["error_code"] == "DEVICE_LIMIT_REACHED"
        assert (await client.get(_ME, headers=_bearer(late, second))).status_code == 403
        await _set_mode(client, admin, "observe")
        assert (await client.get(_ME, headers=_bearer(late, second))).status_code == 200


class TestOtpSignIn:
    async def test_a_driver_signing_in_with_an_otp_goes_through_the_same_gate(
        self,
        devices_client: AsyncClient,
        admin_engine: AsyncEngine,
        devices_hasher: Argon2PasswordHasher,
    ) -> None:
        client = devices_client
        agency = await seed_agency(admin_engine, devices_hasher)
        email = await _seed_driver(admin_engine, devices_hasher, agency)
        phone = f"+91{uuid.uuid4().int % 10**9:09d}9"[:13]
        async with admin_engine.begin() as conn:
            await conn.execute(
                text("UPDATE identity.identity_user SET phone_number = :p WHERE email = :e"),
                {"p": phone, "e": email},
            )
        admin = await login_headers(client, agency.admin_email)
        await _set_mode(client, admin, "enforce")
        install_id = _new_install_id()
        tenant = str(agency.tenant_id)

        async def otp_sign_in(headers: dict[str, str]) -> httpx.Response:
            sent = await client.post(
                "/api/v1/auth/otp/request", json={"tenant_id": tenant, "phone_number": phone}
            )
            assert sent.status_code == 204, sent.text
            code = (await client.get(f"/api/v1/dev/otp-inbox/{phone}")).json()["code"]
            return await client.post(
                "/api/v1/auth/otp/verify",
                json={
                    "tenant_id": tenant,
                    "phone_number": phone,
                    "code": code,
                    "device": {"name": "Van 3", "model": "Redmi 12"},
                },
                headers=headers,
            )

        no_phone = await otp_sign_in({})
        assert no_phone.status_code == 401
        assert no_phone.json()["error_code"] == "DEVICE_REQUIRED"

        with_phone = await otp_sign_in(_phone(install_id))
        assert with_phone.status_code == 200, with_phone.text
        [device] = await _devices(client, admin)
        assert device["status"] == "pending"
        assert device["display_name"] == "Van 3"
        refused = await client.get(_ME, headers=_bearer(with_phone, install_id))
        assert refused.json()["error_code"] == "DEVICE_PENDING"

        await client.post(f"{_DEVICES}/{device['id']}/block", headers=admin)
        blocked = await otp_sign_in(_phone(install_id))
        assert blocked.status_code == 403
        assert blocked.json()["error_code"] == "DEVICE_BLOCKED"


class TestHardening:
    async def test_two_sign_ins_racing_to_register_one_phone_make_one_record(
        self,
        devices_client: AsyncClient,
        admin_engine: AsyncEngine,
        devices_hasher: Argon2PasswordHasher,
    ) -> None:
        client = devices_client
        agency = await seed_agency(admin_engine, devices_hasher)
        driver = await _seed_driver(admin_engine, devices_hasher, agency)
        admin = await login_headers(client, agency.admin_email)
        await _set_mode(client, admin, "enforce")
        install_id = _new_install_id()

        results = await asyncio.gather(*(_sign_in(client, driver, install_id) for _ in range(4)))

        assert [r.status_code for r in results] == [200] * 4, [r.text for r in results]
        assert len(await _devices(client, admin)) == 1

    async def test_one_login_cannot_flood_the_approval_queue(
        self,
        devices_client: AsyncClient,
        admin_engine: AsyncEngine,
        devices_hasher: Argon2PasswordHasher,
    ) -> None:
        client = devices_client
        agency = await seed_agency(admin_engine, devices_hasher)
        driver = await _seed_driver(admin_engine, devices_hasher, agency)
        admin = await login_headers(client, agency.admin_email)
        await _set_mode(client, admin, "enforce")
        phones = [_new_install_id() for _ in range(6)]

        statuses = [(await _sign_in(client, driver, p)).status_code for p in phones]

        assert statuses == [200] * 5 + [409]
        last = await _sign_in(client, driver, phones[-1])
        assert last.json()["error_code"] == "DEVICE_QUEUE_FULL"
        assert len(await _devices(client, admin)) == 5
        # A phone already waiting can still sign in again.
        assert (await _sign_in(client, driver, phones[0])).status_code == 200

    async def test_blocking_one_phone_leaves_the_same_users_other_phone_working(
        self,
        devices_client: AsyncClient,
        admin_engine: AsyncEngine,
        devices_hasher: Argon2PasswordHasher,
    ) -> None:
        client = devices_client
        agency = await seed_agency(admin_engine, devices_hasher)
        driver = await _seed_driver(admin_engine, devices_hasher, agency)
        admin = await login_headers(client, agency.admin_email)
        await _set_mode(client, admin, "enforce")
        phone_a, phone_b = _new_install_id(), _new_install_id()
        session_a = await _sign_in(client, driver, phone_a)
        session_b = await _sign_in(client, driver, phone_b)
        for device in await _devices(client, admin):
            await client.post(f"{_DEVICES}/{device['id']}/approve", headers=admin)
        blocked = next(d for d in await _devices(client, admin) if d["device_ref"])
        names = {d["id"]: d for d in await _devices(client, admin)}
        # Block whichever device phone A is (the first registered).
        first = sorted(names.values(), key=lambda d: d["registered_at"])[0]
        await client.post(f"{_DEVICES}/{first['id']}/block", headers=admin)
        assert blocked  # (the list was readable)

        a_call = await client.get(_ME, headers=_bearer(session_a, phone_a))
        b_call = await client.get(_ME, headers=_bearer(session_b, phone_b))
        a_refresh = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": session_a.json()["refresh_token"]},
            headers=_phone(phone_a),
        )
        b_refresh = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": session_b.json()["refresh_token"]},
            headers=_phone(phone_b),
        )

        assert a_call.status_code == 403
        assert b_call.status_code == 200
        assert a_refresh.status_code == 401
        assert b_refresh.status_code == 200


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class TestRealtime:
    """The WebSocket, over a real socket (uvicorn in this process)."""

    @pytest.fixture
    async def server(
        self,
        integration_settings: Settings,
        postgres_available: bool,
        redis_available: bool,
        monkeypatch: pytest.MonkeyPatch,
    ) -> Any:
        import uvicorn

        if not (postgres_available and redis_available):
            pytest.skip("PostgreSQL / Redis are not reachable")
        monkeypatch.setenv("LPG_ENVIRONMENT", "local")
        monkeypatch.setenv("LPG_DATABASE_URL", str(integration_settings.database_url))
        monkeypatch.setenv("LPG_REDIS_URL", str(integration_settings.redis_url))
        from lpg.api.app import create_app
        from lpg.config.settings import get_settings

        get_settings.cache_clear()
        app = create_app(integration_settings)
        port = _free_port()
        config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
        srv = uvicorn.Server(config)
        task = asyncio.create_task(srv.serve())
        for _ in range(100):
            if srv.started:
                break
            await asyncio.sleep(0.1)
        assert srv.started, "test server did not start"
        yield port
        srv.should_exit = True
        await task
        get_settings.cache_clear()

    async def _connect(self, port: int, token: str, install_id: str | None) -> Any:
        ws = await websockets.connect(f"ws://127.0.0.1:{port}/api/v1/ws")
        frame: dict[str, Any] = {"type": "auth", "token": token}
        if install_id:
            frame["device_id"] = install_id
        await ws.send(json.dumps(frame))
        return ws

    async def _expect_closed(self, ws: Any, code: str, within: float = 5.0) -> None:
        with pytest.raises(websockets.exceptions.ConnectionClosed) as closed:
            async with asyncio.timeout(within):
                while True:
                    await ws.recv()
        assert closed.value.rcvd is not None
        assert closed.value.rcvd.code == 1008
        assert closed.value.rcvd.reason == code

    async def test_pending_wrong_phone_and_blocked_are_all_refused_with_a_reason(
        self,
        server: int,
        admin_engine: AsyncEngine,
        devices_hasher: Argon2PasswordHasher,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        base = f"http://127.0.0.1:{server}"
        async with AsyncClient(base_url=base) as client:
            agency = await seed_agency(admin_engine, devices_hasher)
            driver = await _seed_driver(admin_engine, devices_hasher, agency)
            admin = await login_headers(client, agency.admin_email)
            await _set_mode(client, admin, "enforce")
            install_id = _new_install_id()
            session = await _sign_in(client, driver, install_id)
            token = session.json()["access_token"]

            # Waiting for approval: no live feed.
            ws = await self._connect(server, token, install_id)
            await self._expect_closed(ws, "DEVICE_PENDING")

            [device] = await _devices(client, admin)
            await client.post(f"{_DEVICES}/{device['id']}/approve", headers=admin)

            # The token on a phone it was not issued to.
            ws = await self._connect(server, token, _new_install_id())
            await self._expect_closed(ws, "DEVICE_REQUIRED")
            ws = await self._connect(server, token, None)
            await self._expect_closed(ws, "DEVICE_REQUIRED")

            # Approved, right phone: connected, and a chatty client is still
            # cut off within the re-check interval after a block.
            import lpg.api.v1.routers.ws as ws_module

            monkeypatch.setattr(ws_module, "_DEVICE_RECHECK_S", 0.5)
            ws = await self._connect(server, token, install_id)
            ready = json.loads(await asyncio.wait_for(ws.recv(), 5))
            assert ready == {"type": "ready"}

            await client.post(f"{_DEVICES}/{device['id']}/block", headers=admin)

            async def chatter() -> None:
                while True:
                    await ws.send(json.dumps({"type": "pong"}))
                    await asyncio.sleep(0.1)

            talker = asyncio.create_task(chatter())
            try:
                await self._expect_closed(ws, "DEVICE_BLOCKED", within=10.0)
            finally:
                talker.cancel()

            # And a fresh connection from the blocked phone is refused at once.
            blocked_token_ws = await self._connect(server, token, install_id)
            await self._expect_closed(blocked_token_ws, "DEVICE_BLOCKED")

    async def test_the_agency_admin_and_customers_connect_without_any_phone(
        self,
        server: int,
        admin_engine: AsyncEngine,
        devices_hasher: Argon2PasswordHasher,
    ) -> None:
        base = f"http://127.0.0.1:{server}"
        async with AsyncClient(base_url=base) as client:
            agency = await seed_agency(admin_engine, devices_hasher)
            admin = await login_headers(client, agency.admin_email)
            await _set_mode(client, admin, "enforce")
            token = admin["Authorization"].removeprefix("Bearer ")

            ws = await self._connect(server, token, None)

            assert json.loads(await asyncio.wait_for(ws.recv(), 5)) == {"type": "ready"}
            await ws.close()


_ = (LifespanManager, ASGITransport, PASSWORD)  # kept for readers of the fixtures
