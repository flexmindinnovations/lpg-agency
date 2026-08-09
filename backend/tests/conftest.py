"""Shared pytest fixtures.

Integration tests run against a **real PostgreSQL, Redis, and MinIO** from
docker compose — never SQLite, never a mock. RLS policies and
PostgreSQL-specific types must actually be exercised, and a mock cannot
exercise either (``docs/implementation/testing-strategy.md``).

When those services are unreachable, integration tests **skip with a reason**
rather than fail. A red suite caused by a stopped container trains people to
ignore red suites.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

from lpg.config.settings import Settings, get_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> Iterator[None]:
    """Clear the settings cache around every test.

    ``get_settings`` is LRU-cached for the process lifetime, so without this a
    test that manipulates the environment would leak configuration into every
    subsequent test.
    """
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _no_real_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent a real ``backend/.env`` from leaking into the test suite.

    Normal setup is ``cp .env.dev.example .env`` — every developer following
    the documented workflow ends up with a real, git-ignored ``.env`` on disk.
    ``Settings`` reads that file directly as a config *source*, independent of
    ``os.environ``, so ``monkeypatch.setenv``/``delenv`` alone do not shield a
    test from it: a bare ``Settings()`` call would silently pick up whatever
    environment a developer happens to have configured (production URLs,
    ``LPG_ENVIRONMENT=production`` triggering the non-local guard rails in
    ``model_post_init``, or fields left empty pending real credentials) instead
    of the value a test intends to exercise.

    A test suite whose outcome depends on which environment file happens to
    exist on the machine running it is not hermetic. Disabling dotenv loading
    for the duration of every test closes that gap without touching every call
    site that constructs ``Settings()``.
    """
    monkeypatch.setitem(Settings.model_config, "env_file", None)


@pytest.fixture
def settings() -> Settings:
    return Settings(environment="local", log_json=False, docs_enabled=True)


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    from lpg.api.app import create_app

    return create_app(settings)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """An HTTP client speaking directly to the ASGI app.

    Deliberately does **not** run the lifespan, so unit-level API tests do not
    require PostgreSQL or Redis. Tests that need real dependencies use
    ``lifespan_client`` and are marked ``integration``.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client


@pytest.fixture
async def lifespan_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """An HTTP client with the application lifespan running.

    Opens the database and Redis connection pools, so readiness reports real
    dependency state.
    """
    from asgi_lifespan import LifespanManager  # type: ignore[import-not-found]

    async with LifespanManager(app):  # pragma: no cover - optional dependency
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
            yield http_client


def _database_url() -> str:
    """Connection string for integration tests.

    Defaults to the docker compose test database, connecting as ``lpg_app`` —
    the non-superuser, NOBYPASSRLS role the application uses. Testing as a
    superuser would silently pass tenant-isolation checks that production
    would fail.
    """
    return os.environ.get(
        "LPG_TEST_DATABASE_URL",
        "postgresql+asyncpg://lpg_app:dev123@localhost:55432/lpg_test",
    )


def _redis_url() -> str:
    return os.environ.get("LPG_TEST_REDIS_URL", "redis://localhost:56379/1")


def _storage_endpoint_url() -> str:
    return os.environ.get("LPG_TEST_STORAGE_ENDPOINT_URL", "http://localhost:59000")


def _storage_bucket() -> str:
    # Separate from the dev/uat buckets, mirroring the test database/Redis
    # logical-database separation above.
    return os.environ.get("LPG_TEST_STORAGE_BUCKET", "lpg-test")


def _admin_database_url() -> str:
    """Connection string for **seeding** data that RLS would otherwise block.

    Uses ``lpg_admin`` — the elevated, superuser role migrations run as
    (``06-database-architecture.md`` §2.2) — deliberately, so tests can set up
    fixture rows that the tenant-scoped ``lpg_app`` role could never insert
    itself (e.g. ``tenant.tenant``, whose RLS policy makes self-registration
    impossible by design — see migration ``0242df1a3871``). Never used to
    perform the *action under test*; only to arrange state before it.
    """
    return os.environ.get(
        "LPG_TEST_ADMIN_DATABASE_URL",
        "postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:55432/lpg_test",
    )


@pytest.fixture
async def admin_engine() -> AsyncIterator[AsyncEngine]:
    """An engine connected as the elevated role, for fixture setup only."""
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(_admin_database_url())
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
def integration_settings() -> Settings:
    """Settings pointed at the docker compose services."""
    return Settings(
        environment="local",
        log_json=False,
        database_url=_database_url(),
        redis_url=_redis_url(),
        health_check_timeout_seconds=5.0,
        storage_endpoint_url=_storage_endpoint_url(),
        storage_bucket=_storage_bucket(),
    )


@pytest.fixture
async def postgres_available() -> bool:
    """Whether the docker compose PostgreSQL is reachable."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(_database_url())
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - availability probe
        return False
    else:
        return True
    finally:
        await engine.dispose()


@pytest.fixture
async def redis_available() -> bool:
    """Whether the docker compose Redis is reachable."""
    import redis.asyncio as redis

    # redis-py 5.x's `from_url` loses its type annotation under the <6
    # ceiling `arq` forces (ADR-029) — see the identical note in
    # RedisClient.connect().
    client = redis.from_url(_redis_url(), decode_responses=True)  # type: ignore[no-untyped-call]
    try:
        await client.ping()
    except Exception:  # noqa: BLE001 - availability probe
        return False
    else:
        return True
    finally:
        await client.aclose()


@pytest.fixture
async def storage_available() -> bool:
    """Whether the docker compose MinIO is reachable."""
    import aioboto3

    session = aioboto3.Session()
    try:
        async with session.client(
            "s3",
            endpoint_url=_storage_endpoint_url(),
            aws_access_key_id="lpg_storage",
            aws_secret_access_key="dev_only_not_a_real_secret",
            region_name="us-east-1",
        ) as client:
            await client.list_buckets()
    except Exception:  # noqa: BLE001 - availability probe
        return False
    else:
        return True
