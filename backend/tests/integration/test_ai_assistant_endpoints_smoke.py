"""Smoke test for `POST /ai/ask` through the real ASGI stack (auth, RBAC,
RLS, DB) — the model gateway is overridden with a fake, so this proves the
kill-switch/budget/permission-filtering/ledger-write path end to end
without a real Gemini call (Stage 4's live-verification does that)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
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


class _FakeModelGateway:
    """Overrides `get_model_gateway` — no real network call, but every
    other layer (kill-switch, budget, per-tool permission filtering, the
    tool_executor closure, the ledger write) runs for real."""

    def __init__(self) -> None:
        self.last_tools: tuple[object, ...] | None = None

    async def run_with_tools(self, *, tools, tool_executor, **_kwargs):
        self.last_tools = tools
        # Actually call the one tool offered, proving the real handler
        # (a real repository query against the real DB) runs end to end.
        tool_results = [await tool_executor(tool.name, {}) for tool in tools]
        from lpg.application.ai.ports import AgentRunResult

        return AgentRunResult(
            final_answer=f"Consulted {len(tools)} tool(s): {tool_results}",
            tools_used=tuple(tool.name for tool in tools),
            prompt_tokens=42,
            completion_tokens=8,
            tool_turns=1 if tools else 0,
            provider="fake",
            model="fake-model",
        )


@dataclass
class _AppAndClient:
    app: FastAPI
    client: AsyncClient
    gateway: _FakeModelGateway


@pytest.fixture
async def stack(
    integration_settings: Settings,
    postgres_available: bool,
    redis_available: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[_AppAndClient]:
    if not postgres_available or not redis_available:
        pytest.skip("infra not reachable")
    monkeypatch.setenv("LPG_ENVIRONMENT", "local")
    monkeypatch.setenv("LPG_DATABASE_URL", str(integration_settings.database_url))
    monkeypatch.setenv("LPG_REDIS_URL", str(integration_settings.redis_url))

    from lpg.api.app import create_app
    from lpg.api.v1.dependencies.ai import get_model_gateway
    from lpg.config.settings import get_settings

    get_settings.cache_clear()
    app: FastAPI = create_app(integration_settings)
    gateway = _FakeModelGateway()
    app.dependency_overrides[get_model_gateway] = lambda: gateway
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as http:
            yield _AppAndClient(app=app, client=http, gateway=gateway)
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


async def _seed_manager(
    engine: AsyncEngine, *, password_hash: str, gateway_enabled: bool
) -> tuple[uuid.UUID, str]:
    email = f"{uuid.uuid4().hex}@ai-smoke.example"
    async with engine.begin() as conn:
        tenant_id = (
            await conn.execute(
                text(
                    "INSERT INTO tenant.tenant (id, name, slug, primary_contact_email) "
                    "VALUES (gen_random_uuid(), 'AI Smoke', :slug, 'ops@example.com') "
                    "RETURNING id"
                ),
                {"slug": f"ai-smoke-{uuid.uuid4().hex[:10]}"},
            )
        ).scalar_one()
        user_id = (
            await conn.execute(
                text(
                    "INSERT INTO identity.identity_user "
                    "(id, tenant_id, email, password_hash, role) "
                    "VALUES (gen_random_uuid(), :tenant_id, :email, :ph, 'manager') RETURNING id"
                ),
                {"tenant_id": str(tenant_id), "email": email, "ph": password_hash},
            )
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO identity.identity_user_permission "
                "(id, user_id, permission_id, created_at) "
                "SELECT gen_random_uuid(), :uid, rp.permission_id, now() "
                "FROM identity.role_permission rp JOIN identity.role r ON r.id = rp.role_id "
                "WHERE r.code = 'manager'"
            ),
            {"uid": str(user_id)},
        )
        await conn.execute(
            text(
                "INSERT INTO tenant.tenant_configuration "
                "(id, tenant_id, config_key, config_value, effective_from) "
                "VALUES (gen_random_uuid(), :tenant_id, 'ai_gateway_enabled', :value, now())"
            ),
            {"tenant_id": str(tenant_id), "value": "true" if gateway_enabled else "false"},
        )
    return uuid.UUID(str(tenant_id)), email


async def _login(client: AsyncClient, *, email: str, password: str) -> str:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    token: str = resp.json()["access_token"]
    return token


async def test_ask_ai_assistant_happy_path_calls_real_tools(
    stack: _AppAndClient,
    admin_engine_lpg_test: AsyncEngine,
    integration_settings: Settings,
) -> None:
    password = "correct horse battery staple 42"
    hasher = Argon2PasswordHasher(integration_settings)
    _tenant_id, email = await _seed_manager(
        admin_engine_lpg_test, password_hash=hasher.hash(password), gateway_enabled=True
    )
    token = await _login(stack.client, email=email, password=password)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await stack.client.post(
        "/api/v1/ai/ask", json={"question": "What's today's inventory?"}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["disabled_reason"] is None
    assert body["answer"] is not None
    # manager holds orders:read, inventory:read, complaints.manage in the
    # dev/test seed matrix -- all three tools should have been offered.
    assert set(body["tools_used"]) == {
        "get_today_delivery_status",
        "get_inventory_overview",
        "get_open_complaints_summary",
    }
    assert stack.gateway.last_tools is not None
    assert len(stack.gateway.last_tools) == 3


async def test_ask_ai_assistant_disabled_for_a_tenant_that_never_opted_in(
    stack: _AppAndClient,
    admin_engine_lpg_test: AsyncEngine,
    integration_settings: Settings,
) -> None:
    password = "correct horse battery staple 42"
    hasher = Argon2PasswordHasher(integration_settings)
    _tenant_id, email = await _seed_manager(
        admin_engine_lpg_test, password_hash=hasher.hash(password), gateway_enabled=False
    )
    token = await _login(stack.client, email=email, password=password)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await stack.client.post(
        "/api/v1/ai/ask", json={"question": "Anything?"}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["disabled_reason"] == "gateway_disabled"
    assert body["answer"] is None
    assert stack.gateway.last_tools is None  # gateway never touched


async def test_ask_ai_assistant_requires_ai_read_permission(
    stack: _AppAndClient,
) -> None:
    resp = await stack.client.post("/api/v1/ai/ask", json={"question": "Anything?"})
    assert resp.status_code == 401, resp.text
