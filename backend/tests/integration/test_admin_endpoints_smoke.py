"""End-to-end smoke test for `api/v1/routers/admin.py`: real HTTP request ->
router -> use case -> repository -> real PostgreSQL/Redis.

`test_auth_endpoints_smoke.py`'s module docstring explains why this class of
test exists: `from __future__ import annotations` + a `TYPE_CHECKING`-only
import anywhere in a `Depends()`-facing function's signature breaks FastAPI's
dependency resolution for the *whole* function, silently — found once
already (ADR-035), and admin.py wires 26 endpoints through ~10 dependency
functions, the largest surface this risk has applied to yet. This test
exercises a representative slice through the real stack, not every endpoint.
"""

from __future__ import annotations

import re
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


@pytest.fixture
async def real_lifespan_client(
    integration_settings: Settings,
    postgres_available: bool,
    redis_available: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[AsyncClient]:
    """Same shape as `test_auth_endpoints_smoke.py`'s fixture of the same
    name — see that file's module docstring for why `get_settings()` needs
    matching env vars rather than `integration_settings` passed directly.
    """
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable — start it with ./scripts/dev-up.sh")
    if not redis_available:
        pytest.skip("Redis is not reachable — start it with ./scripts/dev-up.sh")

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
async def admin_engine_lpg_test(postgres_available: bool) -> AsyncIterator[AsyncEngine]:
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable — start it with ./scripts/dev-up.sh")
    engine = create_async_engine(
        "postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:5433/lpg_test"
    )
    try:
        yield engine
    finally:
        await engine.dispose()


async def _seed_staff_user(
    engine: AsyncEngine, *, email: str, password_hash: str, role: str
) -> tuple[uuid.UUID, uuid.UUID]:
    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), 'Admin Smoke Tenant', :slug, 'ops@example.com') "
                    "RETURNING id"
                ),
                {"slug": f"admin-smoke-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
        user_id = (
            await conn.execute(
                text(
                    "INSERT INTO identity.identity_user "
                    "(id, tenant_id, email, password_hash, role) "
                    "VALUES (gen_random_uuid(), :tenant_id, :email, :password_hash, :role) "
                    "RETURNING id"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "email": email,
                    "password_hash": password_hash,
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
                "JOIN identity.role r ON r.id = rp.role_id "
                "WHERE r.code = :role"
            ),
            {"user_id": user_id, "role": role},
        )
    return uuid.UUID(str(tenant_id)), uuid.UUID(str(user_id))


async def _login(client: AsyncClient, *, email: str, password: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    access_token: str = response.json()["access_token"]
    return access_token


class TestAdminEndpointsThroughTheRealStack:
    async def test_agency_admin_can_view_tenant_and_manage_branches(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        email = f"{uuid.uuid4().hex}@admin-smoke.example"
        password = "correct horse battery staple 42"
        hasher = Argon2PasswordHasher(integration_settings)
        tenant_id, _user_id = await _seed_staff_user(
            admin_engine_lpg_test,
            email=email,
            password_hash=hasher.hash(password),
            role="agency_admin",
        )
        token = await _login(real_lifespan_client, email=email, password=password)
        headers = {"Authorization": f"Bearer {token}"}

        tenant_response = await real_lifespan_client.get("/api/v1/admin/tenant", headers=headers)
        assert tenant_response.status_code == 200, tenant_response.text
        assert tenant_response.json()["id"] == str(tenant_id)

        create_response = await real_lifespan_client.post(
            "/api/v1/admin/branches", json={"name": "Nashik West"}, headers=headers
        )
        assert create_response.status_code == 201, create_response.text
        branch_id = create_response.json()["id"]

        list_response = await real_lifespan_client.get("/api/v1/admin/branches", headers=headers)
        assert list_response.status_code == 200, list_response.text
        assert any(b["id"] == branch_id for b in list_response.json())

        audit_response = await real_lifespan_client.get("/api/v1/admin/audit-log", headers=headers)
        assert audit_response.status_code == 200, audit_response.text
        assert any(
            item["entity_name"] == "branch" and item["entity_id"] == branch_id
            for item in audit_response.json()["items"]
        )

    async def test_a_driver_is_denied_admin_access(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        email = f"{uuid.uuid4().hex}@admin-smoke.example"
        password = "correct horse battery staple 42"
        hasher = Argon2PasswordHasher(integration_settings)
        await _seed_staff_user(
            admin_engine_lpg_test, email=email, password_hash=hasher.hash(password), role="driver"
        )
        token = await _login(real_lifespan_client, email=email, password=password)

        response = await real_lifespan_client.get(
            "/api/v1/admin/tenant", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403

    async def test_an_agency_admin_cannot_manage_platform_feature_flags(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        """Platform feature-flag management lives at `/platform/feature-
        flags` (Platform Console plan), not `/admin/feature-flags` — an
        `agency_admin`'s tenant-scoped JWT (a real `tenant_id` claim) is
        rejected by `JwtPlatformPrincipalResolver` itself (`role !=
        'super_admin'`), before any permission code is even considered.
        """
        email = f"{uuid.uuid4().hex}@admin-smoke.example"
        password = "correct horse battery staple 42"
        hasher = Argon2PasswordHasher(integration_settings)
        await _seed_staff_user(
            admin_engine_lpg_test,
            email=email,
            password_hash=hasher.hash(password),
            role="agency_admin",
        )
        token = await _login(real_lifespan_client, email=email, password=password)

        response = await real_lifespan_client.post(
            "/api/v1/platform/feature-flags",
            json={"key": f"flag-{uuid.uuid4().hex[:8]}", "description": "Test"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403


class TestQaFixesThroughTheRealStack:
    """QA fixes DA-01, DA-19, DA-30, DA-32 wired end to end."""

    async def _admin(
        self, client: AsyncClient, engine: AsyncEngine, settings: Settings
    ) -> tuple[uuid.UUID, uuid.UUID, dict[str, str]]:
        email = f"{uuid.uuid4().hex}@admin-smoke.example"
        password = "correct horse battery staple 42"
        tenant_id, user_id = await _seed_staff_user(
            engine,
            email=email,
            password_hash=Argon2PasswordHasher(settings).hash(password),
            role="agency_admin",
        )
        token = await _login(client, email=email, password=password)
        return tenant_id, user_id, {"Authorization": f"Bearer {token}"}

    async def test_setup_progress_and_branch_name_rules(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        _tenant, _me, headers = await self._admin(
            real_lifespan_client, admin_engine_lpg_test, integration_settings
        )
        progress = await real_lifespan_client.get("/api/v1/admin/setup-progress", headers=headers)
        assert progress.status_code == 200, progress.text
        assert progress.json()["steps"]["branch"] is False
        assert progress.json()["complete"] is False

        created = await real_lifespan_client.post(
            "/api/v1/admin/branches", json={"name": "  Kukatpally  "}, headers=headers
        )
        assert created.status_code == 201, created.text
        assert created.json()["name"] == "Kukatpally"
        duplicate = await real_lifespan_client.post(
            "/api/v1/admin/branches", json={"name": "kukatpally"}, headers=headers
        )
        assert duplicate.status_code == 409, duplicate.text
        blank = await real_lifespan_client.post(
            "/api/v1/admin/branches", json={"name": "   "}, headers=headers
        )
        assert blank.status_code == 422, blank.text
        too_long = await real_lifespan_client.post(
            "/api/v1/admin/branches", json={"name": "x" * 300}, headers=headers
        )
        assert too_long.status_code == 422, too_long.text

        progress = await real_lifespan_client.get("/api/v1/admin/setup-progress", headers=headers)
        assert progress.json()["steps"]["branch"] is True

    async def test_self_deactivation_is_refused_and_a_user_can_be_reactivated(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        _tenant, me, headers = await self._admin(
            real_lifespan_client, admin_engine_lpg_test, integration_settings
        )
        own = await real_lifespan_client.patch(
            f"/api/v1/admin/users/{me}/deactivate", headers=headers
        )
        assert own.status_code == 409, own.text

        invited = await real_lifespan_client.post(
            "/api/v1/admin/users",
            json={"email": f"{uuid.uuid4().hex}@staff.example", "role": "dispatcher"},
            headers=headers,
        )
        assert invited.status_code == 201, invited.text
        user_id = invited.json()["id"]
        for action, active in (("deactivate", False), ("reactivate", True)):
            response = await real_lifespan_client.patch(
                f"/api/v1/admin/users/{user_id}/{action}", headers=headers
            )
            assert response.status_code == 204, response.text
            users = (await real_lifespan_client.get("/api/v1/admin/users", headers=headers)).json()
            assert next(u for u in users if u["id"] == user_id)["is_active"] is active

        audit = (await real_lifespan_client.get("/api/v1/admin/audit-log", headers=headers)).json()
        actions = {item["action"] for item in audit["items"] if item["entity_id"] == str(user_id)}
        assert {"deactivate", "reactivate"} <= actions

    async def test_my_profile_round_trip(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        _tenant, _me, headers = await self._admin(
            real_lifespan_client, admin_engine_lpg_test, integration_settings
        )
        updated = await real_lifespan_client.patch(
            "/api/v1/auth/me/profile",
            json={"display_name": "Ravi Kumar", "contact_phone": "+91 98490 12345"},
            headers=headers,
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["display_name"] == "Ravi Kumar"

        wrong = await real_lifespan_client.post(
            "/api/v1/auth/me/password",
            json={"current_password": "not it", "new_password": "a brand new passphrase"},
            headers=headers,
        )
        assert wrong.status_code == 422, wrong.text
        assert "current_password" in wrong.json()["errors"]
        changed = await real_lifespan_client.post(
            "/api/v1/auth/me/password",
            json={
                "current_password": "correct horse battery staple 42",
                "new_password": "a brand new passphrase",
            },
            headers=headers,
        )
        assert changed.status_code == 204, changed.text

    async def test_an_invited_user_sets_a_password_from_the_link_and_signs_in(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        """DA-08: invite -> `/set-password?token=...` -> set password -> login."""
        from lpg.api.v1.dependencies.identity import get_email_sender

        sent: list[str] = []

        class _CapturingEmailSender:
            async def send(self, to: str, subject: str, body: str) -> None:
                sent.append(f"{to}|{subject}|{body}")

        transport = real_lifespan_client._transport
        assert isinstance(transport, ASGITransport)
        app: FastAPI = transport.app  # type: ignore[assignment]
        app.dependency_overrides[get_email_sender] = _CapturingEmailSender
        try:
            _tenant, _me, headers = await self._admin(
                real_lifespan_client, admin_engine_lpg_test, integration_settings
            )
            email = f"{uuid.uuid4().hex}@staff.example"
            invited = await real_lifespan_client.post(
                "/api/v1/admin/users",
                json={"email": email, "role": "dispatcher"},
                headers=headers,
            )
            assert invited.status_code == 201, invited.text
        finally:
            app.dependency_overrides.pop(get_email_sender, None)

        (body,) = sent
        match = re.search(r"/set-password\?token=([A-Za-z0-9_\-]+)", body)
        assert match is not None, body
        assert f"{integration_settings.dashboard_url}/set-password?token=" in body

        new_password = "my own first passphrase 7"
        confirmed = await real_lifespan_client.post(
            "/api/v1/auth/password/reset",
            json={"reset_token": match.group(1), "new_password": new_password},
        )
        assert confirmed.status_code == 204, confirmed.text

        await _login(real_lifespan_client, email=email, password=new_password)
        reused = await real_lifespan_client.post(
            "/api/v1/auth/password/reset",
            json={"reset_token": match.group(1), "new_password": "another passphrase 99"},
        )
        assert reused.status_code >= 400
