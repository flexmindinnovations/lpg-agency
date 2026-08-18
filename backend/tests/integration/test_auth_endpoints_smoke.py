"""End-to-end smoke test: real HTTP request → router → use case →
repository → `SECURITY DEFINER` function → real PostgreSQL/Redis.

Every other Phase 6 test exercises one layer in isolation (domain, use
case, repository, infra adapter). This is the one test proving the whole
stack is actually wired together correctly through `create_app()` — the
application lifespan actually runs, so this is as close to "start the
server and curl it" as a test gets.

Builds its own `app`/client fixtures rather than using `conftest.py`'s
generic `app`/`client`/`lifespan_client` — those default to `Settings`'
class-default password (`dev_only_not_a_real_secret`), a placeholder that
has never matched the real local docker compose password (`dev123`,
`.env.dev.example`). This suite needs a connection that actually works, so
it uses `integration_settings`'s already-correct connection details
instead.
"""

from __future__ import annotations

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
    """`lpg.api.app.lifespan` calls `get_settings()` itself rather than
    using whatever `Settings` `create_app(settings)` was given — a
    pre-existing quirk unrelated to Phase 6 (the `settings` parameter only
    configures the app/middleware, not the lifespan's own resource
    connections). Setting the matching env vars, rather than passing
    `integration_settings` directly, is what actually makes `get_settings()`
    agree with it.
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
    """Seeds into `lpg_test` — `integration_settings.database_url`'s target
    (`tests/conftest.py::_database_url`), matching whichever database
    `real_lifespan_client`'s app actually reads from.
    """
    if not postgres_available:
        pytest.skip("PostgreSQL is not reachable — start it with ./scripts/dev-up.sh")
    engine = create_async_engine(
        "postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:55432/lpg_test"
    )
    try:
        yield engine
    finally:
        await engine.dispose()


async def _seed_tenant_and_user(
    engine: AsyncEngine, *, email: str, password_hash: str
) -> tuple[uuid.UUID, uuid.UUID]:
    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug) "
                    "VALUES (gen_random_uuid(), 'Smoke Test Tenant', :slug) RETURNING id"
                ),
                {"slug": f"smoke-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
        user_id = (
            await conn.execute(
                text(
                    "INSERT INTO identity.identity_user "
                    "(id, tenant_id, email, password_hash, role) "
                    "VALUES (gen_random_uuid(), :tenant_id, :email, :password_hash, 'manager') "
                    "RETURNING id"
                ),
                {"tenant_id": str(tenant_id), "email": email, "password_hash": password_hash},
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
            {"user_id": user_id, "role": "manager"},
        )
    return uuid.UUID(str(tenant_id)), uuid.UUID(str(user_id))


class TestLoginEndToEnd:
    async def test_login_then_me_round_trips_through_the_real_stack(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        email = f"{uuid.uuid4().hex}@smoke.example"
        password = "correct horse battery staple 42"
        hasher = Argon2PasswordHasher(integration_settings)
        tenant_id, _user_id = await _seed_tenant_and_user(
            admin_engine_lpg_test, email=email, password_hash=hasher.hash(password)
        )

        login_response = await real_lifespan_client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        assert login_response.status_code == 200, login_response.text
        body = login_response.json()
        assert body["access_token"]
        assert body["refresh_token"]
        assert "lpg_refresh_token" in login_response.cookies

        me_response = await real_lifespan_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {body['access_token']}"},
        )
        assert me_response.status_code == 200, me_response.text
        principal = me_response.json()
        assert principal["tenant_id"] == str(tenant_id)
        assert principal["role"] == "manager"
        assert principal["email"] == email

    async def test_wrong_password_returns_401_with_stable_error_code(
        self,
        real_lifespan_client: AsyncClient,
        admin_engine_lpg_test: AsyncEngine,
        integration_settings: Settings,
    ) -> None:
        email = f"{uuid.uuid4().hex}@smoke.example"
        hasher = Argon2PasswordHasher(integration_settings)
        await _seed_tenant_and_user(
            admin_engine_lpg_test, email=email, password_hash=hasher.hash("the-real-password")
        )

        response = await real_lifespan_client.post(
            "/api/v1/auth/login", json={"email": email, "password": "wrong-password"}
        )

        assert response.status_code == 401
        assert response.json()["error_code"] == "INVALID_CREDENTIALS"

    async def test_me_without_a_token_returns_401(self, real_lifespan_client: AsyncClient) -> None:
        response = await real_lifespan_client.get("/api/v1/auth/me")

        assert response.status_code == 401
