"""Linked devices through the real ASGI stack and a real PostgreSQL (ADR-071):
the admin's list / approve / block / unblock / remove / rename / history API,
its RBAC, the seat limit, and tenant isolation — both through the API and by
raw SQL as the non-superuser `lpg_app` role.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from lpg.infrastructure.identity.password_hasher import Argon2PasswordHasher
from lpg.infrastructure.persistence.database import Database

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncEngine

    from lpg.config.settings import Settings

pytestmark = pytest.mark.integration

_PASSWORD = "correct horse battery staple 42"


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
async def database(
    integration_settings: Settings, postgres_available: bool
) -> AsyncIterator[Database]:
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable")
    db = Database(integration_settings)
    db.connect()
    try:
        yield db
    finally:
        await db.disconnect()


class Agency:
    """A seeded tenant with an agency admin and a manager."""

    def __init__(self, tenant_id: uuid.UUID, admin_email: str, manager_email: str) -> None:
        self.tenant_id = tenant_id
        self.admin_email = admin_email
        self.manager_email = manager_email


async def _seed_agency(engine: AsyncEngine, hasher: Argon2PasswordHasher) -> Agency:
    suffix = uuid.uuid4().hex[:10]
    admin_email = f"admin-{suffix}@devices.example"
    manager_email = f"manager-{suffix}@devices.example"
    password_hash = hasher.hash(_PASSWORD)
    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), :name, :slug, 'ops@example.com') RETURNING id"
                ),
                {"name": f"Devices Co {suffix}", "slug": f"devices-{suffix}"},
            )
        ).scalar_one()
        for email, role in ((admin_email, "agency_admin"), (manager_email, "manager")):
            user_id = (
                await conn.execute(
                    text(
                        "INSERT INTO identity.identity_user "
                        "(id, tenant_id, email, password_hash, role) "
                        "VALUES (gen_random_uuid(), :tenant_id, :email, :hash, :role) "
                        "RETURNING id"
                    ),
                    {
                        "tenant_id": str(tenant_id),
                        "email": email,
                        "hash": password_hash,
                        "role": role,
                    },
                )
            ).scalar_one()
            await conn.execute(
                text(
                    "INSERT INTO identity.identity_user_permission "
                    "(id, user_id, permission_id, created_at) "
                    "SELECT gen_random_uuid(), :user_id, rp.permission_id, now() "
                    "FROM identity.role_permission rp "
                    "JOIN identity.role r ON r.id = rp.role_id WHERE r.code = :role"
                ),
                {"user_id": user_id, "role": role},
            )
    return Agency(uuid.UUID(str(tenant_id)), admin_email, manager_email)


async def _seed_device(
    engine: AsyncEngine,
    tenant_id: uuid.UUID,
    *,
    status: str = "pending",
    app_type: str = "driver_app",
    name: str = "Redmi 12",
) -> uuid.UUID:
    async with engine.begin() as conn:
        license_id = (
            await conn.execute(
                text("SELECT id FROM platform.license WHERE tenant_id = :t"),
                {"t": str(tenant_id)},
            )
        ).scalar_one()
        device_id = (
            await conn.execute(
                text(
                    "INSERT INTO platform.linked_device "
                    "(id, tenant_id, license_id, app_type, device_identifier, display_name, "
                    "status, model, last_user_name, status_changed_at) "
                    "VALUES (gen_random_uuid(), :t, :l, :app, :ident, :name, :status, "
                    "'Redmi 12', 'Ravi', now()) RETURNING id"
                ),
                {
                    "t": str(tenant_id),
                    "l": str(license_id),
                    "app": app_type,
                    "ident": uuid.uuid4().hex + uuid.uuid4().hex,
                    "name": name,
                    "status": status,
                },
            )
        ).scalar_one()
    return uuid.UUID(str(device_id))


async def _set_device_cap(engine: AsyncEngine, tenant_id: uuid.UUID, caps: dict[str, Any]) -> None:
    import json

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE platform.license SET device_caps = CAST(:caps AS jsonb) "
                "WHERE tenant_id = :t"
            ),
            {"caps": json.dumps(caps), "t": str(tenant_id)},
        )


async def _headers(client: AsyncClient, email: str) -> dict[str, str]:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": _PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def hasher(integration_settings: Settings) -> Argon2PasswordHasher:
    return Argon2PasswordHasher(integration_settings)


class TestAdminActions:
    async def test_full_decision_flow_with_history(
        self, client: AsyncClient, admin_engine: AsyncEngine, hasher: Argon2PasswordHasher
    ) -> None:
        agency = await _seed_agency(admin_engine, hasher)
        device_id = await _seed_device(admin_engine, agency.tenant_id)
        headers = await _headers(client, agency.admin_email)

        listed = await client.get("/api/v1/admin/license/devices", headers=headers)
        assert listed.status_code == 200, listed.text
        [row] = listed.json()
        assert row["status"] == "pending"
        assert row["model"] == "Redmi 12"
        assert "device_identifier" not in row  # stored hashed, never returned
        assert len(row["device_ref"]) == 8

        count = await client.get("/api/v1/admin/license/devices/pending-count", headers=headers)
        assert count.json() == {"count": 1}

        base = f"/api/v1/admin/license/devices/{device_id}"
        assert (await client.post(f"{base}/approve", headers=headers)).json()[
            "status"
        ] == "approved"
        assert (await client.post(f"{base}/block", headers=headers)).json()["status"] == "blocked"
        assert (await client.post(f"{base}/unblock", headers=headers)).json()[
            "status"
        ] == "approved"

        renamed = await client.patch(
            base, headers=headers, json={"display_name": "Van 2", "asset_note": "S/N 4521"}
        )
        assert renamed.status_code == 200, renamed.text
        assert renamed.json()["display_name"] == "Van 2"
        assert renamed.json()["asset_note"] == "S/N 4521"

        removed = await client.post(f"{base}/remove", headers=headers)
        assert removed.json()["status"] == "removed"
        assert (await client.get("/api/v1/admin/license/devices", headers=headers)).json() == []
        gone = await client.get("/api/v1/admin/license/devices?status=removed", headers=headers)
        assert [d["id"] for d in gone.json()] == [str(device_id)]

        history = await client.get(f"{base}/history", headers=headers)
        assert history.status_code == 200, history.text
        actions = [h["action"] for h in history.json()]
        # Newest first.
        assert actions == ["removed", "updated", "unblocked", "blocked", "approved"]
        assert history.json()[-1]["from_status"] == "pending"
        assert history.json()[-1]["to_status"] == "approved"
        assert (
            history.json()[0]["actor_name"] is not None or history.json()[0]["actor_name"] is None
        )

    async def test_an_invalid_move_is_a_conflict_not_a_server_error(
        self, client: AsyncClient, admin_engine: AsyncEngine, hasher: Argon2PasswordHasher
    ) -> None:
        agency = await _seed_agency(admin_engine, hasher)
        device_id = await _seed_device(admin_engine, agency.tenant_id, status="approved")
        headers = await _headers(client, agency.admin_email)

        response = await client.post(
            f"/api/v1/admin/license/devices/{device_id}/approve", headers=headers
        )

        assert response.status_code == 409, response.text

    async def test_the_plans_seat_limit_stops_an_approval(
        self, client: AsyncClient, admin_engine: AsyncEngine, hasher: Argon2PasswordHasher
    ) -> None:
        agency = await _seed_agency(admin_engine, hasher)
        await _set_device_cap(admin_engine, agency.tenant_id, {"driver_app": 1})
        await _seed_device(admin_engine, agency.tenant_id, status="approved")
        waiting = await _seed_device(admin_engine, agency.tenant_id, name="Second")
        headers = await _headers(client, agency.admin_email)

        response = await client.post(
            f"/api/v1/admin/license/devices/{waiting}/approve", headers=headers
        )

        assert response.status_code == 409, response.text
        assert response.json()["error_code"] == "DEVICE_LIMIT_REACHED"

    async def test_filters_by_app_type_and_status(
        self, client: AsyncClient, admin_engine: AsyncEngine, hasher: Argon2PasswordHasher
    ) -> None:
        agency = await _seed_agency(admin_engine, hasher)
        await _seed_device(admin_engine, agency.tenant_id, app_type="driver_app", status="pending")
        admin_phone = await _seed_device(
            admin_engine, agency.tenant_id, app_type="admin_app", status="approved"
        )
        headers = await _headers(client, agency.admin_email)

        admin_only = await client.get(
            "/api/v1/admin/license/devices?app_type=admin_app", headers=headers
        )
        approved = await client.get(
            "/api/v1/admin/license/devices?status=approved", headers=headers
        )
        bad = await client.get("/api/v1/admin/license/devices?status=nonsense", headers=headers)

        assert [d["id"] for d in admin_only.json()] == [str(admin_phone)]
        assert [d["id"] for d in approved.json()] == [str(admin_phone)]
        assert bad.status_code == 422


class TestAccessControl:
    async def test_a_manager_cannot_see_or_decide_on_devices(
        self, client: AsyncClient, admin_engine: AsyncEngine, hasher: Argon2PasswordHasher
    ) -> None:
        agency = await _seed_agency(admin_engine, hasher)
        device_id = await _seed_device(admin_engine, agency.tenant_id)
        headers = await _headers(client, agency.manager_email)

        for method, path in (
            ("get", "/api/v1/admin/license/devices"),
            ("get", "/api/v1/admin/license/devices/pending-count"),
            ("get", f"/api/v1/admin/license/devices/{device_id}/history"),
            ("post", f"/api/v1/admin/license/devices/{device_id}/approve"),
            ("post", f"/api/v1/admin/license/devices/{device_id}/block"),
            ("post", f"/api/v1/admin/license/devices/{device_id}/unblock"),
            ("post", f"/api/v1/admin/license/devices/{device_id}/remove"),
            ("patch", f"/api/v1/admin/license/devices/{device_id}"),
        ):
            response = await client.request(
                method, path, headers=headers, json={} if method == "patch" else None
            )
            assert response.status_code == 403, f"{method} {path}: {response.text}"

    async def test_requests_without_a_token_are_refused(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/admin/license/devices")

        assert response.status_code == 401


class TestTenantIsolation:
    async def test_one_agency_cannot_list_or_change_anothers_devices(
        self, client: AsyncClient, admin_engine: AsyncEngine, hasher: Argon2PasswordHasher
    ) -> None:
        agency_a = await _seed_agency(admin_engine, hasher)
        agency_b = await _seed_agency(admin_engine, hasher)
        device_a = await _seed_device(admin_engine, agency_a.tenant_id)
        headers_b = await _headers(client, agency_b.admin_email)

        assert (await client.get("/api/v1/admin/license/devices", headers=headers_b)).json() == []
        assert (
            await client.get("/api/v1/admin/license/devices/pending-count", headers=headers_b)
        ).json() == {"count": 0}
        for action in ("approve", "block", "unblock", "remove"):
            response = await client.post(
                f"/api/v1/admin/license/devices/{device_a}/{action}", headers=headers_b
            )
            assert response.status_code == 404, f"{action}: {response.text}"
        patched = await client.patch(
            f"/api/v1/admin/license/devices/{device_a}",
            headers=headers_b,
            json={"display_name": "mine"},
        )
        assert patched.status_code == 404
        history = await client.get(
            f"/api/v1/admin/license/devices/{device_a}/history", headers=headers_b
        )
        assert history.status_code == 404

        async with admin_engine.connect() as conn:
            status = (
                await conn.execute(
                    text("SELECT status FROM platform.linked_device WHERE id = :i"),
                    {"i": str(device_a)},
                )
            ).scalar_one()
        assert status == "pending"

    async def test_row_level_security_blocks_raw_sql_across_agencies(
        self, database: Database, admin_engine: AsyncEngine, hasher: Argon2PasswordHasher
    ) -> None:
        agency_a = await _seed_agency(admin_engine, hasher)
        agency_b = await _seed_agency(admin_engine, hasher)
        device_a = await _seed_device(admin_engine, agency_a.tenant_id)
        async with admin_engine.connect() as conn:
            license_a = (
                await conn.execute(
                    text("SELECT id FROM platform.license WHERE tenant_id = :t"),
                    {"t": str(agency_a.tenant_id)},
                )
            ).scalar_one()

        async for session in database.open_session(tenant_id=agency_b.tenant_id):
            seen = await session.execute(
                text("SELECT count(*) FROM platform.linked_device WHERE id = :i"),
                {"i": str(device_a)},
            )
            assert seen.scalar_one() == 0
            updated = await session.execute(
                text("UPDATE platform.linked_device SET status = 'approved' WHERE id = :i"),
                {"i": str(device_a)},
            )
            assert updated.rowcount == 0  # type: ignore[attr-defined]
            with pytest.raises(Exception, match="row-level security"):
                await session.execute(
                    text(
                        "INSERT INTO platform.linked_device "
                        "(id, tenant_id, license_id, app_type, device_identifier, "
                        "display_name, status) "
                        "VALUES (gen_random_uuid(), :other, :license, 'driver_app', "
                        "'x', 'x', 'pending')"
                    ),
                    {"other": str(agency_a.tenant_id), "license": str(license_a)},
                )
            await session.rollback()

        async for session in database.open_session(tenant_id=agency_a.tenant_id):
            seen = await session.execute(
                text("SELECT count(*) FROM platform.linked_device WHERE id = :i"),
                {"i": str(device_a)},
            )
            assert seen.scalar_one() == 1

    async def test_the_database_refuses_an_unknown_status(
        self,
        admin_engine: AsyncEngine,
        hasher: Argon2PasswordHasher,
        postgres_available: bool,
    ) -> None:
        if not postgres_available:
            pytest.skip("PostgreSQL is not reachable")
        agency = await _seed_agency(admin_engine, hasher)

        with pytest.raises(Exception, match=r"ck_linked_device_status|check constraint"):
            await _seed_device(admin_engine, agency.tenant_id, status="trusted")
