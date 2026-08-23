"""Fixtures scoped to `tests/integration/` only.

Kept separate from the top-level `tests/conftest.py` (whose fixtures also
serve unit tests that never touch a real Redis).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


def _admin_database_url() -> str:
    # Mirrors `tests/conftest.py::_admin_database_url` — duplicated for the
    # same self-containment reason `_redis_url` below already is.
    return os.environ.get(
        "LPG_TEST_ADMIN_DATABASE_URL",
        "postgresql+asyncpg://lpg_admin:dev_only_not_a_real_secret@localhost:55432/lpg_test",
    )


_license_auto_activation_installed = False


@pytest.fixture(autouse=True)
async def _auto_activate_licenses_for_new_tenants(postgres_available: bool) -> None:
    """Every login now requires an ACTIVE license (Tenant License
    Activation) — but dozens of pre-existing smoke-test fixture helpers
    across this directory `INSERT INTO tenant.tenant` directly via raw SQL
    and then log in as a freshly-created staff user, none of which know or
    care about licensing; teaching each one about `platform.license`
    individually would touch ~17 files for a concern none of them are
    actually testing.

    Installs a DB trigger once per test process instead — every new
    `tenant.tenant` row gets a long-lived, already-activated license
    automatically, the same "fix the shared test-infra gap in one place"
    approach `_flush_auth_rate_limits` above already uses for the Redis
    rate-limit-key contamination case. `test_license_repositories.py` is the
    one suite that genuinely exercises license issuance itself; its own
    `_seed_tenant` helper deletes the auto-created row before adding its own,
    since `platform.license.tenant_id` is unique.
    """
    global _license_auto_activation_installed
    if _license_auto_activation_installed or not postgres_available:
        return
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(_admin_database_url())
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("""
                    CREATE OR REPLACE FUNCTION platform.auto_activate_test_license()
                    RETURNS trigger AS $$
                    BEGIN
                        INSERT INTO platform.license (
                            id, tenant_id, key_hash, key_prefix, plan_tier,
                            validity_period_seconds, activated_at
                        ) VALUES (
                            gen_random_uuid(), NEW.id,
                            'TEST-' || md5(random()::text || NEW.id::text),
                            'TEST', 'premium', 315360000, now()
                        );
                        RETURN NEW;
                    END;
                    $$ LANGUAGE plpgsql
                """)
            )
            await conn.execute(
                text(
                    "DROP TRIGGER IF EXISTS trg_auto_activate_test_license ON tenant.tenant"
                )
            )
            await conn.execute(
                text("""
                    CREATE TRIGGER trg_auto_activate_test_license
                    AFTER INSERT ON tenant.tenant
                    FOR EACH ROW
                    EXECUTE FUNCTION platform.auto_activate_test_license()
                """)
            )
    finally:
        await engine.dispose()
    _license_auto_activation_installed = True


def _redis_url() -> str:
    # Mirrors `tests/conftest.py::_redis_url` — duplicated rather than
    # imported to keep this fixture self-contained and independent of
    # `tests` being importable as a package under any given pytest
    # invocation.
    return os.environ.get("LPG_TEST_REDIS_URL", "redis://localhost:56379/1")


@pytest.fixture(autouse=True)
async def _flush_auth_rate_limits(redis_available: bool) -> AsyncIterator[None]:
    """Clear `require_rate_limit`'s counters before every integration test.

    `auth:login`/`auth:otp_request`/`auth:password_forgot`
    (`dependencies/identity.py::require_rate_limit`) key by client IP, and
    every ASGI test client reports the same host — so login attempts from
    unrelated smoke tests accumulate against the *same* Redis key across the
    whole suite (all of `tests/integration/` shares one `lpg-redis`
    container, `tests/conftest.py::_redis_url`). Whichever test happens to
    run after ~10 prior logins then trips the 10/60s `auth:login` limit for
    a reason that has nothing to do with what it's testing — confirmed by
    every affected smoke test passing in isolation against a freshly
    flushed Redis.

    Scoped to the `auth:*` key namespace rather than the whole test DB, so
    it can't disturb OTP-store/idempotency/cache state another test set up
    (none of those use the `auth:` prefix — grep confirms `auth:` keys come
    only from `require_rate_limit`).
    """
    if redis_available:
        import redis.asyncio as redis

        # redis-py 5.x's `from_url` loses its type annotation under the <6
        # ceiling `arq` forces (ADR-029) — same note as `redis_available`.
        client = redis.from_url(_redis_url(), decode_responses=True)  # type: ignore[no-untyped-call]
        try:
            keys = [key async for key in client.scan_iter(match="auth:*")]
            if keys:
                await client.delete(*keys)
        finally:
            await client.aclose()
    yield
