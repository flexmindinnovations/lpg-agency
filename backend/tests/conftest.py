"""Shared pytest fixtures.

Integration tests run against a **real PostgreSQL and Redis** from docker
compose — never SQLite, never a mock. RLS policies and PostgreSQL-specific
types must actually be exercised, and a mock cannot exercise either
(``docs/implementation/testing-strategy.md``).

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
        "postgresql+asyncpg://lpg_app:dev_only_not_a_real_secret@localhost:55432/lpg_test",
    )


def _redis_url() -> str:
    return os.environ.get("LPG_TEST_REDIS_URL", "redis://localhost:56379/1")


@pytest.fixture
def integration_settings() -> Settings:
    """Settings pointed at the docker compose services."""
    return Settings(
        environment="local",
        log_json=False,
        database_url=_database_url(),
        redis_url=_redis_url(),
        health_check_timeout_seconds=5.0,
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

    client = redis.from_url(_redis_url(), decode_responses=True)
    try:
        await client.ping()
    except Exception:  # noqa: BLE001 - availability probe
        return False
    else:
        return True
    finally:
        await client.aclose()
